"""Liveness and readiness endpoints (Kubernetes/ECS-compatible semantics).

/health/live  — process is up (never touches dependencies)
/health/ready — dependencies reachable (DB, Redis); load balancers gate on this
"""
from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import SessionFactory

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def readiness() -> dict[str, str]:
    async with SessionFactory() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ready"}
