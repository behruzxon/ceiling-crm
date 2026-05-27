"""
Unit tests for shared moderation helpers (_moderation.py).

Tests cover the in-memory fallback paths for:
- is_flooding    (flood control sliding window)
- incr_link_violations (link violation counter)
"""

from __future__ import annotations

from unittest.mock import patch

from apps.bot.handlers.group._moderation import (
    _flood_msgs,
    _link_violations,
    incr_link_violations,
    is_flooding,
)

_MOD = "apps.bot.handlers.group._moderation"


# ─────────────────────────────────────────────────────────────────────────────
# Flood control
# ─────────────────────────────────────────────────────────────────────────────


class TestIsFlooding:
    def setup_method(self) -> None:
        _flood_msgs.clear()

    async def test_not_flooding_below_threshold(self) -> None:
        """4 messages in window → not flooding."""
        with patch(f"{_MOD}.get_redis", side_effect=RuntimeError("no redis")):
            for _ in range(4):
                result = await is_flooding(1001, 1)
        assert result is False

    async def test_flooding_above_threshold(self) -> None:
        """6 messages in window → flooding on 6th call."""
        with patch(f"{_MOD}.get_redis", side_effect=RuntimeError("no redis")):
            results = [await is_flooding(1001, 2) for _ in range(6)]
        assert results[-1] is True

    async def test_exactly_at_limit_not_flooding(self) -> None:
        """5 messages (= limit) → not flooding (limit is > 5)."""
        with patch(f"{_MOD}.get_redis", side_effect=RuntimeError("no redis")):
            results = [await is_flooding(1001, 3) for _ in range(5)]
        assert results[-1] is False

    async def test_separate_users_independent(self) -> None:
        """Flood counters are per-user; one user flooding does not affect another."""
        with patch(f"{_MOD}.get_redis", side_effect=RuntimeError("no redis")):
            for _ in range(6):
                await is_flooding(1001, 10)  # user 10 floods
            result_new_user = await is_flooding(1001, 11)  # user 11 has 1 msg
        assert result_new_user is False

    async def test_separate_chats_independent(self) -> None:
        """Flood counters are per-chat; overflow in one chat does not affect another."""
        with patch(f"{_MOD}.get_redis", side_effect=RuntimeError("no redis")):
            for _ in range(6):
                await is_flooding(2001, 20)  # chat 2001 floods
            result_other_chat = await is_flooding(3001, 20)  # chat 3001 is clean
        assert result_other_chat is False


# ─────────────────────────────────────────────────────────────────────────────
# Link violation counter
# ─────────────────────────────────────────────────────────────────────────────


class TestIncrLinkViolations:
    def setup_method(self) -> None:
        _link_violations.clear()

    async def test_first_violation_returns_one(self) -> None:
        with patch(f"{_MOD}.get_redis", side_effect=RuntimeError("no redis")):
            count = await incr_link_violations(2001, 10)
        assert count == 1

    async def test_second_violation_returns_two(self) -> None:
        with patch(f"{_MOD}.get_redis", side_effect=RuntimeError("no redis")):
            await incr_link_violations(2001, 11)
            count = await incr_link_violations(2001, 11)
        assert count == 2

    async def test_different_users_independent(self) -> None:
        with patch(f"{_MOD}.get_redis", side_effect=RuntimeError("no redis")):
            await incr_link_violations(2001, 20)
            count = await incr_link_violations(2001, 21)
        assert count == 1

    async def test_different_chats_independent(self) -> None:
        with patch(f"{_MOD}.get_redis", side_effect=RuntimeError("no redis")):
            await incr_link_violations(3001, 30)
            await incr_link_violations(3001, 30)
            count = await incr_link_violations(4001, 30)
        assert count == 1
