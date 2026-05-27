"""
infrastructure.cache.client
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Async Redis client singleton with typed helper methods.

Provides:
- `get_redis()`     — returns the main AsyncRedis connection
- `get_sessions_redis()` — FSM state storage connection (separate DB)
- Standard cache helpers: get/set/delete/exists/expire/incr
- JSON serialisation helpers
- Key namespacing via CacheKey enum (see keys.py)

All keys are prefixed with the app name to avoid collisions in
shared Redis instances.

Usage:
    from infrastructure.cache import get_redis

    redis = await get_redis()
    await redis.set_json("user:42:profile", {"name": "Alisher"}, ttl=3600)
    profile = await redis.get_json("user:42:profile")
"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis
from redis.asyncio import Redis
from redis.asyncio.connection import ConnectionPool

from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Connection pools (module-level singletons)
# ─────────────────────────────────────────────────────────────────────────────

_main_pool: ConnectionPool | None = None
_sessions_pool: ConnectionPool | None = None

APP_KEY_PREFIX = "ccrm:"  # global namespace prefix for all cache keys


def _build_pool(url: str, max_connections: int = 50) -> ConnectionPool:
    return aioredis.ConnectionPool.from_url(
        url,
        max_connections=max_connections,
        decode_responses=True,  # always work with str, not bytes
        socket_keepalive=True,
        socket_connect_timeout=5,
        health_check_interval=30,
    )


def _get_main_pool() -> ConnectionPool:
    global _main_pool
    if _main_pool is None:
        _main_pool = _build_pool(get_settings().redis.url)
        log.info("redis_pool_created", db="main")
    return _main_pool


def _get_sessions_pool() -> ConnectionPool:
    global _sessions_pool
    if _sessions_pool is None:
        _sessions_pool = _build_pool(get_settings().redis.sessions_url)
        log.info("redis_pool_created", db="sessions")
    return _sessions_pool


# ─────────────────────────────────────────────────────────────────────────────
# Extended Redis client with typed helpers
# ─────────────────────────────────────────────────────────────────────────────


class CacheClient:
    """
    Thin wrapper around Redis with:
    - Automatic key prefixing
    - JSON serialisation / deserialisation
    - Retry on transient connection errors
    - Structured logging on errors
    - Type-safe helpers
    """

    _RETRYABLE = (ConnectionError, TimeoutError, OSError)
    _MAX_RETRIES = 3
    _BASE_DELAY = 1.0

    def __init__(self, pool: ConnectionPool, prefix: str = APP_KEY_PREFIX) -> None:
        self._redis: Redis = Redis(connection_pool=pool)
        self._prefix = prefix

    def _key(self, key: str) -> str:
        """Prepend namespace prefix to a raw key."""
        return f"{self._prefix}{key}"

    async def _safe_exec(self, coro_func: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute a Redis coroutine with retry on transient errors."""
        import asyncio as _asyncio

        delay = self._BASE_DELAY
        last_exc: BaseException | None = None
        for attempt in range(1, self._MAX_RETRIES + 2):
            try:
                return await coro_func(*args, **kwargs)
            except self._RETRYABLE as exc:
                last_exc = exc
                if attempt > self._MAX_RETRIES:
                    log.warning(
                        "redis_retry_exhausted",
                        operation=getattr(coro_func, "__name__", "unknown"),
                        attempts=attempt,
                        error=str(exc),
                    )
                    raise
                log.info(
                    "redis_retry",
                    operation=getattr(coro_func, "__name__", "unknown"),
                    attempt=attempt,
                    delay=delay,
                    error=str(exc),
                )
                await _asyncio.sleep(delay)
                delay *= 2
        raise last_exc  # type: ignore[misc]

    # ── Raw passthrough ───────────────────────────────────────────────────

    async def get(self, key: str) -> str | None:
        return await self._safe_exec(self._redis.get, self._key(key))

    async def set(
        self,
        key: str,
        value: str,
        ttl: int | None = None,
        nx: bool = False,  # SET if Not eXists
    ) -> bool:
        result = await self._safe_exec(self._redis.set, self._key(key), value, ex=ttl, nx=nx)
        return bool(result)

    async def delete(self, *keys: str) -> int:
        prefixed = [self._key(k) for k in keys]
        return await self._safe_exec(self._redis.delete, *prefixed)

    async def exists(self, *keys: str) -> int:
        prefixed = [self._key(k) for k in keys]
        return await self._safe_exec(self._redis.exists, *prefixed)

    async def expire(self, key: str, ttl: int) -> bool:
        return bool(await self._safe_exec(self._redis.expire, self._key(key), ttl))

    async def ttl(self, key: str) -> int:
        return await self._safe_exec(self._redis.ttl, self._key(key))

    async def incr(self, key: str, amount: int = 1) -> int:
        return await self._safe_exec(self._redis.incrby, self._key(key), amount)

    async def keys(self, pattern: str) -> list[str]:
        raw: list[str] = await self._safe_exec(self._redis.keys, self._key(pattern))
        prefix_len = len(self._prefix)
        return [k[prefix_len:] for k in raw]

    # ── JSON helpers ──────────────────────────────────────────────────────

    async def get_json(self, key: str) -> Any | None:
        """Return a deserialised JSON object or None if key absent."""
        raw = await self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            log.warning("cache_json_decode_error", key=key)
            return None

    async def set_json(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
        nx: bool = False,
    ) -> bool:
        """Serialise value to JSON and store."""
        serialised = json.dumps(value, ensure_ascii=False, default=str)
        return await self.set(key, serialised, ttl=ttl, nx=nx)

    # ── Hash helpers ──────────────────────────────────────────────────────

    async def hset(self, key: str, mapping: dict[str, str]) -> int:
        return await self._safe_exec(self._redis.hset, self._key(key), mapping=mapping)  # type: ignore[arg-type]

    async def hget(self, key: str, field: str) -> str | None:
        return await self._safe_exec(self._redis.hget, self._key(key), field)

    async def hgetall(self, key: str) -> dict[str, str]:
        return await self._safe_exec(self._redis.hgetall, self._key(key))

    async def hdel(self, key: str, *fields: str) -> int:
        return await self._safe_exec(self._redis.hdel, self._key(key), *fields)

    # ── Rate limiting (sliding window counter) ────────────────────────────

    async def rate_limit_check(
        self,
        identifier: str,
        window_seconds: int,
        max_requests: int,
    ) -> tuple[bool, int]:
        """
        Sliding window rate limiter.

        Returns:
            (is_allowed: bool, remaining: int)
        """
        key = self._key(f"rl:{identifier}")
        pipe = self._redis.pipeline()
        import time

        now = int(time.time())
        window_start = now - window_seconds
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window_seconds + 1)
        results = await pipe.execute()
        count: int = results[2]
        remaining = max(0, max_requests - count)
        return count <= max_requests, remaining

    # ── Sorted-set helpers (used by CTA inactivity feature) ──────────────

    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        """ZADD wrapper with automatic key prefixing."""
        return await self._safe_exec(self._redis.zadd, self._key(key), mapping)  # type: ignore[arg-type]

    async def zrangebyscore(self, key: str, min_score: float, max_score: float) -> list[str]:
        """Return members with scores in [min_score, max_score]."""
        result: list[str] = await self._safe_exec(
            self._redis.zrangebyscore, self._key(key), min_score, max_score
        )
        return result

    async def zrem(self, key: str, *members: str) -> int:
        """Remove one or more members from a sorted set."""
        return await self._safe_exec(self._redis.zrem, self._key(key), *members)

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def ping(self) -> bool:
        """Check Redis connectivity."""
        try:
            return await self._redis.ping()
        except Exception:
            return False

    async def close(self) -> None:
        await self._redis.aclose()


