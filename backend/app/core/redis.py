"""Redis client singleton."""

import redis
import redis.asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()

redis_client: aioredis.Redis | None = None
_sync_redis: redis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global redis_client
    if redis_client is None:
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return redis_client


def get_redis_sync() -> redis.Redis:
    """Synchronous Redis client for Celery tasks."""
    global _sync_redis
    if _sync_redis is None:
        _sync_redis = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _sync_redis


async def close_redis():
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None
