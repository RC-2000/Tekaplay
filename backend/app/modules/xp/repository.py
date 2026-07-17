import uuid

from sqlalchemy import select

from app.modules.xp.models import PlayerXp, XpTransaction
from app.repositories.base import BaseRepository


class PlayerXpRepository(BaseRepository[PlayerXp]):
    model = PlayerXp

    async def get_for_user(self, user_id: uuid.UUID) -> PlayerXp | None:
        stmt = select(PlayerXp).where(PlayerXp.user_id == user_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def top(self, limit: int) -> list[PlayerXp]:
        stmt = (select(PlayerXp)
                .order_by(PlayerXp.total_xp.desc(), PlayerXp.created_at.asc())
                .limit(limit))
        return list((await self.session.execute(stmt)).scalars())


class XpTransactionRepository(BaseRepository[XpTransaction]):
    model = XpTransaction
