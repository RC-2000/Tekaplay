"""Fixed-window rate limiting in Redis.

Fail-open by design: if Redis is unreachable the request proceeds and a
warning is logged — availability over strictness for product features.
(Security-critical limits, e.g. login attempts, will use a fail-closed
variant when the hardening slice lands.)
"""
from app.core.errors import RateLimitedError
from app.core.logging import get_logger

log = get_logger(__name__)


async def check_rate_limit(key: str, *, limit: int, window_seconds: int,
                           client=None) -> None:
    """Raise RateLimitedError when `key` exceeds `limit` per window."""
    if limit <= 0:
        return
    if client is None:
        from app.core.redis import get_redis

        client = get_redis()
    redis_key = f"ratelimit:{key}"
    try:
        count = await client.incr(redis_key)
        if count == 1:
            await client.expire(redis_key, window_seconds)
    except Exception as exc:  # noqa: BLE001 — fail open, never fail the request
        log.warning("rate_limit_backend_unavailable", error=str(exc))
        return
    if count > limit:
        raise RateLimitedError(
            "Too many requests — please slow down",
            details={"limit": limit, "window_seconds": window_seconds},
        )
