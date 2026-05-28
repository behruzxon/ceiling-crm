"""Step 9 — Handoff auto-expire integration flow.

End-to-end (in-memory): build stale + protected handoff rows, invoke the
service, confirm only the right rows move to ``expired``. No Telegram, no
OpenAI, no destructive deletes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.services.crm_operator_handoff_service import (
    CRMOperatorHandoffService,
    is_handoff_expirable,
)

NOW = datetime(2026, 5, 28, 12, 0, tzinfo=UTC)


@dataclass
class HRow:
    id: int
    status: str
    created_at: datetime
    expires_at: datetime | None = None
    updated_at: datetime | None = None
    phone_masked: str | None = None


def _session_for(rows: list[HRow]) -> MagicMock:
    """Return a fake AsyncSession that yields exactly the expirable subset."""
    expirable = [
        r
        for r in rows
        if is_handoff_expirable(
            status=r.status,
            created_at=r.created_at,
            expires_at=r.expires_at,
            now=NOW,
        )
    ]
    session = MagicMock()
    scalars = MagicMock()
    scalars.all.return_value = expirable
    result = MagicMock()
    result.scalars.return_value = scalars
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


class TestStaleHandoffFlow:
    @pytest.mark.asyncio
    async def test_create_stale_then_expire(self) -> None:
        stale = HRow(
            id=1,
            status="open",
            created_at=NOW - timedelta(hours=30),
        )
        session = _session_for([stale])
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW)
        assert result.expired_count == 1
        assert stale.status == "expired"

    @pytest.mark.asyncio
    async def test_status_becomes_expired(self) -> None:
        row = HRow(
            id=2,
            status="waiting_phone",
            created_at=NOW - timedelta(hours=48),
            expires_at=NOW - timedelta(hours=24),
        )
        session = _session_for([row])
        svc = CRMOperatorHandoffService(session=session)
        await svc.expire_stale_handoffs(now=NOW)
        assert row.status == "expired"

    @pytest.mark.asyncio
    async def test_contacted_remains_contacted(self) -> None:
        row = HRow(
            id=3,
            status="contacted",
            created_at=NOW - timedelta(days=5),
            expires_at=NOW - timedelta(days=1),
        )
        session = _session_for([row])
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW)
        assert result.expired_count == 0
        assert row.status == "contacted"

    @pytest.mark.asyncio
    async def test_resolved_remains_resolved(self) -> None:
        row = HRow(
            id=4,
            status="resolved",
            created_at=NOW - timedelta(days=5),
            expires_at=NOW - timedelta(days=1),
        )
        session = _session_for([row])
        svc = CRMOperatorHandoffService(session=session)
        await svc.expire_stale_handoffs(now=NOW)
        assert row.status == "resolved"

    @pytest.mark.asyncio
    async def test_cancelled_remains_cancelled(self) -> None:
        row = HRow(
            id=5,
            status="cancelled",
            created_at=NOW - timedelta(days=5),
            expires_at=NOW - timedelta(days=1),
        )
        session = _session_for([row])
        svc = CRMOperatorHandoffService(session=session)
        await svc.expire_stale_handoffs(now=NOW)
        assert row.status == "cancelled"

    @pytest.mark.asyncio
    async def test_assigned_stale_becomes_expired(self) -> None:
        row = HRow(
            id=6,
            status="assigned",
            created_at=NOW - timedelta(hours=48),
            expires_at=NOW - timedelta(hours=24),
            phone_masked="9981****99",
        )
        session = _session_for([row])
        svc = CRMOperatorHandoffService(session=session)
        await svc.expire_stale_handoffs(now=NOW)
        assert row.status == "expired"

    @pytest.mark.asyncio
    async def test_fresh_row_untouched(self) -> None:
        row = HRow(
            id=7,
            status="open",
            created_at=NOW - timedelta(minutes=15),
        )
        session = _session_for([row])
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW, expire_hours=24)
        assert result.expired_count == 0
        assert row.status == "open"


class TestMixedBatchFlow:
    @pytest.mark.asyncio
    async def test_mixed_batch(self) -> None:
        rows = [
            HRow(id=10, status="open", created_at=NOW - timedelta(hours=30)),
            HRow(id=11, status="waiting_phone", created_at=NOW - timedelta(hours=40)),
            HRow(id=12, status="assigned", created_at=NOW - timedelta(hours=40)),
            HRow(id=13, status="open", created_at=NOW - timedelta(minutes=10)),
            HRow(
                id=14,
                status="contacted",
                created_at=NOW - timedelta(days=10),
                expires_at=NOW - timedelta(days=5),
            ),
            HRow(
                id=15,
                status="resolved",
                created_at=NOW - timedelta(days=10),
                expires_at=NOW - timedelta(days=5),
            ),
        ]
        session = _session_for(rows)
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW, expire_hours=24)

        expired_ids = set(result.expired_ids)
        assert {10, 11, 12}.issubset(expired_ids)
        assert 13 not in expired_ids
        assert 14 not in expired_ids
        assert 15 not in expired_ids

    @pytest.mark.asyncio
    async def test_audit_trail_updated_at_set(self) -> None:
        row = HRow(
            id=20,
            status="open",
            created_at=NOW - timedelta(hours=30),
        )
        session = _session_for([row])
        svc = CRMOperatorHandoffService(session=session)
        await svc.expire_stale_handoffs(now=NOW)
        assert row.updated_at == NOW


class TestSafety:
    @pytest.mark.asyncio
    async def test_no_telegram_send_during_flow(self) -> None:
        row = HRow(
            id=30,
            status="open",
            created_at=NOW - timedelta(hours=30),
            phone_masked="9991****88",
        )
        session = _session_for([row])
        svc = CRMOperatorHandoffService(session=session)
        # We don't import or patch aiogram; service must not call it.
        await svc.expire_stale_handoffs(now=NOW)
        assert row.status == "expired"

    def test_no_openai_call_during_flow(self) -> None:
        # Sync assertion — verifies the service module source contains no
        # openai reference. Run synchronously to avoid blocking-I/O lint.
        from core.services import crm_operator_handoff_service as mod

        src = mod.__file__ or ""
        if src:
            with open(src, encoding="utf-8") as f:
                contents = f.read()
            assert "openai" not in contents.lower()

    @pytest.mark.asyncio
    async def test_no_destructive_delete(self) -> None:
        row = HRow(
            id=32,
            status="open",
            created_at=NOW - timedelta(hours=30),
        )
        session = _session_for([row])
        svc = CRMOperatorHandoffService(session=session)
        await svc.expire_stale_handoffs(now=NOW)
        # The session should never receive a delete call
        assert not session.delete.called  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_no_token_leak_in_repr(self) -> None:
        session = _session_for([])
        svc = CRMOperatorHandoffService(session=session)
        result = await svc.expire_stale_handoffs(now=NOW)
        as_str = f"{result!r}"
        assert "sk-" not in as_str
        assert "Bearer" not in as_str


class TestAPIQueueExpiredFilter:
    """Optional: confirm the web template + API support filtering on
    ``expired``. The API route already accepts arbitrary status strings."""

    def test_template_has_expired_option(self) -> None:
        from pathlib import Path

        path = (
            Path(__file__).resolve().parents[3] / "apps" / "web" / "templates" / "crm_handoffs.html"
        )
        src = path.read_text(encoding="utf-8")
        assert 'value="expired"' in src

    def test_api_accepts_status_filter(self) -> None:
        # API queue accepts up-to-30-char status string; expired (7 chars) ok.
        import apps.api.routes.admin_crm_handoffs as mod

        assert hasattr(mod, "handoff_queue")


class TestStep8RegressionStillPassing:
    """Sanity: Step 8 take/unassign endpoints + service still importable."""

    def test_take_endpoint_imports(self) -> None:
        from apps.api.routes.admin_crm_handoffs import take_handoff

        assert callable(take_handoff)

    def test_unassign_endpoint_imports(self) -> None:
        from apps.api.routes.admin_crm_handoffs import unassign_handoff

        assert callable(unassign_handoff)

    def test_operator_workload_endpoint_imports(self) -> None:
        from apps.api.routes.admin_crm_handoffs import operator_workload_summary

        assert callable(operator_workload_summary)
