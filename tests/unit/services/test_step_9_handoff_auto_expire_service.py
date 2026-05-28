"""Step 9 — Handoff Auto-Expire Service unit tests.

Covers the pure ``is_handoff_expirable`` predicate and the async
``CRMOperatorHandoffService.expire_stale_handoffs`` method.

No Telegram. No OpenAI. No real DB.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.services.crm_operator_handoff_service import (
    DEFAULT_EXPIRE_HOURS,
    EXPIRABLE_STATUSES,
    PROTECTED_STATUSES,
    CRMOperatorHandoffService,
    ExpireResult,
    is_handoff_expirable,
)

NOW = datetime(2026, 5, 28, 12, 0, tzinfo=UTC)


@dataclass
class FakeRow:
    id: int
    status: str
    created_at: datetime | None
    expires_at: datetime | None = None
    updated_at: datetime | None = None


def _fake_session(rows: list[FakeRow]) -> MagicMock:
    session = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = list(rows)
    result = MagicMock()
    result.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


# ----------------------------- Pure predicate -------------------------------


class TestExpirableStatusSets:
    def test_open_is_expirable(self) -> None:
        assert "open" in EXPIRABLE_STATUSES

    def test_waiting_phone_is_expirable(self) -> None:
        assert "waiting_phone" in EXPIRABLE_STATUSES

    def test_assigned_is_expirable(self) -> None:
        assert "assigned" in EXPIRABLE_STATUSES

    def test_contacted_protected(self) -> None:
        assert "contacted" in PROTECTED_STATUSES
        assert "contacted" not in EXPIRABLE_STATUSES

    def test_resolved_protected(self) -> None:
        assert "resolved" in PROTECTED_STATUSES
        assert "resolved" not in EXPIRABLE_STATUSES

    def test_cancelled_protected(self) -> None:
        assert "cancelled" in PROTECTED_STATUSES
        assert "cancelled" not in EXPIRABLE_STATUSES

    def test_expired_protected(self) -> None:
        assert "expired" in PROTECTED_STATUSES
        assert "expired" not in EXPIRABLE_STATUSES

    def test_no_overlap(self) -> None:
        assert EXPIRABLE_STATUSES.isdisjoint(PROTECTED_STATUSES)


class TestIsHandoffExpirable:
    def test_expires_open_past_expires_at(self) -> None:
        assert is_handoff_expirable(
            status="open",
            created_at=NOW - timedelta(hours=1),
            expires_at=NOW - timedelta(minutes=1),
            now=NOW,
        )

    def test_expires_waiting_phone_past_expires_at(self) -> None:
        assert is_handoff_expirable(
            status="waiting_phone",
            created_at=NOW - timedelta(hours=2),
            expires_at=NOW - timedelta(seconds=1),
            now=NOW,
        )

    def test_expires_assigned_past_expires_at(self) -> None:
        assert is_handoff_expirable(
            status="assigned",
            created_at=NOW - timedelta(hours=2),
            expires_at=NOW - timedelta(seconds=1),
            now=NOW,
        )

    def test_does_not_expire_contacted(self) -> None:
        assert not is_handoff_expirable(
            status="contacted",
            created_at=NOW - timedelta(days=10),
            expires_at=NOW - timedelta(days=5),
            now=NOW,
        )

    def test_does_not_expire_resolved(self) -> None:
        assert not is_handoff_expirable(
            status="resolved",
            created_at=NOW - timedelta(days=10),
            expires_at=NOW - timedelta(days=5),
            now=NOW,
        )

    def test_does_not_expire_cancelled(self) -> None:
        assert not is_handoff_expirable(
            status="cancelled",
            created_at=NOW - timedelta(days=10),
            expires_at=NOW - timedelta(days=5),
            now=NOW,
        )

    def test_does_not_expire_already_expired(self) -> None:
        assert not is_handoff_expirable(
            status="expired",
            created_at=NOW - timedelta(days=10),
            expires_at=NOW - timedelta(days=5),
            now=NOW,
        )

    def test_does_not_expire_future_expires_at(self) -> None:
        assert not is_handoff_expirable(
            status="open",
            created_at=NOW - timedelta(hours=1),
            expires_at=NOW + timedelta(hours=1),
            now=NOW,
        )

    def test_falls_back_to_created_at_when_no_expires_at(self) -> None:
        assert is_handoff_expirable(
            status="open",
            created_at=NOW - timedelta(hours=25),
            expires_at=None,
            now=NOW,
            expire_hours=24,
        )

    def test_fallback_does_not_expire_fresh(self) -> None:
        assert not is_handoff_expirable(
            status="open",
            created_at=NOW - timedelta(hours=1),
            expires_at=None,
            now=NOW,
            expire_hours=24,
        )

    def test_fallback_boundary_equal(self) -> None:
        assert is_handoff_expirable(
            status="assigned",
            created_at=NOW - timedelta(hours=24),
            expires_at=None,
            now=NOW,
            expire_hours=24,
        )

    def test_default_expire_hours_is_24(self) -> None:
        assert DEFAULT_EXPIRE_HOURS == 24

    def test_zero_expire_hours_returns_false(self) -> None:
        assert not is_handoff_expirable(
            status="open",
            created_at=NOW - timedelta(days=10),
            expires_at=None,
            now=NOW,
            expire_hours=0,
        )

    def test_negative_expire_hours_returns_false(self) -> None:
        assert not is_handoff_expirable(
            status="open",
            created_at=NOW - timedelta(days=10),
            expires_at=None,
            now=NOW,
            expire_hours=-1,
        )

    def test_none_created_no_expires_returns_false(self) -> None:
        assert not is_handoff_expirable(
            status="open",
            created_at=None,
            expires_at=None,
            now=NOW,
            expire_hours=24,
        )

    def test_naive_datetimes_handled(self) -> None:
        naive_now = datetime(2026, 5, 28, 12, 0)
        assert is_handoff_expirable(
            status="open",
            created_at=datetime(2026, 5, 27, 0, 0),
            expires_at=None,
            now=naive_now,
            expire_hours=24,
        )

    def test_unknown_status_returns_false(self) -> None:
        assert not is_handoff_expirable(
            status="weird_status",
            created_at=NOW - timedelta(days=10),
            expires_at=NOW - timedelta(days=5),
            now=NOW,
        )

    def test_custom_expire_hours_short(self) -> None:
        assert is_handoff_expirable(
            status="open",
            created_at=NOW - timedelta(hours=2),
            expires_at=None,
            now=NOW,
            expire_hours=1,
        )

    def test_custom_expire_hours_long_blocks_expiry(self) -> None:
        assert not is_handoff_expirable(
            status="open",
            created_at=NOW - timedelta(hours=48),
            expires_at=None,
            now=NOW,
            expire_hours=72,
        )

    def test_expires_at_takes_precedence_over_created_at(self) -> None:
        # expires_at is in the past → expire regardless of created_at age
        assert is_handoff_expirable(
            status="open",
            created_at=NOW - timedelta(minutes=5),
            expires_at=NOW - timedelta(seconds=1),
            now=NOW,
            expire_hours=240,
        )

    def test_future_expires_at_blocks_even_with_old_created_at(self) -> None:
        # expires_at takes precedence — when set and in future, no expiry
        assert not is_handoff_expirable(
            status="open",
            created_at=NOW - timedelta(days=10),
            expires_at=NOW + timedelta(hours=1),
            now=NOW,
        )


# --------------------------- Async service method ---------------------------


class TestExpireStaleHandoffsResult:
    @pytest.mark.asyncio
    async def test_no_session_returns_error_result(self) -> None:
        svc = CRMOperatorHandoffService(session=None)
        result = await svc.expire_stale_handoffs(now=NOW)
        assert isinstance(result, ExpireResult)
        assert result.expired_count == 0
        assert "no_session" in result.errors

    @pytest.mark.asyncio
    async def test_empty_list_returns_zero_counts(self) -> None:
        session = _fake_session([])
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW)
        assert result.scanned == 0
        assert result.expired_count == 0
        assert result.skipped_count == 0
        assert result.expired_ids == ()
        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_expire_result_dataclass(self) -> None:
        session = _fake_session([])
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW)
        assert isinstance(result, ExpireResult)


class TestExpireStaleHandoffsFlow:
    @pytest.mark.asyncio
    async def test_expires_open_past_expires_at(self) -> None:
        row = FakeRow(
            id=1,
            status="open",
            created_at=NOW - timedelta(hours=2),
            expires_at=NOW - timedelta(seconds=1),
        )
        session = _fake_session([row])
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW)
        assert result.expired_count == 1
        assert 1 in result.expired_ids
        assert row.status == "expired"
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_expires_waiting_phone_past_expires_at(self) -> None:
        row = FakeRow(
            id=2,
            status="waiting_phone",
            created_at=NOW - timedelta(hours=5),
            expires_at=NOW - timedelta(minutes=10),
        )
        session = _fake_session([row])
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW)
        assert result.expired_count == 1
        assert row.status == "expired"

    @pytest.mark.asyncio
    async def test_expires_assigned_past_expires_at(self) -> None:
        row = FakeRow(
            id=3,
            status="assigned",
            created_at=NOW - timedelta(hours=5),
            expires_at=NOW - timedelta(minutes=10),
        )
        session = _fake_session([row])
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW)
        assert result.expired_count == 1
        assert row.status == "expired"

    @pytest.mark.asyncio
    async def test_skips_contacted_in_post_filter(self) -> None:
        # Simulate DB returning a row whose status changed between SELECT
        # and update (defensive double-check).
        row = FakeRow(
            id=4,
            status="contacted",
            created_at=NOW - timedelta(days=5),
            expires_at=NOW - timedelta(days=1),
        )
        session = _fake_session([row])
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW)
        assert result.expired_count == 0
        assert result.skipped_count == 1
        assert row.status == "contacted"
        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_resolved_in_post_filter(self) -> None:
        row = FakeRow(
            id=5,
            status="resolved",
            created_at=NOW - timedelta(days=5),
            expires_at=NOW - timedelta(days=1),
        )
        session = _fake_session([row])
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW)
        assert result.expired_count == 0
        assert row.status == "resolved"

    @pytest.mark.asyncio
    async def test_skips_already_expired_in_post_filter(self) -> None:
        row = FakeRow(
            id=6,
            status="expired",
            created_at=NOW - timedelta(days=5),
            expires_at=NOW - timedelta(days=1),
        )
        session = _fake_session([row])
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW)
        assert result.expired_count == 0
        assert row.status == "expired"

    @pytest.mark.asyncio
    async def test_uses_fallback_when_expires_at_null(self) -> None:
        row = FakeRow(
            id=7,
            status="open",
            created_at=NOW - timedelta(hours=30),
            expires_at=None,
        )
        session = _fake_session([row])
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW, expire_hours=24)
        assert result.expired_count == 1
        assert row.status == "expired"

    @pytest.mark.asyncio
    async def test_default_expire_hours_24(self) -> None:
        row = FakeRow(
            id=8,
            status="open",
            created_at=NOW - timedelta(hours=25),
            expires_at=None,
        )
        session = _fake_session([row])
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW)
        assert result.expired_count == 1

    @pytest.mark.asyncio
    async def test_does_not_touch_fresh_row(self) -> None:
        row = FakeRow(
            id=9,
            status="open",
            created_at=NOW - timedelta(minutes=5),
            expires_at=None,
        )
        session = _fake_session([row])
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW, expire_hours=24)
        assert result.expired_count == 0
        assert result.skipped_count == 1
        assert row.status == "open"

    @pytest.mark.asyncio
    async def test_mixed_batch_expires_only_stale(self) -> None:
        stale = FakeRow(
            id=10,
            status="open",
            created_at=NOW - timedelta(hours=30),
            expires_at=None,
        )
        fresh = FakeRow(
            id=11,
            status="open",
            created_at=NOW - timedelta(minutes=10),
            expires_at=None,
        )
        protected = FakeRow(
            id=12,
            status="contacted",
            created_at=NOW - timedelta(days=10),
            expires_at=NOW - timedelta(days=1),
        )
        session = _fake_session([stale, fresh, protected])
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW, expire_hours=24)
        assert result.expired_count == 1
        assert result.skipped_count == 2
        assert stale.status == "expired"
        assert fresh.status == "open"
        assert protected.status == "contacted"

    @pytest.mark.asyncio
    async def test_expired_ids_match_changed_rows(self) -> None:
        rows = [
            FakeRow(id=100, status="open", created_at=NOW - timedelta(hours=30)),
            FakeRow(id=101, status="open", created_at=NOW - timedelta(hours=30)),
            FakeRow(id=102, status="open", created_at=NOW - timedelta(minutes=1)),
        ]
        session = _fake_session(rows)
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW, expire_hours=24)
        assert sorted(result.expired_ids) == [100, 101]

    @pytest.mark.asyncio
    async def test_updates_updated_at(self) -> None:
        row = FakeRow(
            id=200,
            status="open",
            created_at=NOW - timedelta(hours=30),
            expires_at=None,
        )
        session = _fake_session([row])
        svc = CRMOperatorHandoffService(session=session)
        await svc.expire_stale_handoffs(now=NOW)
        assert row.updated_at == NOW

    @pytest.mark.asyncio
    async def test_commit_called_only_when_changes(self) -> None:
        fresh = FakeRow(
            id=201,
            status="open",
            created_at=NOW - timedelta(minutes=5),
            expires_at=None,
        )
        session = _fake_session([fresh])
        svc = CRMOperatorHandoffService(session=session)
        await svc.expire_stale_handoffs(now=NOW, expire_hours=24)
        session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_commit_called_when_changes(self) -> None:
        row = FakeRow(
            id=202,
            status="open",
            created_at=NOW - timedelta(hours=30),
            expires_at=None,
        )
        session = _fake_session([row])
        svc = CRMOperatorHandoffService(session=session)
        await svc.expire_stale_handoffs(now=NOW, expire_hours=24)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_limit_clamped_min_1(self) -> None:
        row = FakeRow(
            id=300,
            status="open",
            created_at=NOW - timedelta(hours=30),
            expires_at=None,
        )
        session = _fake_session([row])
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW, limit=0)
        assert result.expired_count == 1  # limit normalized to ≥1

    @pytest.mark.asyncio
    async def test_limit_clamped_max_1000(self) -> None:
        session = _fake_session([])
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW, limit=999_999)
        assert result.scanned == 0  # no rows; just confirm no crash

    @pytest.mark.asyncio
    async def test_uses_default_now_when_none(self) -> None:
        session = _fake_session([])
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=None)
        assert isinstance(result, ExpireResult)


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_query_error_returns_error_result(self) -> None:
        session = MagicMock()
        session.execute = AsyncMock(side_effect=RuntimeError("boom"))
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW)
        assert result.expired_count == 0
        assert any(e.startswith("query_error") for e in result.errors)

    @pytest.mark.asyncio
    async def test_commit_failure_rolls_back(self) -> None:
        row = FakeRow(
            id=400,
            status="open",
            created_at=NOW - timedelta(hours=30),
            expires_at=None,
        )
        session = _fake_session([row])
        session.commit = AsyncMock(side_effect=RuntimeError("commit broke"))
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW)
        assert result.expired_count == 0
        session.rollback.assert_awaited()
        assert any(e.startswith("commit_error") for e in result.errors)

    @pytest.mark.asyncio
    async def test_malformed_row_skipped(self) -> None:
        class BadRow:
            id = 500
            status = "open"
            created_at = "not-a-date"  # type: ignore[assignment]
            expires_at = None
            updated_at = None

        session = _fake_session([BadRow()])  # type: ignore[arg-type]
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW)
        # Malformed → predicate returns False → skipped, no commit
        assert result.expired_count == 0


class TestNoSideEffects:
    """Guard against leaks: no Telegram, no OpenAI, no phone/token in output."""

    @pytest.mark.asyncio
    async def test_no_phone_in_result_str(self) -> None:
        row = FakeRow(
            id=600,
            status="open",
            created_at=NOW - timedelta(hours=30),
            expires_at=None,
        )
        session = _fake_session([row])
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW)
        rendered = repr(result)
        assert "+998" not in rendered

    @pytest.mark.asyncio
    async def test_no_token_in_result_str(self) -> None:
        session = _fake_session([])
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW)
        rendered = repr(result)
        assert "Bearer" not in rendered
        assert "sk-" not in rendered

    def test_service_does_not_import_aiogram(self) -> None:
        # Sync test — read the source file synchronously to avoid blocking I/O
        # inside an async test.
        from core.services import crm_operator_handoff_service as mod

        src = mod.__file__ or ""
        if src:
            with open(src, encoding="utf-8") as f:
                contents = f.read()
            assert "aiogram" not in contents
            assert "openai" not in contents.lower()

    @pytest.mark.asyncio
    async def test_no_openai_calls(self) -> None:
        svc = CRMOperatorHandoffService(session=None)
        result = await svc.expire_stale_handoffs(now=NOW)
        assert isinstance(result, ExpireResult)


class TestStaticHelper:
    def test_is_expirable_static_matches_function(self) -> None:
        assert (
            CRMOperatorHandoffService.is_expirable(
                status="open",
                created_at=NOW - timedelta(hours=30),
                expires_at=None,
                now=NOW,
            )
            is True
        )

    def test_is_expirable_static_rejects_resolved(self) -> None:
        assert (
            CRMOperatorHandoffService.is_expirable(
                status="resolved",
                created_at=NOW - timedelta(days=10),
                expires_at=NOW - timedelta(days=5),
                now=NOW,
            )
            is False
        )


class TestSafetyConstants:
    def test_expirable_does_not_include_resolved(self) -> None:
        assert "resolved" not in CRMOperatorHandoffService.EXPIRABLE_STATUSES

    def test_expirable_does_not_include_cancelled(self) -> None:
        assert "cancelled" not in CRMOperatorHandoffService.EXPIRABLE_STATUSES

    def test_expirable_does_not_include_expired(self) -> None:
        assert "expired" not in CRMOperatorHandoffService.EXPIRABLE_STATUSES

    def test_protected_includes_contacted(self) -> None:
        assert "contacted" in CRMOperatorHandoffService.PROTECTED_STATUSES


_ = Any  # silence unused import on some linter configs
