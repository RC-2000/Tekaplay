"""Standard error model for the entire API.

Every error the platform returns has the same envelope:

    {"error": {"code": "...", "message": "...", "details": {...}, "request_id": "..."}}

Services raise AppError subclasses; the exception handlers in main.py translate
them to HTTP. Modules never construct HTTPException themselves — that keeps
business logic transport-agnostic (the same services will later back gRPC,
workers, and websockets).
"""
from typing import Any


class AppError(Exception):
    """Base application error. code is a stable, machine-readable identifier."""

    status_code: int = 500
    code: str = "internal_error"
    retryable: bool = False

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ValidationFailedError(AppError):
    status_code = 422
    code = "validation_failed"


class AuthenticationError(AppError):
    status_code = 401
    code = "authentication_required"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "permission_denied"


class ConflictError(AppError):
    """Optimistic-concurrency or uniqueness conflicts. Clients may retry with fresh state."""

    status_code = 409
    code = "conflict"
    retryable = True


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"
    retryable = True
