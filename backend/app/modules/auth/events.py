"""Events published by auth + subscriptions it registers.

Verification and reset TOKENS travel only inside events consumed server-side
(the notification module will render them into emails); they are never
returned in API responses.
"""
from app.events.bus import DomainEvent, EventBus
from app.modules.users.events import USER_DELETED

VERIFICATION_REQUESTED = "auth.verification_requested"
PASSWORD_RESET_REQUESTED = "auth.password_reset_requested"
PASSWORD_CHANGED = "auth.password_changed"
LOGIN_SUCCEEDED = "auth.login_succeeded"
REFRESH_REUSE_DETECTED = "auth.refresh_reuse_detected"


def register(bus: EventBus) -> None:
    """Cross-module reaction: when a user deletes their account (users module),
    kill every session. Auth knows users' events; users knows nothing of auth."""

    async def revoke_sessions_on_user_deleted(event: DomainEvent) -> None:
        # Handler owns its session: subscribers must never piggyback on the
        # emitting request's transaction.
        from app.db.session import SessionFactory
        from app.modules.auth.repository import RefreshTokenRepository

        if event.user_id is None:
            return
        async with SessionFactory() as session:
            await RefreshTokenRepository(session).revoke_all_for_user(event.user_id)
            await session.commit()

    bus.subscribe(USER_DELETED, revoke_sessions_on_user_deleted)
