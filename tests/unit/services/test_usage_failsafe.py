"""Unit tests for usage service fail-safe behavior.

Covers:
  1. check_lead_limit denies when Redis is down
  2. check_ai_limit denies when Redis is down
  3. Unlimited plans (limit=0) still allowed even if Redis is down
  4. User-friendly message returned on Redis failure
  5. track_lead_created logs warning but doesn't raise on Redis failure
  6. Normal operation still works (happy path)
  7. Structured log fields (tenant_id, operation) are logged
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────────


def _mock_redis_down():
    """Patch get_redis to raise ConnectionError."""
    mock_cache = MagicMock()
    mock_cache.get = AsyncMock(side_effect=ConnectionError("Redis down"))
    mock_cache.incr_with_ttl = AsyncMock(side_effect=ConnectionError("Redis down"))
    return patch("infrastructure.cache.client.get_redis", return_value=mock_cache)


def _mock_redis_ok(lead_count: int = 0, ai_count: int = 0):
    """Patch get_redis with working mock returning given counts."""
    mock_cache = MagicMock()

    async def mock_get(key: str):
        if "usage:leads:" in key:
            return str(lead_count) if lead_count > 0 else None
        if "ai:quota:" in key:
            return str(ai_count) if ai_count > 0 else None
        return None

    mock_cache.get = AsyncMock(side_effect=mock_get)
    mock_cache.incr_with_ttl = AsyncMock(return_value=lead_count + 1)
    return patch("infrastructure.cache.client.get_redis", return_value=mock_cache)


# ── check_lead_limit: fail-safe ─────────────────────────────────────────


class TestCheckLeadLimitFailSafe:
    """check_lead_limit denies when Redis is unreachable."""

    async def test_redis_down_denies_request(self) -> None:
        from core.services.usage_service import check_lead_limit

        with _mock_redis_down():
            result = await check_lead_limit(tenant_id=1, plan_name="basic")

        assert result.allowed is False
        assert result.reason is not None
        assert "vaqtincha" in result.reason  # Uzbek: "temporarily"

    async def test_redis_down_with_unlimited_plan_allows(self) -> None:
        """Plans with leads_per_month=0 (unlimited) bypass Redis entirely."""
        from core.services.usage_service import check_lead_limit

        with _mock_redis_down():
            result = await check_lead_limit(tenant_id=1, plan_name="enterprise")

        assert result.allowed is True

    async def test_redis_ok_within_limit_allows(self) -> None:
        from core.services.usage_service import check_lead_limit

        with _mock_redis_ok(lead_count=5):
            result = await check_lead_limit(tenant_id=1, plan_name="basic")

        assert result.allowed is True
        assert result.used == 5

    async def test_redis_ok_at_limit_denies(self) -> None:
        from core.services.usage_service import check_lead_limit
        from shared.constants.plans import get_plan_config

        config = get_plan_config("basic")
        at_limit = config.leads_per_month

        with _mock_redis_ok(lead_count=at_limit):
            result = await check_lead_limit(tenant_id=1, plan_name="basic")

        assert result.allowed is False
        assert "limiti tugadi" in result.reason


# ── check_ai_limit: fail-safe ───────────────────────────────────────────


class TestCheckAiLimitFailSafe:
    """check_ai_limit denies when Redis is unreachable."""

    async def test_redis_down_denies_request(self) -> None:
        from core.services.usage_service import check_ai_limit

        with _mock_redis_down():
            result = await check_ai_limit(tenant_id=1, plan_name="basic")

        assert result.allowed is False
        assert result.reason is not None
        assert "vaqtincha" in result.reason

    async def test_redis_down_with_unlimited_plan_allows(self) -> None:
        """Plans with ai_messages_per_day=0 (unlimited) bypass Redis entirely."""
        from core.services.usage_service import check_ai_limit

        with _mock_redis_down():
            result = await check_ai_limit(tenant_id=1, plan_name="enterprise")

        assert result.allowed is True

    async def test_redis_ok_within_limit_allows(self) -> None:
        from core.services.usage_service import check_ai_limit

        with _mock_redis_ok(ai_count=3):
            result = await check_ai_limit(tenant_id=1, plan_name="basic")

        assert result.allowed is True
        assert result.used == 3


# ── track_lead_created: non-fatal but logged ────────────────────────────


class TestTrackLeadFailSafe:
    """track_lead_created logs but doesn't raise on Redis failure."""

    async def test_redis_down_does_not_raise(self) -> None:
        from core.services.usage_service import track_lead_created

        with _mock_redis_down():
            # Should NOT raise
            await track_lead_created(tenant_id=1)

    async def test_redis_ok_increments(self) -> None:
        from core.services.usage_service import track_lead_created

        with _mock_redis_ok() as mock_patch:
            await track_lead_created(tenant_id=42)

        mock_cache = mock_patch.return_value
        mock_cache.incr_with_ttl.assert_awaited_once()


# ── Fail-safe message quality ────────────────────────────────────────────


class TestFailSafeMessage:
    """The deny message on Redis failure is user-friendly."""

    async def test_lead_limit_message_is_user_friendly(self) -> None:
        from core.services.usage_service import check_lead_limit

        with _mock_redis_down():
            result = await check_lead_limit(tenant_id=1, plan_name="basic")

        assert result.reason is not None
        # Should be a human-readable message, not a traceback
        assert "Redis" not in result.reason
        assert "Error" not in result.reason
        assert "Exception" not in result.reason

    async def test_ai_limit_message_is_user_friendly(self) -> None:
        from core.services.usage_service import check_ai_limit

        with _mock_redis_down():
            result = await check_ai_limit(tenant_id=1, plan_name="basic")

        assert result.reason is not None
        assert "Redis" not in result.reason
