"""Tests for Step AU — Stage4ApprovalReportService."""
from __future__ import annotations

from core.schemas.stage4_approval_report import (
    Stage4ApprovalReport,
    Stage4NoSendSafetyMetrics,
)
from core.services.stage4_approval_report_service import Stage4ApprovalReportService

svc = Stage4ApprovalReportService

def _report(**kw) -> Stage4ApprovalReport:
    defaults = {
        "generated_at": "t", "since": "t", "until": "t", "environment": "test",
        "duration_minutes": 720, "total_proposals": 30, "proposed_count": 5,
        "approved_count": 15, "rejected_count": 5, "expired_count": 3,
        "blocked_count": 2, "executed_count": 0, "pending_count": 5,
        "stale_pending_count": 0,
        "no_send": Stage4NoSendSafetyMetrics(), "health_status": "green",
    }
    defaults.update(kw)
    return Stage4ApprovalReport(**defaults)

class TestPassClean:
    def test_passes(self):
        assert svc.evaluate_pass_fail(_report()).passed is True

class TestFailNoSend:
    def test_executed(self):
        assert not svc.evaluate_pass_fail(
            _report(no_send=Stage4NoSendSafetyMetrics(executed_records_count=1))).passed

    def test_live_sender(self):
        assert not svc.evaluate_pass_fail(
            _report(no_send=Stage4NoSendSafetyMetrics(live_sender_executed=1))).passed

    def test_auto_execute(self):
        assert not svc.evaluate_pass_fail(
            _report(no_send=Stage4NoSendSafetyMetrics(auto_execute_count=1))).passed

    def test_user_dm(self):
        assert not svc.evaluate_pass_fail(
            _report(no_send=Stage4NoSendSafetyMetrics(user_dm_sent_count=1))).passed

    def test_health_red(self):
        assert not svc.evaluate_pass_fail(_report(health_status="red")).passed

    def test_all_zero_passes(self):
        assert svc.evaluate_pass_fail(_report(no_send=Stage4NoSendSafetyMetrics())).passed

class TestWarnings:
    def test_stale_high(self):
        pf = svc.evaluate_pass_fail(_report(stale_pending_count=15))
        assert "stale_pending_high" in pf.warnings

    def test_no_proposals(self):
        pf = svc.evaluate_pass_fail(_report(total_proposals=0))
        assert "no_proposals" in pf.warnings

    def test_high_rejection(self):
        pf = svc.evaluate_pass_fail(_report(total_proposals=20, rejected_count=15))
        assert "high_rejection_rate" in pf.warnings

    def test_high_expiration(self):
        pf = svc.evaluate_pass_fail(_report(total_proposals=20, expired_count=10))
        assert "high_expiration_rate" in pf.warnings

class TestRecommendations:
    def test_fail_rollback(self):
        r = _report(no_send=Stage4NoSendSafetyMetrics(executed_records_count=1))
        recs = svc.build_recommendations(r, svc.evaluate_pass_fail(r))
        assert any("rollback" in rec.lower() for rec in recs)

    def test_no_proposals_continue(self):
        r = _report(total_proposals=0)
        recs = svc.build_recommendations(r, svc.evaluate_pass_fail(r))
        assert any("continue" in rec.lower() for rec in recs)

    def test_enough_proposals_stage5(self):
        r = _report(total_proposals=25)
        recs = svc.build_recommendations(r, svc.evaluate_pass_fail(r))
        assert any("stage 5" in rec.lower() or "live" in rec.lower() for rec in recs)

    def test_high_rejection_inspect(self):
        r = _report(total_proposals=20, rejected_count=15)
        recs = svc.build_recommendations(r, svc.evaluate_pass_fail(r))
        assert any("rejection" in rec.lower() or "inspect" in rec.lower() for rec in recs)

class TestDefaults:
    def test_empty(self):
        r = Stage4ApprovalReport()
        assert r.total_proposals == 0 and r.pass_fail.passed is True

    def test_frozen(self):
        import pytest
        with pytest.raises(AttributeError):
            Stage4ApprovalReport().health_status = "red"  # type: ignore[misc]

class TestDB:
    async def test_empty_db(self):
        from datetime import UTC, datetime, timedelta
        from unittest.mock import AsyncMock, MagicMock
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar=MagicMock(return_value=0), all=MagicMock(return_value=[])))
        now = datetime.now(UTC)
        r = await Stage4ApprovalReportService(session).build_report(now - timedelta(hours=1), now)
        assert r.total_proposals == 0 and r.pass_fail.passed is True

    async def test_db_error(self):
        from datetime import UTC, datetime, timedelta
        from unittest.mock import AsyncMock
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=Exception("DB"))
        now = datetime.now(UTC)
        r = await Stage4ApprovalReportService(session).build_report(now - timedelta(hours=1), now)
        assert r.total_proposals == 0

    async def test_generated_at(self):
        from datetime import UTC, datetime, timedelta
        from unittest.mock import AsyncMock, MagicMock
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar=MagicMock(return_value=0), all=MagicMock(return_value=[])))
        now = datetime.now(UTC)
        r = await Stage4ApprovalReportService(session).build_report(now - timedelta(hours=2), now)
        assert r.generated_at != "" and r.duration_minutes == 120

class TestNoSecrets:
    def test_clean(self):
        from dataclasses import asdict
        assert "sk-" not in str(asdict(Stage4ApprovalReport()))
