import uuid

from sqlalchemy import select

from app.modules.progress.models import MissionProgress, PlayerStreak
from app.repositories.base import BaseRepository


class MissionProgressRepository(BaseRepository[MissionProgress]):
    model = MissionProgress

    async def get_for(self, user_id: uuid.UUID, slug: str) -> MissionProgress | None:
        stmt = select(MissionProgress).where(MissionProgress.user_id == user_id,
                                             MissionProgress.slug == slug)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[MissionProgress]:
        stmt = (select(MissionProgress)
                .where(MissionProgress.user_id == user_id)
                .order_by(MissionProgress.last_played_at.desc()))
        return list((await self.session.execute(stmt)).scalars())


class PlayerStreakRepository(BaseRepository[PlayerStreak]):
    model = PlayerStreak

    async def get_for_user(self, user_id: uuid.UUID) -> PlayerStreak | None:
        stmt = select(PlayerStreak).where(PlayerStreak.user_id == user_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()
