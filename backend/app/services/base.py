"""Service layer conventions.

A service owns one bounded context's business logic. It receives its
dependencies (repositories, event bus, other services' *interfaces*) through
the constructor — never imports concrete infrastructure. Transactions are
scoped by the request session; services flush, the session dependency commits.
"""
from app.events.bus import DomainEvent, EventBus


class BaseService:
    def __init__(self, event_bus: EventBus) -> None:
        self._events = event_bus

    async def emit(self, event: DomainEvent) -> None:
        await self._events.publish(event)
