import uuid

from sqlalchemy import select

from app.modules.inventory.models import PlayerInventoryItem
from app.repositories.base import BaseRepository


class PlayerInventoryRepository(BaseRepository[PlayerInventoryItem]):
    model = PlayerInventoryItem

    async def get_item(self, user_id: uuid.UUID, source_slug: str,
                       item_key: str) -> PlayerInventoryItem | None:
        stmt = select(PlayerInventoryItem).where(
            PlayerInventoryItem.user_id == user_id,
            PlayerInventoryItem.source_slug == source_slug,
            PlayerInventoryItem.item_key == item_key,
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[PlayerInventoryItem]:
        stmt = (select(PlayerInventoryItem)
                .where(PlayerInventoryItem.user_id == user_id,
                       PlayerInventoryItem.qty > 0)
                .order_by(PlayerInventoryItem.item_key))
        return list((await self.session.execute(stmt)).scalars())
