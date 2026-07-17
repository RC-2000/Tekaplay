from app.events.bus import DomainEvent, EventBus


def register(bus: EventBus) -> None:
    async def on_achievement_unlocked(event: DomainEvent) -> None:
        if event.user_id is None:
            return
        from app.db.session import SessionFactory
        from app.events.bus import BufferedEventBus
        from app.events.bus import bus as real_bus
        from app.modules.achievements.repository import (
            AchievementRepository,
            UserAchievementRepository,
        )
        from app.modules.achievements.service import AchievementService

        code = event.payload.get("code")
        if not code:
            return
        # Same commit-then-flush discipline as the request layer: the XP
        # cascade must not dispatch against our uncommitted transaction.
        buffered = BufferedEventBus(real_bus)
        async with SessionFactory() as session:
            service = AchievementService(AchievementRepository(session),
                                         UserAchievementRepository(session),
                                         buffered)
            await service.unlock(user_id=event.user_id, code=str(code))
            await session.commit()
        await buffered.flush()

    bus.subscribe("achievement.unlocked", on_achievement_unlocked)
