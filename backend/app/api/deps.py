"""Shared FastAPI dependencies (the composition seam for DI).

Route handlers depend on these providers; providers wire services to
repositories and the event bus. Tests override any provider with
app.dependency_overrides — no patching, no globals.

RBAC model: permissions are code-defined granular capabilities; roles bundle
them; users hold roles. Routes declare require_permission("x.y") and stay
ignorant of roles entirely, so role composition is runtime-configurable
without code changes.
"""
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.security import decode_access_token
from app.db.session import get_session
from app.events.bus import EventBus, bus


async def get_db() -> AsyncIterator[AsyncSession]:
    async for session in get_session():
        yield session


def get_event_bus() -> EventBus:
    return bus


DbSession = Annotated[AsyncSession, Depends(get_db)]
Bus = Annotated[EventBus, Depends(get_event_bus)]


async def get_current_user(request: Request, session: DbSession):
    """Resolve the Bearer token to an active user. Binds user_id into the
    logging context so every subsequent log line in the request carries it."""
    import structlog

    from app.modules.users.repository import UserRepository

    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthenticationError("Missing bearer token")
    user_id = decode_access_token(token)
    user = await UserRepository(session).get(user_id)
    if not user.is_active:
        raise AuthenticationError("Account is not active")
    structlog.contextvars.bind_contextvars(user_id=str(user.id))
    return user


from app.modules.users.models import User  # noqa: E402  (import cycle guard)

CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permission(code: str):
    """Route-level permission gate: dependencies=[require_permission("users.read")].

    Services re-check critical permissions internally (defense in depth); this
    gate is the first line, producing a uniform 403 envelope.
    """

    async def _check(current_user: CurrentUser, session: DbSession) -> None:
        from app.modules.users.repository import UserRepository

        codes = await UserRepository(session).get_permission_codes(current_user.id)
        if code not in codes:
            raise PermissionDeniedError(
                "You don't have permission to do this", details={"required": code}
            )

    return Depends(_check)
