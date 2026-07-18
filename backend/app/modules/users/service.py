import uuid
from datetime import UTC, datetime

from app.core.errors import NotFoundError
from app.events.bus import DomainEvent, EventBus
from app.modules.users import events
from app.modules.users.audit import AuditService
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserUpdate
from app.services.base import BaseService


class UserService(BaseService):
    def __init__(self, repo: UserRepository, audit: AuditService, event_bus: EventBus) -> None:
        super().__init__(event_bus)
        self._repo = repo
        self._audit = audit

    async def get(self, user_id: uuid.UUID) -> User:
        return await self._repo.get(user_id)

    async def list(self, *, limit: int, offset: int) -> list[User]:
        return await self._repo.list(limit=limit, offset=offset)

    async def get_many(self, ids: list[uuid.UUID]) -> list[User]:
        return await self._repo.get_many(ids)

    async def organization_ids_for(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        return await self._repo.organization_ids_for(user_id)

    async def update_profile(self, user_id: uuid.UUID, patch: UserUpdate) -> User:
        user = await self._repo.get(user_id)
        for field, value in patch.model_dump(exclude_none=True).items():
            setattr(user, field, value)
        await self._repo.flush()
        await self.emit(DomainEvent(name=events.USER_UPDATED, user_id=user.id))
        return user

    async def delete_account(self, user_id: uuid.UUID, *, ip_address: str | None = None) -> None:
        """Soft-delete + anonymize (privacy requirement). Refresh-token
        revocation happens in the auth module via the user.deleted event —
        this module doesn't know auth exists."""
        user = await self._repo.get(user_id)
        user.deleted_at = datetime.now(UTC)
        user.is_active = False
        user.email = f"deleted-{user.id}@anonymized.invalid"
        user.display_name = "Deleted user"
        user.avatar_url = None
        user.password_hash = None
        await self._repo.flush()
        self._audit.record(
            action="user.account_deleted",
            actor_user_id=user_id,
            entity_type="user",
            entity_id=user_id,
            ip_address=ip_address,
        )
        await self.emit(DomainEvent(name=events.USER_DELETED, user_id=user_id))

    async def require_active(self, user_id: uuid.UUID) -> User:
        user = await self._repo.get(user_id)
        if not user.is_active:
            raise NotFoundError("User not found", details={"id": str(user_id)})
        return user


def build_user_service(session, event_bus: EventBus) -> UserService:
    """Composition helper — how other modules obtain the users service."""
    from app.modules.users.audit import AuditService
    from app.modules.users.repository import UserRepository

    return UserService(UserRepository(session), AuditService(session), event_bus)
