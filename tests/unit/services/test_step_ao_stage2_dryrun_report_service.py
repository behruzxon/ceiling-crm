"""Tests for Step AO — Stage2DryRunReportService (pure pass/fail logic)."""
from __future__ import annotations

from core.schemas.stage2_dryrun_report import (
    Stage2DryRunReport,
    Stage2NoSendSafetyMetrics,
)
from core.services.stage2_dryrun_report_service import Stage2DryRunReportService

svc = Stage2DryRunReportService


def _report(**kw) -> Stage2DryRunReport:
    defaults = {
        "generated_at": "2026-05-26T12:00:00", "since": "2026-05-26T00:00:00",
        "until": "2026-05-26T12:00:00", "environment": "test",
        "duration_minutes": 720, "total_payloads": 50,
        "total_would_execute": 35, "total_blocked": 15,
        "action_counts": {"send_user_reply": 25, "send_admin_alert": 5, "handoff_operator": 5},
        "channel_counts": {"user_dm": 25, "admin_group": 5, "internal_only": 20},
        "risk_counts": {"low": 30, "medium": 15, "high": 5},
        "block_reason_counts": {"stop_signal": 5, "daily_cap": 3, "high_risk_user_dm": 2},
        "no_send": Stage2NoSendSafetyMetrics(),
        "health_status": "green",
    }
    defaults.update(kw)
    return Stage2DryRunReport(**defaults)


class TestPassFailClean:
    def test_clean_passes(self):
        pf = svc.evaluate_pass_fail(_report())
        assert pf.passed is True

    def test_no_failures(self):
        pf = svc.evaluate_pass_fail(_report())
        assert pf.failures == []


class TestPassFailViolations:
    def test_actual_sent(self):
        pf = svc.evaluate_pass_fail(
            _report(no_send=Stage2NoSendSafetyMetrics(actual_sent_count=1)),
        )
        assert pf.passed is False

    def test_executed_records(self):
        pf = svc.evaluate_pass_fail(
            _report(no_send=Stage2NoSendSafetyMetrics(executed_records_count=1)),
        )
        assert pf.passed is False

    def test_live_sender(self):
        pf = svc.evaluate_pass_fail(
            _report(no_send=Stage2NoSendSafetyMetrics(live_sender_executed=1)),
        )
        assert pf.passed is False

    def test_all_zero_passes(self):
        pf = svc.evaluate_pass_fail(_report(no_send=Stage2NoSendSafetyMetrics()))
        assert pf.passed is True


class TestPassFailHealth:
    def test_health_red(self):
        pf = svc.evaluate_pass_fail(_report(health_status="red"))
        assert pf.passed is False

    def test_health_green(self):
        pf = svc.evaluate_pass_fail(_report(health_status="green"))
        assert pf.passed is True


class TestPassFailWarnings:
    def test_high_blocked_ratio(self):
        pf = svc.evaluate_pass_fail(_report(total_payloads=50, total_blocked=45))
        assert "high_blocked_ratio" in pf.warnings

    def test_normal_blocked_no_warning(self):
        pf = svc.evaluate_pass_fail(_report(total_payloads=50, total_blocked=10))
        assert "high_blocked_ratio" not in pf.warnings

    def test_high_risk_ratio(self):
        pf = svc.evaluate_pass_fail(
            _report(risk_counts={"high": 10, "critical": 10, "low": 10}, total_payloads=30),
        )
        assert "high_risk_ratio" in pf.warnings

    def test_no_payloads_warning(self):
        pf = svc.evaluate_pass_fail(_report(total_payloads=0))
        assert "no_payloads" in pf.warnings


class TestRecommendations:
    def test_fail_recommends_rollback(self):
        r = _report(no_send=Stage2NoSendSafetyMetrics(actual_sent_count=1))
        pf = svc.evaluate_pass_fail(r)
        recs = svc.build_recommendations(r, pf)
        assert any("rollback" in rec.lower() for rec in recs)

    def test_no_payloads_recommends_check(self):
        r = _report(total_payloads=0)
        pf = svc.evaluate_pass_fail(r)
        recs = svc.build_recommendations(r, pf)
        assert any("check" in rec.lower() or "no" in rec.lower() for rec in recs)

    def test_enough_payloads_recommends_canary(self):
        r = _report(total_payloads=50)
        pf = svc.evaluate_pass_fail(r)
        recs = svc.build_recommendations(r, pf)
        assert any("canary" in rec.lower() or "stage 3" in rec.lower() for rec in recs)

    def test_few_payloads_recommends_continue(self):
        r = _report(total_payloads=10)
        pf = svc.evaluate_pass_fail(r)
        recs = svc.build_recommendations(r, pf)
        assert any("continue" in rec.lower() or "active" in rec.lower() for rec in recs)

    def test_high_blocked_recommends_review(self):
        r = _report(total_payloads=50, total_blocked=45)
        pf = svc.evaluate_pass_fail(r)
        recs = svc.build_recommendations(r, pf)
        assert any("blocked" in rec.lower() or "review" in rec.lower() for rec in recs)


class TestMetricsCounting:
    def test_action_counts(self):
        r = _report()
        assert r.action_counts.get("send_user_reply") == 25

    def test_channel_counts(self):
        r = _report()
        assert r.channel_counts.get("user_dm") == 25

    def test_risk_counts(self):
        r = _report()
        assert r.risk_counts.get("low") == 30

    def test_block_reason_counts(self):
        r = _report()
        assert r.block_reason_counts.get("stop_signal") == 5


class TestReportDefaults:
    def test_empty_defaults(self):
        r = Stage2DryRunReport()
        assert r.total_payloads == 0
        assert r.health_status == "green"
        assert r.pass_fail.passed is True

    def test_no_send_defaults(self):
        ns = Stage2NoSendSafetyMetrics()
        assert ns.actual_sent_count == 0
        assert ns.executed_records_count == 0

    def test_frozen(self):
        import pytest
        r = Stage2DryRunReport()
        with pytest.raises(AttributeError):
            r.health_status = "red"  # type: ignore[misc]


class TestDBService:
    async def test_empty_db_safe(self):
        from datetime import UTC, datetime, timedelta
        from unittest.mock import AsyncMock, MagicMock
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar=MagicMock(return_value=0), all=MagicMock(return_value=[])),
        )
        s = Stage2DryRunReportService(session)
        now = datetime.now(UTC)
        r = await s.build_report(now - timedelta(hours=1), now)
        assert r.total_payloads == 0
        assert r.pass_fail.passed is True

    async def test_db_exception_safe(self):
        from datetime import UTC, datetime, timedelta
        from unittest.mock import AsyncMock
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=Exception("DB down"))
        s = Stage2DryRunReportService(session)
        now = datetime.now(UTC)
        r = await s.build_report(now - timedelta(hours=1), now)
        assert r.total_payloads == 0

    async def test_has_generated_at(self):
        from datetime import UTC, datetime, timedelta
        from unittest.mock import AsyncMock, MagicMock
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar=MagicMock(return_value=0), all=MagicMock(return_value=[])),
        )
        s = Stage2DryRunReportService(session)
        now = datetime.now(UTC)
        r = await s.build_report(now - timedelta(hours=2), now)
        assert r.generated_at != ""
        assert r.duration_minutes == 120


class TestRedaction:
    def test_no_secrets_in_defaults(self):
        from dataclasses import asdict
        text = str(asdict(Stage2DryRunReport()))
        assert "sk-" not in text
        assert "+998" not in text
