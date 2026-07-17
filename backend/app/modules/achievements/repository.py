import uuid

from sqlalchemy import select

from app.modules.achievements.models import Achievement, UserAchievement
from app.repositories.base import BaseRepository


class AchievementRepository(BaseRepository[Achievement]):
    model = Achievement

    async def get_by_code(self, code: str) -> Achievement | None:
        stmt = select(Achievement).where(Achievement.code == code)
        return (await self.session.execute(stmt)).scalar_one_or_none()


class UserAchievementRepository(BaseRepository[UserAchievement]):
    model = UserAchievement

    async def get_grant(self, user_id: uuid.UUID,
                        achievement_id: uuid.UUID) -> UserAchievement | None:
        stmt = select(UserAchievement).where(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_id == achievement_id,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[UserAchievement]:
        stmt = (select(UserAchievement)
                .where(UserAchievement.user_id == user_id)
                .order_by(UserAchievement.created_at.desc()))
        return list((await self.session.execute(stmt)).scalars())
