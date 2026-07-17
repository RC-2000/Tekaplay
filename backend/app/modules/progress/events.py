"""Progress and streaks are pure event consumers of the runtime's stream.
Events without a definition_slug (e.g. emitted before slug enrichment, or
non-mission activity) are skipped for progress but still count for streaks."""
from app.events.bus import DomainEvent, EventBus


def register(bus: EventBus) -> None:
    async def _service(session):
        from app.events.bus import bus as real_bus
        from app.modules.progress.repository import (
            MissionProgressRepository,
            PlayerStreakRepository,
        )
        from app.modules.progress.service import ProgressService

        return ProgressService(MissionProgressRepository(session),
                               PlayerStreakRepository(session), real_bus)

    async def on_mission_started(event: DomainEvent) -> None:
        if event.user_id is None:
            return
        from app.db.session import SessionFactory

        slug = event.payload.get("definition_slug")
        async with SessionFactory() as session:
            service = await _service(session)
            if slug:
                await service.touch_started(user_id=event.user_id, slug=str(slug))
            await service.bump_streak(user_id=event.user_id)
            await session.commit()

    async def on_question_answered(event: DomainEvent) -> None:
        if event.user_id is None:
            return
        from app.db.session import SessionFactory

        slug = event.payload.get("definition_slug")
        async with SessionFactory() as session:
            service = await _service(session)
            if slug:
                await service.record_answer(user_id=event.user_id, slug=str(slug),
                                            correct=bool(event.payload.get("correct")))
            await service.bump_streak(user_id=event.user_id)
            await session.commit()

    async def on_mission_finished(event: DomainEvent) -> None:
        if event.user_id is None:
            return
        from app.db.session import SessionFactory

        slug = event.payload.get("definition_slug")
        async with SessionFactory() as session:
            service = await _service(session)
            if slug:
                await service.record_finish(user_id=event.user_id, slug=str(slug),
                                            ending_id=event.payload.get("ending_id"))
            await service.bump_streak(user_id=event.user_id)
            await session.commit()

    bus.subscribe("mission.started", on_mission_started)
    bus.subscribe("question.answered", on_question_answered)
    bus.subscribe("mission.finished", on_mission_finished)
