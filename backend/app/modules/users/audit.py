"""Audit trail writer. Any module may depend on this service interface."""
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import AuditLog


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def record(
        self,
        *,
        action: str,
        actor_user_id: uuid.UUID | None = None,
        entity_type: str | None = None,
        entity_id: uuid.UUID | None = None,
        meta: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> None:
        self._session.add(
            AuditLog(
                action=action,
                actor_user_id=actor_user_id,
                entity_type=entity_type,
                entity_id=entity_id,
                meta=meta or {},
                ip_address=ip_address,
            )
        )
