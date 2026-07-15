import uuid

from sqlalchemy import select

from app.modules.runtime.models import GameDefinitionRecord, GameSession, SavePoint
from app.repositories.base import BaseRepository


class GameDefinitionRepository(BaseRepository[GameDefinitionRecord]):
    model = GameDefinitionRecord

    async def get_live_by_slug(self, slug: str) -> GameDefinitionRecord | None:
        stmt = self._base_query().where(
            GameDefinitionRecord.slug == slug,
            GameDefinitionRecord.live.is_(True),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_live(self, *, limit: int, offset: int) -> list[GameDefinitionRecord]:
        stmt = (self._base_query()
                .where(GameDefinitionRecord.live.is_(True))
                .limit(limit).offset(offset))
        return list((await self.session.execute(stmt)).scalars())

    async def live_slug_map(self) -> dict[str, "GameDefinitionRecord"]:
        stmt = self._base_query().where(GameDefinitionRecord.live.is_(True))
        return {r.slug: r for r in (await self.session.execute(stmt)).scalars()}


class GameSessionRepository(BaseRepository[GameSession]):
    model = GameSession

    async def get_active(self, user_id: uuid.UUID,
                         definition_id: uuid.UUID) -> GameSession | None:
        stmt = (
            select(GameSession)
            .where(
                GameSession.user_id == user_id,
                GameSession.definition_id == definition_id,
                GameSession.status == "active",
            )
            .order_by(GameSession.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class SavePointRepository(BaseRepository[SavePoint]):
    model = SavePoint

    async def list_for_session(self, session_id: uuid.UUID) -> list[SavePoint]:
        stmt = (select(SavePoint)
                .where(SavePoint.session_id == session_id)
                .order_by(SavePoint.created_at.desc()))
        return list((await self.session.execute(stmt)).scalars())
