"""Single place where modules attach to the application.

Adding a module = one line in each function here; no module ever edits
another module to integrate.
"""
from fastapi import APIRouter

from app.events.bus import EventBus


def mount_routers(api_router: APIRouter) -> None:
    from app.modules.auth.router import router as auth_router
    from app.modules.content.router import router as content_router
    from app.modules.runtime.router import router as runtime_router
    from app.modules.users.router import router as users_router

    api_router.include_router(auth_router)
    api_router.include_router(users_router)
    api_router.include_router(runtime_router)
    api_router.include_router(content_router)


def wire_event_subscribers(bus: EventBus) -> None:
    from app.modules.auth import events as auth_events

    auth_events.register(bus)
