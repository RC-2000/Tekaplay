import uuid
from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import Bus, CurrentUser, DbSession, require_permission
from app.modules.achievements.repository import (
    AchievementRepository,
    UserAchievementRepository,
)
from app.modules.achievements.service import AchievementService

router = APIRouter(prefix="/achievements", tags=["achievements"])


class AchievementCreate(BaseModel):
    code: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    icon: str = ""
    xp_reward: int = Field(default=0, ge=0)
    hidden: bool = False


class AchievementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    title: str
    description: str
    icon: str
    xp_reward: int
    hidden: bool


class UnlockedOut(AchievementOut):
    unlocked_at: datetime


def _service(session, bus) -> AchievementService:
    return AchievementService(AchievementRepository(session),
                              UserAchievementRepository(session), bus)


@router.get("", response_model=list[AchievementOut])
async def catalog(
    _: CurrentUser, session: DbSession, bus: Bus,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[AchievementOut]:
    records = await _service(session, bus).catalog(limit=limit, offset=offset)
    # hidden achievements stay out of the public catalog until unlocked
    return [AchievementOut.model_validate(r) for r in records if not r.hidden]


@router.get("/me", response_model=list[UnlockedOut])
async def my_achievements(current_user: CurrentUser, session: DbSession,
                          bus: Bus) -> list[UnlockedOut]:
    pairs = await _service(session, bus).unlocked_for(current_user.id)
    return [
        UnlockedOut(**AchievementOut.model_validate(a).model_dump(),
                    unlocked_at=grant.created_at)
        for grant, a in pairs
    ]


@router.post("", response_model=AchievementOut, status_code=201,
             dependencies=[require_permission("achievements.manage")])
async def define(body: AchievementCreate, session: DbSession, bus: Bus) -> AchievementOut:
    record = await _service(session, bus).define(**body.model_dump())
    return AchievementOut.model_validate(record)
