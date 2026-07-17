import uuid

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.deps import Bus, CurrentUser, DbSession
from app.modules.users.service import build_user_service
from app.modules.xp.repository import PlayerXpRepository, XpTransactionRepository
from app.modules.xp.service import XpService

router = APIRouter(prefix="/xp", tags=["xp"])


class XpSummary(BaseModel):
    total_xp: int
    level: int
    level_floor: int
    next_level_at: int


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: uuid.UUID
    display_name: str
    total_xp: int
    level: int


@router.get("/me", response_model=XpSummary)
async def my_xp(current_user: CurrentUser, session: DbSession, bus: Bus) -> XpSummary:
    service = XpService(PlayerXpRepository(session),
                        XpTransactionRepository(session), bus)
    return XpSummary(**await service.summary(current_user.id))


@router.get("/leaderboard", response_model=list[LeaderboardEntry])
async def leaderboard(
    _: CurrentUser, session: DbSession, bus: Bus,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[LeaderboardEntry]:
    service = XpService(PlayerXpRepository(session),
                        XpTransactionRepository(session), bus)
    rows = await service.leaderboard(limit)
    users = await build_user_service(session, bus).get_many(
        [r.user_id for r in rows])
    names = {u.id: u.display_name for u in users}
    return [
        LeaderboardEntry(rank=i + 1, user_id=r.user_id,
                         display_name=names.get(r.user_id, "Player"),
                         total_xp=r.total_xp, level=r.level)
        for i, r in enumerate(rows)
        if r.user_id in names  # soft-deleted users drop off the board
    ]
