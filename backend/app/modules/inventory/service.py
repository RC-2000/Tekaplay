import uuid

from app.events.bus import EventBus
from app.modules.inventory.models import PlayerInventoryItem
from app.modules.inventory.repository import PlayerInventoryRepository
from app.services.base import BaseService


class InventoryService(BaseService):
    def __init__(self, items: PlayerInventoryRepository, event_bus: EventBus) -> None:
        super().__init__(event_bus)
        self._items = items

    async def apply_change(self, *, user_id: uuid.UUID, source_slug: str,
                           item_key: str, delta: int) -> PlayerInventoryItem:
        record = await self._items.get_item(user_id, source_slug, item_key)
        if record is None:
            record = PlayerInventoryItem(user_id=user_id, source_slug=source_slug,
                                         item_key=item_key, qty=0)
            self._items.add(record)
        record.qty = max(0, record.qty + delta)
        await self._items.flush()
        return record

    async def list_for_user(self, user_id: uuid.UUID) -> list[PlayerInventoryItem]:
        return await self._items.list_for_user(user_id)
