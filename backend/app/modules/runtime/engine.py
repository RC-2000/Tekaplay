"""The Game Runtime interpreter.

Pure functions over (definition, state): no database, no HTTP, no clock beyond
what state carries. Every operation mutates the state dict it is given and
returns the pending domain events it implies. The service layer owns
persistence, ownership, concurrency, and turning pending events into
DomainEvents — this separation is what makes the runtime trivially testable
and reusable by future realtime/multiplayer transports.

State document (versioned via the session row's optimistic-lock column):
  scene_id, element_index, variables, flags, inventory, attempts,
  results, achievements, xp_earned, status, ending_id
"""
from typing import Any

from app.core.errors import ValidationFailedError
from app.modules.runtime import challenges
from app.modules.runtime.conditions import evaluate as condition_holds
from app.modules.runtime.definition import (
    ChallengeElement,
    ChoiceElement,
    DialogueElement,
    GameDefinition,
    MediaElement,
    Outcome,
    Scene,
)
from app.modules.runtime.effects import PendingEvent, apply_effects

STATUS_ACTIVE = "active"
STATUS_COMPLETED = "completed"


class View:
    """What the client is allowed to see right now. The client is a renderer
    of server state; nothing here ever contains answers."""

    def __init__(self) -> None:
        self.passives: list[dict[str, Any]] = []
        self.interactive: dict[str, Any] | None = None
        self.can_advance: bool = False
        self.ending: dict[str, Any] | None = None


def new_state(defn: GameDefinition) -> tuple[dict[str, Any], list[PendingEvent]]:
    state: dict[str, Any] = {
        "scene_id": None,
        "element_index": 0,
        "variables": dict(defn.variables),
        "flags": [],
        "inventory": {},
        "attempts": {},
        "results": {},
        "achievements": [],
        "xp_earned": 0,
        "status": STATUS_ACTIVE,
        "ending_id": None,
    }
    events = _enter_scene(defn, state, defn.start_scene)
    return state, events


def compute_view(defn: GameDefinition, state: dict[str, Any]) -> View:
    view = View()
    if state["status"] == STATUS_COMPLETED:
        scene = _scene(defn, state["scene_id"])
        view.ending = scene.ending.model_dump() if scene.ending else {"id": state["ending_id"]}
        return view

    scene = _scene(defn, state["scene_id"])
    index = state["element_index"]
    while index < len(scene.elements):
        element = scene.elements[index]
        if isinstance(element, DialogueElement):
            if condition_holds(element.condition, state):
                npc = defn.npcs.get(element.npc) if element.npc else None
                view.passives.append({
                    "type": "dialogue",
                    "npc": ({"id": element.npc, "name": npc.name, "role": npc.role}
                            if npc else None),
                    "text": element.text,
                })
            index += 1
        elif isinstance(element, MediaElement):
            if condition_holds(element.condition, state):
                view.passives.append({
                    "type": "media", "kind": element.kind,
                    "asset_id": element.asset_id, "caption": element.caption,
                })
            index += 1
        elif isinstance(element, ChoiceElement):
            visible = [
                {"id": o.id, "text": o.text}
                for o in element.options
                if condition_holds(o.condition, state)
            ]
            view.interactive = {
                "type": "choice", "id": element.id,
                "prompt": element.prompt, "options": visible,
            }
            return view
        elif isinstance(element, ChallengeElement):
            attempts_used = state["attempts"].get(element.id, 0)
            view.interactive = {
                "type": "challenge", "id": element.id,
                "challenge_type": element.challenge_type,
                "config": challenges.get(element.challenge_type).public_config(element.config),
                "attempts_remaining": element.max_attempts - attempts_used,
            }
            return view
    view.can_advance = True  # scene exhausted; advance() follows next/ending
    return view


def advance(defn: GameDefinition, state: dict[str, Any]) -> list[PendingEvent]:
    """Move past the end of an exhausted scene (to `next` or the ending)."""
    _require_active(state)
    view = compute_view(defn, state)
    if view.interactive is not None:
        raise ValidationFailedError(
            "Resolve the current interaction first",
            details={"pending": view.interactive["type"], "id": view.interactive["id"]},
        )
    scene = _scene(defn, state["scene_id"])
    events: list[PendingEvent] = [("scene.completed", {"scene_id": state["scene_id"]})]
    if scene.ending is not None:
        events += _finish(state, scene.ending.id)
    elif scene.next is not None:
        events += _enter_scene(defn, state, scene.next)
    else:  # publish-time validation guarantees a branching exit was taken instead
        raise ValidationFailedError("Scene has no onward transition")
    return events


