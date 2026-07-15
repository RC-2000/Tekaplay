import pytest

from app.core.errors import ValidationFailedError
from app.modules.runtime import challenges


def test_registry_lists_builtins():
    assert {"quiz", "ordering", "text_input"} <= set(challenges.registered_types())


def test_unknown_type_rejected():
    with pytest.raises(ValidationFailedError):
        challenges.get("vr_simulation")


def test_ordering_partial_credit():
    ordering = challenges.get("ordering")
    config = {"prompt": "p",
              "items": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"},
                        {"id": "c", "text": "C"}],
              "correct_order": ["a", "b", "c"]}
    result = ordering.evaluate(config, {"order": ["a", "c", "b"]})
    assert not result.correct
    assert result.score == pytest.approx(1 / 3)


def test_text_input_case_insensitive_default():
    text = challenges.get("text_input")
    config = {"prompt": "p", "answers": ["us-east-1"]}
    assert text.evaluate(config, {"text": "  US-East-1 "}).correct


def test_quiz_public_config_strips_answers():
    quiz = challenges.get("quiz")
    config = {"question": "q", "options": [{"id": "a", "text": "A"},
                                           {"id": "b", "text": "B"}],
              "correct": ["a"], "explanation": "secret"}
    public = quiz.public_config(config)
    assert "correct" not in public and "explanation" not in public
    assert public["multi_select"] is False
