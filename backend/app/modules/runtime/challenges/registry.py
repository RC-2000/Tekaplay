"""Challenge-type registry — the runtime's extensibility point.

A challenge type owns three things: config validation (publish time),
public projection (what the client may see — NEVER answers), and evaluation.
Adding a game type = register a type here + ship a renderer component;
the runtime core never changes. This is the seam future plugins use.
"""
from typing import Any, Protocol

from pydantic import BaseModel

from app.core.errors import ValidationFailedError


class ChallengeResult(BaseModel):
    correct: bool
    score: float  # 0.0–1.0; partial credit where the type supports it
    feedback: str = ""


class ChallengeType(Protocol):
    type_name: str

    def validate_config(self, config: dict[str, Any]) -> None: ...
    def public_config(self, config: dict[str, Any]) -> dict[str, Any]: ...
    def evaluate(self, config: dict[str, Any], response: dict[str, Any]) -> ChallengeResult: ...


_REGISTRY: dict[str, ChallengeType] = {}


def register(challenge_type: ChallengeType) -> None:
    _REGISTRY[challenge_type.type_name] = challenge_type


def get(type_name: str) -> ChallengeType:
    challenge_type = _REGISTRY.get(type_name)
    if challenge_type is None:
        raise ValidationFailedError(
            "Unknown challenge type", details={"challenge_type": type_name}
        )
    return challenge_type


def registered_types() -> list[str]:
    return sorted(_REGISTRY)