def choose(defn: GameDefinition, state: dict[str, Any], element_id: str,
           option_id: str) -> list[PendingEvent]:
    _require_active(state)
    element, index = _pending_interactive(defn, state)
    if not isinstance(element, ChoiceElement) or element.id != element_id:
        raise ValidationFailedError("That choice is not currently active",
                                    details={"element_id": element_id})
    option = next((o for o in element.options if o.id == option_id), None)
    if option is None or not condition_holds(option.condition, state):
        raise ValidationFailedError("Invalid option", details={"option_id": option_id})
    events = apply_effects(state, option.effects)
    state["element_index"] = index + 1
    if option.goto is not None:
        events += [("scene.completed", {"scene_id": state["scene_id"]})]
        events += _enter_scene(defn, state, option.goto)
    return events


def answer(defn: GameDefinition, state: dict[str, Any], element_id: str,
           response: dict[str, Any]) -> tuple[challenges.ChallengeResult, list[PendingEvent]]:
    _require_active(state)
    element, index = _pending_interactive(defn, state)
    if not isinstance(element, ChallengeElement) or element.id != element_id:
        raise ValidationFailedError("That challenge is not currently active",
                                    details={"element_id": element_id})
    attempts = state["attempts"].get(element.id, 0)
    if attempts >= element.max_attempts:
        raise ValidationFailedError("No attempts remaining",
                                    details={"element_id": element_id})
    result = challenges.get(element.challenge_type).evaluate(element.config, response)
    state["attempts"][element.id] = attempts + 1
    events: list[PendingEvent] = [(
        "question.answered",
        {
            "challenge_id": element.id,
            "challenge_type": element.challenge_type,
            "correct": result.correct,
            "score": result.score,
            "attempt": attempts + 1,
        },
    )]
    if result.correct:
        state["results"][element.id] = {"correct": True, "score": result.score,
                                        "attempts": attempts + 1}
        events += _resolve_outcome(defn, state, element.on_correct, index)
    else:
        events += apply_effects(state, element.on_incorrect.effects)
        if state["attempts"][element.id] >= element.max_attempts:
            state["results"][element.id] = {"correct": False, "score": result.score,
                                            "attempts": attempts + 1}
            exhausted = element.on_exhausted or Outcome()
            events += _resolve_outcome(defn, state, exhausted, index)
        elif element.on_incorrect.goto is not None:
            events += [("scene.completed", {"scene_id": state["scene_id"]})]
            events += _enter_scene(defn, state, element.on_incorrect.goto)
    return result, events


# ── internals ──────────────────────────────────────────────────
def _scene(defn: GameDefinition, scene_id: str) -> Scene:
    return defn.scenes[scene_id]


def _require_active(state: dict[str, Any]) -> None:
    if state["status"] != STATUS_ACTIVE:
        raise ValidationFailedError("This session is already completed")


def _pending_interactive(defn: GameDefinition, state: dict[str, Any]):
    """Locate the interactive element the player is currently blocked on."""
    scene = _scene(defn, state["scene_id"])
    index = state["element_index"]
    while index < len(scene.elements):
        element = scene.elements[index]
        if isinstance(element, (ChoiceElement, ChallengeElement)):
            return element, index
        index += 1
    raise ValidationFailedError("No interaction is pending")


def _resolve_outcome(defn: GameDefinition, state: dict[str, Any], outcome: Outcome,
                     element_index: int) -> list[PendingEvent]:
    events = apply_effects(state, outcome.effects)
    state["element_index"] = element_index + 1
    if outcome.goto is not None:
        events += [("scene.completed", {"scene_id": state["scene_id"]})]
        events += _enter_scene(defn, state, outcome.goto)
    return events


def _enter_scene(defn: GameDefinition, state: dict[str, Any],
                 scene_id: str) -> list[PendingEvent]:
    state["scene_id"] = scene_id
    state["element_index"] = 0
    events: list[PendingEvent] = [("scene.entered", {"scene_id": scene_id})]
    events += apply_effects(state, defn.scenes[scene_id].on_enter)
    return events


def _finish(state: dict[str, Any], ending_id: str) -> list[PendingEvent]:
    state["status"] = STATUS_COMPLETED
    state["ending_id"] = ending_id
    return [("mission.finished", {
        "ending_id": ending_id,
        "xp_earned": state.get("xp_earned", 0),
        "results": state.get("results", {}),
    })]
