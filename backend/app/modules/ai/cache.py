"""Fast cache layer (Redis, best-effort). The durable cache is the database:
completed responses are looked up by prompt_hash regardless of Redis health,
so caching semantics are deterministic even when Redis is down."""
from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

_PREFIX = "ai:response:"


async def get_cached(prompt_hash: str) -> str | None:
    try:
        from app.core.redis import get_redis

        return await get_redis().get(_PREFIX + prompt_hash)
    except Exception as exc:  # noqa: BLE001 — cache is best-effort
        log.warning("ai_cache_unavailable", op="get", error=str(exc))
        return None


async def set_cached(prompt_hash: str, content: str) -> None:
    try:
        from app.core.redis import get_redis

        await get_redis().set(_PREFIX + prompt_hash, content,
                              ex=get_settings().ai_cache_ttl_seconds)
    except Exception as exc:  # noqa: BLE001
        log.warning("ai_cache_unavailable", op="set", error=str(exc))
