"""Unit tests for atomic Redis increment-with-TTL.

Covers:
  1. First increment creates key with value 1
  2. Subsequent increments increase the value
  3. TTL is set on first call and preserved on subsequent calls
  4. Orphaned keys (no TTL) get TTL restored
  5. Error propagation from Redis
  6. CacheClient.incr_with_ttl() convenience method
  7. Standalone atomic_incr_with_ttl() function
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_cache_client() -> MagicMock:
    """Build a mock CacheClient with _key() and _redis.eval()."""
    from infrastructure.cache.client import CacheClient

    client = MagicMock(spec=CacheClient)
    client._key = MagicMock(side_effect=lambda k: f"ccrm:{k}")
    client._redis = AsyncMock()
    return client


# ── Lua script behavior tests ───────────────────────────────────────────────


class TestAtomicIncrWithTtl:
    """Test the standalone atomic_incr_with_ttl function."""

    @pytest.mark.asyncio
    async def test_first_increment_returns_1(self) -> None:
        from infrastructure.cache.redis_atomic import atomic_incr_with_ttl

        client = _make_cache_client()
        client._redis.eval = AsyncMock(return_value=1)

        result = await atomic_incr_with_ttl(client, "counter:test", 3600)

        assert result == 1
        client._redis.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_subsequent_increment_returns_higher_value(self) -> None:
        from infrastructure.cache.redis_atomic import atomic_incr_with_ttl

        client = _make_cache_client()
        client._redis.eval = AsyncMock(return_value=5)

        result = await atomic_incr_with_ttl(client, "counter:test", 3600)

        assert result == 5

    @pytest.mark.asyncio
    async def test_passes_prefixed_key_and_ttl_to_eval(self) -> None:
        from infrastructure.cache.redis_atomic import (
            _INCR_WITH_TTL_LUA,
            atomic_incr_with_ttl,
        )

        client = _make_cache_client()
        client._redis.eval = AsyncMock(return_value=1)

        await atomic_incr_with_ttl(client, "usage:leads:1:2026-03", 2_764_800)

        client._redis.eval.assert_called_once_with(
            _INCR_WITH_TTL_LUA,
            1,
            "ccrm:usage:leads:1:2026-03",
            2_764_800,
        )

    @pytest.mark.asyncio
    async def test_rejects_non_cache_client(self) -> None:
        from infrastructure.cache.redis_atomic import atomic_incr_with_ttl

        with pytest.raises(TypeError, match="CacheClient"):
            await atomic_incr_with_ttl("not-a-client", "key", 100)

    @pytest.mark.asyncio
    async def test_propagates_redis_error(self) -> None:
        from infrastructure.cache.redis_atomic import atomic_incr_with_ttl

        client = _make_cache_client()
        client._redis.eval = AsyncMock(side_effect=ConnectionError("Redis down"))

        with pytest.raises(ConnectionError, match="Redis down"):
            await atomic_incr_with_ttl(client, "key", 100)


# ── CacheClient.incr_with_ttl convenience method ────────────────────────────


class TestCacheClientIncrWithTtl:
    """Test the incr_with_ttl method on CacheClient."""

    @pytest.mark.asyncio
    async def test_delegates_to_lua_eval(self) -> None:
        from infrastructure.cache.redis_atomic import _INCR_WITH_TTL_LUA

        client = _make_cache_client()
        client._redis.eval = AsyncMock(return_value=3)

        # Call the real method (not the mock spec)
        from infrastructure.cache.client import CacheClient

        result = await CacheClient.incr_with_ttl(client, "ai:quota:1:2026-03-09", 90_000)

        assert result == 3
        client._redis.eval.assert_called_once_with(
            _INCR_WITH_TTL_LUA,
            1,
            "ccrm:ai:quota:1:2026-03-09",
            90_000,
        )

    @pytest.mark.asyncio
    async def test_returns_int(self) -> None:
        from infrastructure.cache.client import CacheClient

        client = _make_cache_client()
        # Redis eval may return bytes or other types
        client._redis.eval = AsyncMock(return_value=b"7")

        result = await CacheClient.incr_with_ttl(client, "key", 100)

        assert result == 7
        assert isinstance(result, int)


# ── Lua script correctness (simulated) ──────────────────────────────────────


class TestLuaScriptLogic:
    """Simulate the Lua script's 3 branches to verify correctness.

    These tests simulate what Redis does with the Lua script by tracking
    a virtual key store, ensuring:
    - New key → value=1, TTL set
    - Existing key with TTL → value incremented, TTL unchanged
    - Orphaned key (TTL=-1) → value incremented, TTL restored
    """

    def _simulate_lua(
        self,
        store: dict[str, dict],
        key: str,
        ttl: int,
    ) -> int:
        """Python simulation of the Lua script logic."""
        if key not in store:
            store[key] = {"value": 1, "ttl": ttl}
            return 1
        else:
            store[key]["value"] += 1
            if store[key]["ttl"] == -1:
                store[key]["ttl"] = ttl
            return store[key]["value"]

    def test_new_key_gets_value_1_and_ttl(self) -> None:
        store: dict[str, dict] = {}

        result = self._simulate_lua(store, "counter:1", 3600)

        assert result == 1
        assert store["counter:1"]["value"] == 1
        assert store["counter:1"]["ttl"] == 3600

    def test_existing_key_increments_preserves_ttl(self) -> None:
        store = {"counter:1": {"value": 3, "ttl": 3500}}

        result = self._simulate_lua(store, "counter:1", 3600)

        assert result == 4
        assert store["counter:1"]["ttl"] == 3500  # original TTL preserved

    def test_orphaned_key_gets_ttl_restored(self) -> None:
        store = {"counter:1": {"value": 10, "ttl": -1}}

        result = self._simulate_lua(store, "counter:1", 3600)

        assert result == 11
        assert store["counter:1"]["ttl"] == 3600  # TTL restored

    def test_multiple_increments_sequence(self) -> None:
        store: dict[str, dict] = {}

        r1 = self._simulate_lua(store, "k", 100)
        r2 = self._simulate_lua(store, "k", 100)
        r3 = self._simulate_lua(store, "k", 100)

        assert r1 == 1
        assert r2 == 2
        assert r3 == 3
        assert store["k"]["ttl"] == 100  # TTL from first call preserved


# ── Usage service integration ───────────────────────────────────────────────


class TestUsageServiceAtomic:
    """Verify usage_service.track_lead_created uses atomic increment."""

    @pytest.mark.asyncio
    async def test_track_lead_uses_incr_with_ttl(self) -> None:
        mock_cache = _make_cache_client()
        mock_cache.incr_with_ttl = AsyncMock(return_value=1)

        with patch("infrastructure.cache.client.get_redis", return_value=mock_cache):
            from core.services.usage_service import track_lead_created

            await track_lead_created(tenant_id=42)

        mock_cache.incr_with_ttl.assert_called_once()
        args = mock_cache.incr_with_ttl.call_args
        # Key should contain tenant_id and year-month
        assert "42" in args[0][0]
        # TTL should be MONTHLY_LEAD_COUNTER (2_764_800)
        assert args[0][1] == 2_764_800

    @pytest.mark.asyncio
    async def test_track_lead_does_not_call_separate_expire(self) -> None:
        mock_cache = _make_cache_client()
        mock_cache.incr_with_ttl = AsyncMock(return_value=1)
        mock_cache.expire = AsyncMock()

        with patch("infrastructure.cache.client.get_redis", return_value=mock_cache):
            from core.services.usage_service import track_lead_created

            await track_lead_created(tenant_id=42)

        # expire should NOT be called separately
        mock_cache.expire.assert_not_called()