# ─────────────────────────────────────────────────────────────────────────────
# Singleton accessors
# ─────────────────────────────────────────────────────────────────────────────

_main_client: CacheClient | None = None
_sessions_client: CacheClient | None = None


def get_redis() -> CacheClient:
    """Return the main cache CacheClient singleton."""
    global _main_client
    if _main_client is None:
        _main_client = CacheClient(_get_main_pool())
    return _main_client


def get_sessions_redis() -> CacheClient:
    """
    Return the FSM sessions CacheClient singleton.
    Used by aiogram RedisStorage for state persistence.
    """
    global _sessions_client
    if _sessions_client is None:
        _sessions_client = CacheClient(_get_sessions_pool(), prefix="ccrm:fsm:")
    return _sessions_client


async def connect_redis() -> None:
    """Verify Redis connectivity at startup."""
    client = get_redis()
    if not await client.ping():
        raise RuntimeError("Redis connection failed — check REDIS_HOST/PORT/PASSWORD")
    log.info("redis_connected", url=get_settings().redis.host)


async def disconnect_redis() -> None:
    """Close all Redis connections on shutdown."""
    global _main_client, _sessions_client, _main_pool, _sessions_pool
    if _main_client:
        await _main_client.close()
        _main_client = None
    if _sessions_client:
        await _sessions_client.close()
        _sessions_client = None
    if _main_pool:
        await _main_pool.disconnect()
        _main_pool = None
    if _sessions_pool:
        await _sessions_pool.disconnect()
        _sessions_pool = None
    log.info("redis_disconnected")


async def check_redis_health() -> dict[str, Any]:
    """Health check for monitoring endpoint."""
    client = get_redis()
    try:
        ok = await client.ping()
        info = await client._redis.info("server")
        return {
            "status": "ok" if ok else "error",
            "version": info.get("redis_version"),
            "connected_clients": info.get("connected_clients"),
            "used_memory_human": info.get("used_memory_human"),
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
