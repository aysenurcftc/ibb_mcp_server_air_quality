import json
import logging
from typing import Any
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class RedisCache:
    """Async Redis cache manager."""

    def __init__(self, redis_url: str, default_ttl: int = 60):
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        """Initialize the Redis connection."""
        try:
            self._client = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
            )
            await self._client.ping()
            logger.info(f"Redis connection established: {self.redis_url}")
        except Exception as e:
            logger.warning(
                f"Failed to establish Redis connection: {e}. Cache is disabled."
            )
            self._client = None

    async def disconnect(self) -> None:
        """Close the Redis connection."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    async def get(self, key: str) -> Any | None:
        """Read data from the cache. Returns None if not found."""
        if not self._client:
            return None
        try:
            raw = await self._client.get(key)
            if raw:
                logger.debug(f"Cache HIT: {key}")
                return json.loads(raw)
            logger.debug(f"Cache MISS: {key}")
            return None
        except Exception as e:
            logger.warning(f"Cache read error [{key}]: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Write data to the cache."""
        if not self._client:
            return
        try:
            ttl = ttl or self.default_ttl
            await self._client.setex(key, ttl, json.dumps(value, ensure_ascii=False))
            logger.debug(f"Cache SET: {key} (TTL={ttl}s)")
        except Exception as e:
            logger.warning(f"Cache write error [{key}]: {e}")

    async def delete(self, key: str) -> None:
        """Delete data from the cache."""
        if not self._client:
            return
        try:
            await self._client.delete(key)
        except Exception as e:
            logger.warning(f"Cache deletion error [{key}]: {e}")

    def make_key(self, *parts: str) -> str:
        """Generate a standard cache key."""
        return ":".join(["ibb_mcp", *parts])
