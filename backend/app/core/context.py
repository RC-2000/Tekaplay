"""Request-scoped context (request_id, user_id, correlation_id).

Stored in contextvars so it flows through async code and into every log line
via structlog.contextvars — no manual threading of IDs through call stacks.
"""
import uuid

import structlog


def bind_request_context(
    *,
    request_id: str | None = None,
    correlation_id: str | None = None,
    user_id: str | None = None,
) -> str:
    rid = request_id or uuid.uuid4().hex
    structlog.contextvars.bind_contextvars(
        request_id=rid,
        correlation_id=correlation_id or rid,
        user_id=user_id,
    )
    return rid


def clear_request_context() -> None:
    structlog.contextvars.clear_contextvars()
