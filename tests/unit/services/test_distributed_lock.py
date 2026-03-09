"""Tests for distributed scheduler locking.

Verifies:
  1. Lock acquisition via Redis SET NX EX
  2. Second instance is skipped when lock is held
  3. Lock is released after job completes
  4. Lock auto-expires (crash safety) via TTL
  5. Decorator skips execution when lock is held
  6. Release uses token comparison (no accidental release)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from infrastructure.cache.distributed_lock import DistributedLock, scheduler_lock


# ── Helpers ─────────────────────────────────────────────────────────────────


def _mock_cache(*, set_returns: bool = True) -> MagicMock:
    """Build a mock CacheClient."""
    cache = MagicMock()
    cache.set = AsyncMock(return_value=set_returns)
    cache._key = lambda k: f"ccrm:{k}"
    cache._redis = MagicMock()
    cache._redis.eval = AsyncMock(return_value=1)
    return cache


# ── DistributedLock unit tests ──────────────────────────────────────────────


class TestDistributedLockAcquire:
    """Lock acquisition tests."""

    @pytest.mark.asyncio
    async def test_acquire_succeeds_when_key_not_exists(self) -> None:
        """SET NX returns True → lock acquired."""
        cache = _mock_cache(set_returns=True)
        with patch("infrastructure.cache.client.get_redis", return_value=cache):
            lock = DistributedLock("test_job", ttl=60)
            result = await lock.acquire()

        assert result is True
        assert lock._acquired is True
        cache.set.assert_awaited_once_with(
            "scheduler:lock:test_job", lock._token, ttl=60, nx=True
        )

    @pytest.mark.asyncio
    async def test_acquire_fails_when_key_exists(self) -> None:
        """SET NX returns False → lock NOT acquired (another instance holds it)."""
        cache = _mock_cache(set_returns=False)
        with patch("infrastructure.cache.client.get_redis", return_value=cache):
            lock = DistributedLock("test_job", ttl=60)
            result = await lock.acquire()

        assert result is False
        assert lock._acquired is False

    @pytest.mark.asyncio
    async def test_acquire_fails_closed_on_redis_error(self) -> None:
        """Redis exception → fail closed (don't run)."""
        cache = _mock_cache()
        cache.set = AsyncMock(side_effect=ConnectionError("Redis down"))
        with patch("infrastructure.cache.client.get_redis", return_value=cache):
            lock = DistributedLock("test_job", ttl=60)
            result = await lock.acquire()

        assert result is False


class TestDistributedLockRelease:
    """Lock release tests."""

    @pytest.mark.asyncio
    async def test_release_calls_lua_with_token(self) -> None:
        """Release uses Lua script to atomically check token before delete."""
        cache = _mock_cache(set_returns=True)
        with patch("infrastructure.cache.client.get_redis", return_value=cache):
            lock = DistributedLock("test_job", ttl=60)
            await lock.acquire()
            await lock.release()

        cache._redis.eval.assert_awaited_once()
        call_args = cache._redis.eval.call_args
        assert call_args.args[1] == 1  # numkeys
        assert "ccrm:scheduler:lock:test_job" in call_args.args[2]
        assert call_args.args[3] == lock._token

    @pytest.mark.asyncio
    async def test_release_noop_when_not_acquired(self) -> None:
        """Release does nothing if lock was never acquired."""
        cache = _mock_cache(set_returns=False)
        with patch("infrastructure.cache.client.get_redis", return_value=cache):
            lock = DistributedLock("test_job", ttl=60)
            await lock.acquire()  # fails
            await lock.release()

        cache._redis.eval.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_release_clears_acquired_flag(self) -> None:
        """After release, _acquired is False."""
        cache = _mock_cache(set_returns=True)
        with patch("infrastructure.cache.client.get_redis", return_value=cache):
            lock = DistributedLock("test_job", ttl=60)
            await lock.acquire()
            assert lock._acquired is True
            await lock.release()
            assert lock._acquired is False


class TestDistributedLockContextManager:
    """Async context manager tests."""

    @pytest.mark.asyncio
    async def test_context_manager_acquires_and_releases(self) -> None:
        """Context manager acquires on enter, releases on exit."""
        cache = _mock_cache(set_returns=True)
        with patch("infrastructure.cache.client.get_redis", return_value=cache):
            lock = DistributedLock("test_job", ttl=60)
            async with lock as acquired:
                assert acquired is True
                assert lock._acquired is True

        assert lock._acquired is False  # released

    @pytest.mark.asyncio
    async def test_context_manager_releases_on_exception(self) -> None:
        """Lock is released even if the body raises."""
        cache = _mock_cache(set_returns=True)
        with patch("infrastructure.cache.client.get_redis", return_value=cache):
            lock = DistributedLock("test_job", ttl=60)
            with pytest.raises(ValueError, match="boom"):
                async with lock:
                    raise ValueError("boom")

        assert lock._acquired is False  # released despite exception


class TestDistributedLockTTL:
    """TTL / auto-expiry tests."""

    def test_default_ttl_from_cache_ttl(self) -> None:
        """When no ttl is provided, uses CacheTTL.SCHEDULER_LOCK."""
        lock = DistributedLock("test_job")
        assert lock.ttl == 300

    def test_custom_ttl_override(self) -> None:
        """Custom TTL is used when provided."""
        lock = DistributedLock("test_job", ttl=120)
        assert lock.ttl == 120

    @pytest.mark.asyncio
    async def test_ttl_passed_to_redis_set(self) -> None:
        """TTL is passed to Redis SET command for auto-expiry on crash."""
        cache = _mock_cache(set_returns=True)
        with patch("infrastructure.cache.client.get_redis", return_value=cache):
            lock = DistributedLock("test_job", ttl=120)
            await lock.acquire()

        cache.set.assert_awaited_once_with(
            "scheduler:lock:test_job", lock._token, ttl=120, nx=True
        )


# ── Token safety (prevents accidental release by wrong instance) ────────────


class TestTokenSafety:
    """Verify that each lock instance uses a unique token."""

    def test_unique_tokens(self) -> None:
        """Two lock instances for the same job get different tokens."""
        lock_a = DistributedLock("same_job")
        lock_b = DistributedLock("same_job")
        assert lock_a._token != lock_b._token

    @pytest.mark.asyncio
    async def test_release_sends_own_token(self) -> None:
        """Release sends the acquirer's token, not a generic value."""
        cache = _mock_cache(set_returns=True)
        with patch("infrastructure.cache.client.get_redis", return_value=cache):
            lock = DistributedLock("test_job", ttl=60)
            token_before = lock._token
            await lock.acquire()
            await lock.release()

        call_args = cache._redis.eval.call_args
        assert call_args.args[3] == token_before


# ── Decorator tests ─────────────────────────────────────────────────────────


class TestSchedulerLockDecorator:
    """Tests for the @scheduler_lock decorator."""

    @pytest.mark.asyncio
    async def test_decorator_runs_function_when_acquired(self) -> None:
        """Function executes when lock is acquired."""
        call_log: list[str] = []

        @scheduler_lock("my_job", ttl=60)
        async def my_job() -> str:
            call_log.append("executed")
            return "done"

        cache = _mock_cache(set_returns=True)
        with patch("infrastructure.cache.client.get_redis", return_value=cache):
            result = await my_job()

        assert result == "done"
        assert call_log == ["executed"]

    @pytest.mark.asyncio
    async def test_decorator_skips_when_lock_held(self) -> None:
        """Function is NOT executed when lock is held by another instance."""
        call_log: list[str] = []

        @scheduler_lock("my_job", ttl=60)
        async def my_job() -> str:
            call_log.append("executed")
            return "done"

        cache = _mock_cache(set_returns=False)
        with patch("infrastructure.cache.client.get_redis", return_value=cache):
            result = await my_job()

        assert result is None  # skipped
        assert call_log == []  # never called

    @pytest.mark.asyncio
    async def test_decorator_releases_after_success(self) -> None:
        """Lock is released after function completes successfully."""
        @scheduler_lock("my_job", ttl=60)
        async def my_job() -> None:
            pass

        cache = _mock_cache(set_returns=True)
        with patch("infrastructure.cache.client.get_redis", return_value=cache):
            await my_job()

        # Lua eval called once (for release)
        cache._redis.eval.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_decorator_releases_after_exception(self) -> None:
        """Lock is released even when function raises an exception."""
        @scheduler_lock("my_job", ttl=60)
        async def my_job() -> None:
            raise RuntimeError("job failed")

        cache = _mock_cache(set_returns=True)
        with patch("infrastructure.cache.client.get_redis", return_value=cache):
            with pytest.raises(RuntimeError, match="job failed"):
                await my_job()

        # Lock was still released
        cache._redis.eval.assert_awaited_once()


# ── Concurrent instance simulation ─────────────────────────────────────────


class TestConcurrentInstances:
    """Simulate two scheduler instances trying to run the same job."""

    @pytest.mark.asyncio
    async def test_two_instances_one_wins(self) -> None:
        """Only the first instance to acquire the lock runs the job."""
        execution_log: list[str] = []

        @scheduler_lock("shared_job", ttl=60)
        async def shared_job(instance: str) -> None:
            execution_log.append(instance)

        # Instance A acquires the lock
        cache_a = _mock_cache(set_returns=True)
        with patch("infrastructure.cache.client.get_redis", return_value=cache_a):
            await shared_job("instance_a")

        # Instance B cannot acquire (lock held)
        cache_b = _mock_cache(set_returns=False)
        with patch("infrastructure.cache.client.get_redis", return_value=cache_b):
            await shared_job("instance_b")

        assert execution_log == ["instance_a"]

    @pytest.mark.asyncio
    async def test_second_instance_runs_after_release(self) -> None:
        """After the first instance releases, the second can acquire."""
        execution_log: list[str] = []

        @scheduler_lock("shared_job", ttl=60)
        async def shared_job(instance: str) -> None:
            execution_log.append(instance)

        # Instance A runs and releases
        cache = _mock_cache(set_returns=True)
        with patch("infrastructure.cache.client.get_redis", return_value=cache):
            await shared_job("instance_a")

        # Instance B can now acquire (lock released)
        with patch("infrastructure.cache.client.get_redis", return_value=cache):
            await shared_job("instance_b")

        assert execution_log == ["instance_a", "instance_b"]


# ── CacheKeys integration ──────────────────────────────────────────────────


class TestCacheKeysIntegration:
    """Verify CacheKeys.scheduler_lock key format."""

    def test_scheduler_lock_key_format(self) -> None:
        from infrastructure.cache.keys import CacheKeys
        assert CacheKeys.scheduler_lock("billing_expiration_check") == "scheduler:lock:billing_expiration_check"

    def test_scheduler_lock_ttl(self) -> None:
        from infrastructure.cache.keys import CacheTTL
        assert CacheTTL.SCHEDULER_LOCK == 300
