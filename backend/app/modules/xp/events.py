"""Subscriber: turns runtime xp.awarded events into durable XP.

Handlers own their sessions (post-commit delivery via BufferedEventBus) and
construct their service against the REAL bus so cascades (level.up) dispatch
immediately.
"""
import uuid

from app.events.bus import DomainEvent, EventBus


def register(bus: EventBus) -> None:
    async def on_xp_awarded(event: DomainEvent) -> None:
        if event.user_id is None:
            return
        from app.db.session import SessionFactory
        from app.events.bus import BufferedEventBus
        from app.events.bus import bus as real_bus
        from app.modules.xp.repository import (
            PlayerXpRepository,
            XpTransactionRepository,
        )
        from app.modules.xp.service import XpService

        session_id = event.payload.get("session_id")
        buffered = BufferedEventBus(real_bus)  # level.up flushes post-commit
        async with SessionFactory() as session:
            service = XpService(PlayerXpRepository(session),
                                XpTransactionRepository(session), buffered)
            await service.apply_award(
                user_id=event.user_id,
                amount=int(event.payload.get("amount", 0)),
                reason=str(event.payload.get("reason", "")),
                session_id=uuid.UUID(session_id) if session_id else None,
            )
            await session.commit()
        await buffered.flush()

    bus.subscribe("xp.awarded", on_xp_awarded)
