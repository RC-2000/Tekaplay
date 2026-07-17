import uuid

from app.core.errors import ConflictError
from app.core.logging import get_logger
from app.events.bus import DomainEvent, EventBus
from app.modules.achievements.models import Achievement, UserAchievement
from app.modules.achievements.repository import (
    AchievementRepository,
    UserAchievementRepository,
)
from app.services.base import BaseService

log = get_logger(__name__)


class AchievementService(BaseService):
    def __init__(self, achievements: AchievementRepository,
                 grants: UserAchievementRepository, event_bus: EventBus) -> None:
        super().__init__(event_bus)
        self._achievements = achievements
        self._grants = grants

    async def define(self, *, code: str, title: str, description: str,
                     icon: str, xp_reward: int, hidden: bool) -> Achievement:
        if await self._achievements.get_by_code(code) is not None:
            raise ConflictError("An achievement with this code already exists",
                                details={"code": code})
        record = Achievement(code=code, title=title, description=description,
                             icon=icon, xp_reward=xp_reward, hidden=hidden)
        self._achievements.add(record)
        await self._achievements.flush()
        return record

    async def catalog(self, *, limit: int, offset: int) -> list[Achievement]:
        return await self._achievements.list(limit=limit, offset=offset)

    async def unlock(self, *, user_id: uuid.UUID, code: str) -> Achievement | None:
        """Grant if defined and not already held. Idempotent; the XP reward
        cascades as a normal xp.awarded event."""
        achievement = await self._achievements.get_by_code(code)
        if achievement is None:
            log.warning("achievement_code_undefined", code=code)
            return None
        if await self._grants.get_grant(user_id, achievement.id) is not None:
            return None
        self._grants.add(UserAchievement(user_id=user_id,
                                         achievement_id=achievement.id))
        await self._grants.flush()
        if achievement.xp_reward > 0:
            await self.emit(DomainEvent(
                name="xp.awarded", user_id=user_id,
                payload={"amount": achievement.xp_reward,
                         "reason": f"achievement:{code}"},
            ))
        return achievement

    async def unlocked_for(self, user_id: uuid.UUID) -> list[tuple[UserAchievement, Achievement]]:
        grants = await self._grants.list_for_user(user_id)
        result = []
        for grant in grants:
            achievement = await self._achievements.get(grant.achievement_id)
            result.append((grant, achievement))
        return result
