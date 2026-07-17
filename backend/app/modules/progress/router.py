import uuid
from datetime import date, datetime

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from app.api.deps import Bus, CurrentUser, DbSession
from app.modules.progress.repository import (
    MissionProgressRepository,
    PlayerStreakRepository,
)
from app.modules.progress.service import ProgressService

router = APIRouter(prefix="/progress", tags=["progress"])


class ProgressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    status: str
    completions: int
    best_ending: str | None
    questions_answered: int
    questions_correct: int
    last_played_at: datetime | None


class StreakOut(BaseModel):
    current_streak: int
    longest_streak: int
    last_activity_date: date | None


def _service(session, bus) -> ProgressService:
    return ProgressService(MissionProgressRepository(session),
                           PlayerStreakRepository(session), bus)


@router.get("/me", response_model=list[ProgressOut])
async def my_progress(current_user: CurrentUser, session: DbSession,
                      bus: Bus) -> list[ProgressOut]:
    records = await _service(session, bus).list_for_user(current_user.id)
    return [ProgressOut.model_validate(r) for r in records]


@router.get("/me/streak", response_model=StreakOut)
async def my_streak(current_user: CurrentUser, session: DbSession,
                    bus: Bus) -> StreakOut:
    streak = await _service(session, bus).streak_for(current_user.id)
    if streak is None:
        return StreakOut(current_streak=0, longest_streak=0, last_activity_date=None)
    return StreakOut(current_streak=streak.current_streak,
                     longest_streak=streak.longest_streak,
                     last_activity_date=streak.last_activity_date)
