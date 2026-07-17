"""Event bus — the backbone of the platform.

Every significant business action publishes a DomainEvent. Analytics,
achievements, adaptive learning, and notifications are all subscribers; none
of them are called directly by the code that does the work. That decoupling is
what lets the Game Runtime stay generic.

The default bus is in-process (fine for a modular monolith). The EventBus
protocol is deliberately tiny so a Redis Streams or SQS-backed implementation
can replace it without touching publishers or subscribers — see
docs/ARCHITECTURE.md, "Event-driven core".
"""
import asyncio
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.core.logging import get_logger

log = get_logger(__name__)


class DomainEvent(BaseModel):
    """Envelope for all platform events.

    `name` is dot-namespaced and stable: "mission.started", "question.answered",
    "xp.awarded", "achievement.unlocked", "purchase.completed", ...
    The full catalog lives in docs/ARCHITECTURE.md and grows additively — event
    names and payload fields are never renamed or removed, only added.
    """

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    user_id: uuid.UUID | None = None
    correlation_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


Handler = Callable[[DomainEvent], Awaitable[None]]


class EventBus(Protocol):
    def subscribe(self, event_name: str, handler: Handler) -> None: ...
    async def publish(self, event: DomainEvent) -> None: ...


class InProcessEventBus:
    """Async in-process pub/sub. Handler failures are isolated and logged —
    a broken subscriber must never break the business action that emitted."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: Handler) -> None:
        self._handlers[event_name].append(handler)

    async def publish(self, event: DomainEvent) -> None:
        handlers = self._handlers.get(event.name, []) + self._handlers.get("*", [])
        if not handlers:
            return
        results = await asyncio.gather(
            *(h(event) for h in handlers), return_exceptions=True
        )
        for handler, result in zip(handlers, results, strict=True):
            if isinstance(result, Exception):
                log.error(
                    "event_handler_failed",
                    event=event.name,
                    handler=getattr(handler, "__qualname__", str(handler)),
                    error=str(result),
                )


bus: EventBus = InProcessEventBus()


class BufferedEventBus:
    """Transactional wrapper: publish() buffers; flush() delivers to the inner
    bus. Request handling wires one of these per request and flushes only
    after the DB transaction commits — so subscribers never observe events for
    state that was rolled back, and never race the emitting transaction.
    (Precursor of the durable outbox; see docs/ARCHITECTURE.md.)"""

    def __init__(self, inner: EventBus) -> None:
        self._inner = inner
        self._buffer: list[DomainEvent] = []

    def subscribe(self, event_name: str, handler: Handler) -> None:
        self._inner.subscribe(event_name, handler)

    async def publish(self, event: DomainEvent) -> None:
        self._buffer.append(event)

    async def flush(self) -> None:
        buffered, self._buffer = self._buffer, []
        for event in buffered:
            await self._inner.publish(event)

    def discard(self) -> None:
        self._buffer.clear()
