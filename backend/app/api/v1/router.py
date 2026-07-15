"""v1 API composition root.

Modules self-describe their routers; bootstrap mounts them. Adding a module
never means editing another module — only bootstrap.py changes.
"""
from fastapi import APIRouter

from app.api.v1 import health
from app.modules.bootstrap import mount_routers

api_router = APIRouter()
api_router.include_router(health.router)
mount_routers(api_router)
