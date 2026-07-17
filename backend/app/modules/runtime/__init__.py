from app.modules.runtime.challenges.builtin import register_builtin_types
from app.modules.runtime.challenges.registry import (
    ChallengeResult,
    ChallengeType,
    get,
    register,
    registered_types,
)

register_builtin_types()

__all__ = ["ChallengeResult", "ChallengeType", "get", "register", "registered_types"]
