"""
infrastructure.cache.distributed_lock
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Redis-based distributed lock for scheduler jobs.

Ensures that only one instance of a scheduled job runs at a time across
multiple application processes (horizontal scaling).

Implementation:
  - Uses ``SET key value NX EX ttl`` (atomic set-if-not-exists with expiry)
  - Lock value is a unique token (UUID) to prevent accidental release by
    another instance
  - Lock auto-expires via Redis TTL even if the worker crashes
  - Release uses a Lua script to atomically check token before deleting

Usage:
    from infrastructure.cache.distributed_lock import scheduler_lock

    @scheduler_lock("billing_expiration_check")
    async def check_billing_expirations() -> None:
        ...

    # Or as a context manager:
    async with DistributedLock("my_job", ttl=120) as acquired:
        if acquired:
            ...
"""
from __future__ import annotations

import functools
import uuid
from typing import Any, Callable

from shared.logging import get_logger

log = get_logger(__name__)

# Lua script: release lock only if the value matches our token.
# This prevents Instance A from releasing Instance B's lock.
_RELEASE_LOCK_LUA = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""


class DistributedLock:
    """Redis-based distributed mutex with auto-expiry.

    Args:
        job_id: Unique identifier for the lock (typically the scheduler job ID).
        ttl: Lock expiration in seconds. Must be longer than the maximum
             expected job duration. Defaults to CacheTTL.SCHEDULER_LOCK (300s).
    """

    def __init__(self, job_id: str, ttl: int | None = None) -> None:
        self.job_id = job_id
        self._ttl = ttl
        self._token: str = uuid.uuid4().hex
        self._acquired = False

    @property
    def ttl(self) -> int:
        if self._ttl is not None:
            return self._ttl
        from infrastructure.cache.keys import CacheTTL
        return CacheTTL.SCHEDULER_LOCK

    async def acquire(self) -> bool:
        """Try to acquire the lock. Returns True if acquired, False if held."""
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys

        try:
            cache = get_redis()
            key = CacheKeys.scheduler_lock(self.job_id)
            self._acquired = await cache.set(key, self._token, ttl=self.ttl, nx=True)
            return self._acquired
        except Exception:
            log.warning("scheduler_lock_acquire_failed", job_id=self.job_id)
            return False  # fail closed — don't run if Redis is down

    async def release(self) -> None:
        """Release the lock if we hold it. Uses Lua for atomic check-and-delete."""
        if not self._acquired:
            return
        try:
            from infrastructure.cache.client import get_redis
            from infrastructure.cache.keys import CacheKeys

            cache = get_redis()
            prefixed_key = cache._key(CacheKeys.scheduler_lock(self.job_id))
            await cache._redis.eval(_RELEASE_LOCK_LUA, 1, prefixed_key, self._token)
        except Exception:
            log.warning("scheduler_lock_release_failed", job_id=self.job_id)
        finally:
            self._acquired = False

    async def __aenter__(self) -> bool:
        return await self.acquire()

    async def __aexit__(self, *exc: object) -> None:
        await self.release()


def scheduler_lock(
    job_id: str,
    ttl: int | None = None,
) -> Callable[..., Callable[..., Any]]:
    """Decorator that wraps an async scheduler job with a distributed lock.

    If the lock cannot be acquired (another instance is running the job),
    the function is silently skipped.

    Args:
        job_id: Unique identifier for the lock (use the APScheduler job ID).
        ttl: Lock TTL in seconds. Defaults to CacheTTL.SCHEDULER_LOCK.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            lock = DistributedLock(job_id, ttl=ttl)
            acquired = await lock.acquire()
            if not acquired:
                log.debug(
                    "scheduler_job_skipped_lock_held",
                    job_id=job_id,
                )
                return None
            try:
                return await func(*args, **kwargs)
            finally:
                await lock.release()

        return wrapper

    return decorator
