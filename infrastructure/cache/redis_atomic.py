"""
infrastructure.cache.redis_atomic
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Atomic Redis counter operations using Lua scripts.

Prevents the race condition where a crash between INCR and EXPIRE
leaves a key without TTL (persisting forever).

Usage::

    from infrastructure.cache.redis_atomic import atomic_incr_with_ttl

    count = await atomic_incr_with_ttl(cache, "usage:leads:1:2026-03", 2_764_800)
"""
from __future__ import annotations

from shared.logging import get_logger

log = get_logger(__name__)

# ── Lua script: atomic increment with guaranteed TTL ────────────────────────
#
# Behavior:
#   - Key doesn't exist → SET key 1 EX ttl (TTL guaranteed from creation)
#   - Key exists with TTL → INCR only (preserves existing TTL)
#   - Key exists WITHOUT TTL (orphaned) → INCR + restore TTL (self-healing)
#
# This runs atomically in Redis — no crash window between INCR and EXPIRE.

_INCR_WITH_TTL_LUA = """
local key = KEYS[1]
local ttl = tonumber(ARGV[1])

if redis.call("EXISTS", key) == 0 then
    redis.call("SET", key, 1, "EX", ttl)
    return 1
else
    local val = redis.call("INCR", key)
    if redis.call("TTL", key) == -1 then
        redis.call("EXPIRE", key, ttl)
    end
    return val
end
"""


async def atomic_incr_with_ttl(
    cache: object,
    key: str,
    ttl: int,
) -> int:
    """Atomically increment a counter and ensure it has a TTL.

    Args:
        cache: A ``CacheClient`` instance (from ``get_redis()``).
        key: The unprefixed cache key (prefix is added by CacheClient).
        ttl: Time-to-live in seconds for the key.

    Returns:
        The new counter value after increment.

    Raises:
        Exception: If Redis is unreachable (caller should handle).
    """
    from infrastructure.cache.client import CacheClient

    if not isinstance(cache, CacheClient):
        raise TypeError(f"Expected CacheClient, got {type(cache).__name__}")

    prefixed_key = cache._key(key)
    result = await cache._redis.eval(_INCR_WITH_TTL_LUA, 1, prefixed_key, ttl)
    return int(result)
