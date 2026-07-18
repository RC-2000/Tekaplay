"""Celery worker entry for AI processing (routed to the `ai` queue).

Idempotent by construction: process() is a no-op on non-queued requests, so
at-least-once delivery is safe. A request enqueued just before its commit may
not be visible yet — NotFound retries briefly.
"""
import asyncio
import uuid

from app.core.errors import NotFoundError
from app.workers.celery_app import celery


async def _run(request_id: str) -> None:
    from app.db.session import SessionFactory
    from app.events.bus import BufferedEventBus
    from app.events.bus import bus as real_bus
    from app.modules.ai.service import build_ai_service

    buffered = BufferedEventBus(real_bus)
    async with SessionFactory() as session:
        service = build_ai_service(session, buffered)
        await service.process(uuid.UUID(request_id))
        await session.commit()
    await buffered.flush()


@celery.task(
    name="app.modules.ai.tasks.process_ai_request",
    autoretry_for=(NotFoundError,),
    retry_backoff=2,
    retry_kwargs={"max_retries": 5},
    acks_late=True,
)
def process_ai_request(request_id: str) -> None:
    asyncio.run(_run(request_id))
