"""XP aggregation and the level curve.

Curve: total XP for level n is 100·(n−1)². L1 starts at 0, L2 at 100,
L3 at 400, L4 at 900 — quadratic, tuned later without schema changes because
the ledger is append-only and the aggregate is recomputable.
"""
import uuid

from app.events.bus import DomainEvent, EventBus
from app.modules.xp.models import PlayerXp, XpTransaction
from app.modules.xp.repository import PlayerXpRepository, XpTransactionRepository
from app.services.base import BaseService

LEVEL_UP = "level.up"


def level_for_total(total_xp: int) -> int:
    return int((max(total_xp, 0) / 100) ** 0.5) + 1


def total_for_level(level: int) -> int:
    return 100 * (max(level, 1) - 1) ** 2


class XpService(BaseService):
    def __init__(self, players: PlayerXpRepository,
                 transactions: XpTransactionRepository,
                 event_bus: EventBus) -> None:
        super().__init__(event_bus)
        self._players = players
        self._transactions = transactions

    async def apply_award(self, *, user_id: uuid.UUID, amount: int, reason: str,
                          session_id: uuid.UUID | None = None) -> PlayerXp:
        record = await self._players.get_for_user(user_id)
        if record is None:
            record = PlayerXp(user_id=user_id, total_xp=0, level=1)
            self._players.add(record)
        self._transactions.add(XpTransaction(user_id=user_id, amount=amount,
                                             reason=reason, session_id=session_id))
        old_level = record.level
        record.total_xp += amount
        record.level = level_for_total(record.total_xp)
        await self._players.flush()
        if record.level > old_level:
            await self.emit(DomainEvent(name=LEVEL_UP, user_id=user_id,
                                        payload={"level": record.level,
                                                 "total_xp": record.total_xp}))
        return record

    async def summary(self, user_id: uuid.UUID) -> dict:
        record = await self._players.get_for_user(user_id)
        total = record.total_xp if record else 0
        level = record.level if record else 1
        return {
            "total_xp": total,
            "level": level,
            "level_floor": total_for_level(level),
            "next_level_at": total_for_level(level + 1),
        }

    async def leaderboard(self, limit: int) -> list[PlayerXp]:
        return await self._players.top(limit)
