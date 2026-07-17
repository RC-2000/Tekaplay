import uuid
from datetime import UTC, datetime, timedelta

from app.events.bus import EventBus
from app.modules.progress.models import MissionProgress, PlayerStreak
from app.modules.progress.repository import (
    MissionProgressRepository,
    PlayerStreakRepository,
)
from app.services.base import BaseService


class ProgressService(BaseService):
    def __init__(self, progress: MissionProgressRepository,
                 streaks: PlayerStreakRepository, event_bus: EventBus) -> None:
        super().__init__(event_bus)
        self._progress = progress
        self._streaks = streaks

    async def _get_or_create(self, user_id: uuid.UUID, slug: str) -> MissionProgress:
        record = await self._progress.get_for(user_id, slug)
        if record is None:
            record = MissionProgress(user_id=user_id, slug=slug)
            self._progress.add(record)
        return record

    async def touch_started(self, *, user_id: uuid.UUID, slug: str) -> None:
        record = await self._get_or_create(user_id, slug)
        if record.status != "completed":
            record.status = "in_progress"
        record.last_played_at = datetime.now(UTC)
        await self._progress.flush()

    async def record_answer(self, *, user_id: uuid.UUID, slug: str,
                            correct: bool) -> None:
        record = await self._get_or_create(user_id, slug)
        record.questions_answered += 1
        if correct:
            record.questions_correct += 1
        record.last_played_at = datetime.now(UTC)
        await self._progress.flush()

    async def record_finish(self, *, user_id: uuid.UUID, slug: str,
                            ending_id: str | None) -> None:
        record = await self._get_or_create(user_id, slug)
        record.status = "completed"
        record.completions += 1
        record.best_ending = ending_id or record.best_ending
        record.last_played_at = datetime.now(UTC)
        await self._progress.flush()

    async def bump_streak(self, *, user_id: uuid.UUID) -> PlayerStreak:
        today = datetime.now(UTC).date()
        streak = await self._streaks.get_for_user(user_id)
        if streak is None:
            streak = PlayerStreak(user_id=user_id, current_streak=1,
                                  longest_streak=1, last_activity_date=today)
            self._streaks.add(streak)
        elif streak.last_activity_date == today:
            pass  # already counted today
        elif streak.last_activity_date == today - timedelta(days=1):
            streak.current_streak += 1
            streak.longest_streak = max(streak.longest_streak, streak.current_streak)
            streak.last_activity_date = today
        else:
            streak.current_streak = 1
            streak.longest_streak = max(streak.longest_streak, 1)
            streak.last_activity_date = today
        await self._streaks.flush()
        return streak

    async def list_for_user(self, user_id: uuid.UUID) -> list[MissionProgress]:
        return await self._progress.list_for_user(user_id)

    async def streak_for(self, user_id: uuid.UUID) -> PlayerStreak | None:
        return await self._streaks.get_for_user(user_id)
