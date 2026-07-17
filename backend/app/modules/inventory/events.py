from app.events.bus import DomainEvent, EventBus


def register(bus: EventBus) -> None:
    async def on_inventory_changed(event: DomainEvent) -> None:
        if event.user_id is None:
            return
        item = event.payload.get("item")
        delta = event.payload.get("delta")
        if not item or delta is None:
            return
        from app.db.session import SessionFactory
        from app.events.bus import bus as real_bus
        from app.modules.inventory.repository import PlayerInventoryRepository
        from app.modules.inventory.service import InventoryService

        async with SessionFactory() as session:
            service = InventoryService(PlayerInventoryRepository(session), real_bus)
            await service.apply_change(
                user_id=event.user_id,
                source_slug=str(event.payload.get("definition_slug", "")),
                item_key=str(item),
                delta=int(delta),
            )
            await session.commit()

    bus.subscribe("inventory.changed", on_inventory_changed)
