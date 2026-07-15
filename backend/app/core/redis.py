"""Shared async Redis client (cache, rate limits, OAuth state).

Lazy singleton per process. Nothing durable lives only in Redis.
"""
from redis.asyncio import Redis, from_url

from app.core.config import get_settings

_client: Redis | None = None


def get_redis() -> Redis:
    global _client
    if _client is None:
        _client = from_url(get_settings().redis_url, decode_responses=True)
    return _client
