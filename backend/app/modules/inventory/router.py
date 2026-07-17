import uuid

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from app.api.deps import Bus, CurrentUser, DbSession
from app.modules.inventory.repository import PlayerInventoryRepository
from app.modules.inventory.service import InventoryService

router = APIRouter(prefix="/inventory", tags=["inventory"])


class InventoryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_slug: str
    item_key: str
    qty: int


@router.get("/me", response_model=list[InventoryItemOut])
async def my_inventory(current_user: CurrentUser, session: DbSession,
                       bus: Bus) -> list[InventoryItemOut]:
    service = InventoryService(PlayerInventoryRepository(session), bus)
    items = await service.list_for_user(current_user.id)
    return [InventoryItemOut.model_validate(i) for i in items]
