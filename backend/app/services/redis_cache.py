# backend/app/services/redis_cache.py
from __future__ import annotations

import logging

import redis.asyncio as aioredis

from app.config import Settings

logger = logging.getLogger(__name__)

_cache: RedisCache | None = None


class RedisCache:
    """Async Redis wrapper for caching."""

    def __init__(self, client: aioredis.Redis) -> None:
        self._client = client

    @classmethod
    async def create(cls, settings: Settings) -> RedisCache | None:
        """Try to connect to Redis; return None if unavailable."""
        try:
            client = aioredis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password or None,
                ssl=settings.redis_ssl,
                decode_responses=True,
            )
            await client.ping()
            logger.info(
                "Redis connection established at %s:%s",
                settings.redis_host,
                settings.redis_port,
            )
            return cls(client=client)
        except Exception as exc:
            logger.warning("Redis unavailable — caching disabled: %s", exc)
            return None

    async def get(self, key: str) -> str | None:
        """Get a cached value by key."""
        return await self._client.get(key)

    async def set(self, key: str, value: str, ttl_seconds: int = 300) -> None:
        """Set a cached value with a TTL in seconds."""
        await self._client.set(key, value, ex=ttl_seconds)

    async def delete(self, key: str) -> None:
        """Delete a cached key."""
        await self._client.delete(key)

    async def publish(self, channel: str, message: str) -> None:
        """Publish a message to a Redis pub/sub channel."""
        await self._client.publish(channel, message)

    def pubsub(self) -> aioredis.client.PubSub:
        """Create a dedicated pub/sub connection for long-lived listeners."""
        return self._client.pubsub()

    async def close(self) -> None:
        """Close the Redis connection."""
        await self._client.aclose()


async def init_redis_cache(settings: Settings) -> RedisCache | None:
    """Create and cache the global RedisCache singleton."""
    global _cache
    _cache = await RedisCache.create(settings)
    return _cache


def get_redis_cache() -> RedisCache | None:
    """Return the global RedisCache instance, or None if unavailable."""
    return _cache
