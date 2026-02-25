from __future__ import annotations

import redis.asyncio as redis

from app.core.settings import settings


def _record_get(hit: bool) -> None:
    from app.core.cache_metrics import record_cache_get
    record_cache_get(hit)


def _record_set() -> None:
    from app.core.cache_metrics import record_cache_set
    record_cache_set()


class _RedisMetricsWrapper:
    """Wraps Redis client to record cache hits, misses, and sets for /metrics/app."""

    def __init__(self, client: redis.Redis):
        self._client = client

    async def get(self, key: str, *args, **kwargs):
        out = await self._client.get(key, *args, **kwargs)
        _record_get(out is not None)
        return out

    async def set(self, key: str, value: str, *args, **kwargs):
        _record_set()
        return await self._client.set(key, value, *args, **kwargs)

    async def delete(self, *keys, **kwargs):
        return await self._client.delete(*keys, **kwargs)

    async def expire(self, key: str, time: int, **kwargs):
        return await self._client.expire(key, time, **kwargs)

    async def hset(self, key: str, mapping: dict | None = None, **kwargs):
        _record_set()
        return await self._client.hset(key, mapping=mapping, **kwargs)

    async def hgetall(self, key: str, **kwargs):
        out = await self._client.hgetall(key, **kwargs)
        _record_get(bool(out))
        return out


_real_client = redis.from_url(settings.redis_url, decode_responses=True)
redis_client = _RedisMetricsWrapper(_real_client)
