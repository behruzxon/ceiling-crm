"""Tests for Step AL — Stage1ObservationReportService (pure pass/fail logic)."""
from __future__ import annotations

from core.schemas.stage1_observation_report import (
    Stage1NoSendSafetyMetrics,
    Stage1ObservationReport,
    Stage1PassFailResult,
)
from core.services.stage1_observation_report_service import (
    Stage1ObservationReportService,
)

svc = Stage1ObservationReportService


def _report(**kw) -> Stage1ObservationReport:
    defaults = {
        "generated_at": "2026-05-26T12:00:00",
        "since": "2026-05-26T00:00:00",
        "until": "2026-05-26T12:00:00",
        "environment": "test",
        "duration_minutes": 720,
        "total_users_observed": 0,
        "total_journey_events": 0,
        "total_orchestrator_traces": 0,
        "intent_counts": {},
        "objection_counts": {},
        "decision_state_counts": {},
        "offer_type_counts": {},
        "policy_action_counts": {},
        "no_send": Stage1NoSendSafetyMetrics(),
        "health_status": "green",
    }
    defaults.update(kw)
    return Stage1ObservationReport(**defaults)


class TestPassFailEmpty:
    def test_empty_report_passes(self):
        r = _report()
        pf = svc.evaluate_pass_fail(r)
        assert pf.passed is True

    def test_empty_warns_no_traffic(self):
        r = _report()
        pf = svc.evaluate_pass_fail(r)
        assert "no_traffic_observed" in pf.warnings


class TestPassFailNoSendViolations:
    def test_followup_scheduled_fails(self):
        r = _report(no_send=Stage1NoSendSafetyMetrics(followups_scheduled=1))
        pf = svc.evaluate_pass_fail(r)
        assert pf.passed is False

    def test_followup_sent_fails(self):
        r = _report(no_send=Stage1NoSendSafetyMetrics(followups_sent=1))
        pf = svc.evaluate_pass_fail(r)
        assert pf.passed is False

    def test_admin_escalation_fails(self):
        r = _report(no_send=Stage1NoSendSafetyMetrics(admin_escalations_sent=1))
        pf = svc.evaluate_pass_fail(r)
        assert pf.passed is False

    def test_execution_executed_fails(self):
        r = _report(no_send=Stage1NoSendSafetyMetrics(execution_records_executed=1))
        pf = svc.evaluate_pass_fail(r)
        assert pf.passed is False

    def test_live_sender_fails(self):
        r = _report(no_send=Stage1NoSendSafetyMetrics(live_sender_executed=1))
        pf = svc.evaluate_pass_fail(r)
        assert pf.passed is False

    def test_all_zero_passes(self):
        r = _report(no_send=Stage1NoSendSafetyMetrics())
        pf = svc.evaluate_pass_fail(r)
        assert pf.passed is True


class TestPassFailHealth:
    def test_health_red_fails(self):
        r = _report(health_status="red")
        pf = svc.evaluate_pass_fail(r)
        assert pf.passed is False

    def test_health_green_passes(self):
        r = _report(health_status="green")
        pf = svc.evaluate_pass_fail(r)
        assert pf.passed is True

    def test_health_yellow_passes(self):
        r = _report(health_status="yellow")
        pf = svc.evaluate_pass_fail(r)
        assert pf.passed is True


class TestPassFailTraces:
    def test_traffic_no_traces_warning(self):
        r = _report(total_journey_events=50, total_orchestrator_traces=0)
        pf = svc.evaluate_pass_fail(r)
        assert "traffic_but_no_traces" in pf.warnings

    def test_traffic_with_traces_no_warning(self):
        r = _report(total_journey_events=50, total_orchestrator_traces=30)
        pf = svc.evaluate_pass_fail(r)
        assert "traffic_but_no_traces" not in pf.warnings


class TestPassFailIntents:
    def test_high_unclear_warning(self):
        r = _report(intent_counts={"unclear": 15, "wants_price": 3})
        pf = svc.evaluate_pass_fail(r)
        assert "high_unclear_ratio" in pf.warnings

    def test_low_unclear_no_warning(self):
        r = _report(intent_counts={"unclear": 2, "wants_price": 10})
        pf = svc.evaluate_pass_fail(r)
        assert "high_unclear_ratio" not in pf.warnings


class TestRecommendations:
    def test_fail_recommends_rollback(self):
        r = _report(no_send=Stage1NoSendSafetyMetrics(followups_sent=1))
        pf = svc.evaluate_pass_fail(r)
        recs = svc.build_recommendations(r, pf)
        assert any("rollback" in rec.lower() for rec in recs)

    def test_no_traces_recommends_check(self):
        r = _report()
        pf = svc.evaluate_pass_fail(r)
        recs = svc.build_recommendations(r, pf)
        assert any("check" in rec.lower() or "no traces" in rec.lower() for rec in recs)

    def test_enough_traces_recommends_stage2(self):
        r = _report(total_orchestrator_traces=60, total_journey_events=60)
        pf = svc.evaluate_pass_fail(r)
        recs = svc.build_recommendations(r, pf)
        assert any("stage 2" in rec.lower() or "dry_run" in rec.lower() for rec in recs)

    def test_few_traces_recommends_continue(self):
        r = _report(total_orchestrator_traces=10, total_journey_events=10)
        pf = svc.evaluate_pass_fail(r)
        recs = svc.build_recommendations(r, pf)
        assert any("continue" in rec.lower() or "pass" in rec.lower() for rec in recs)

    def test_high_unclear_recommends_improve(self):
        r = _report(
            intent_counts={"unclear": 20, "wants_price": 5},
            total_orchestrator_traces=25,
            total_journey_events=25,
        )
        pf = svc.evaluate_pass_fail(r)
        recs = svc.build_recommendations(r, pf)
        assert any("unclear" in rec.lower() or "keyword" in rec.lower() for rec in recs)

    def test_price_objection_high_recommends_improve(self):
        r = _report(
            objection_counts={"price": 8, "trust": 2},
            total_orchestrator_traces=10,
            total_journey_events=10,
        )
        pf = svc.evaluate_pass_fail(r)
        recs = svc.build_recommendations(r, pf)
        assert any("price" in rec.lower() for rec in recs)


class TestRedaction:
    def test_phone_redacted(self):
        r = svc.redact_sensitive("Call +998901234567")
        assert "+998901234567" not in r
        assert "[***]" in r

    def test_token_redacted(self):
        r = svc.redact_sensitive("sk-abc123secret")
        assert "sk-abc" not in r

    def test_clean_text_unchanged(self):
        r = svc.redact_sensitive("Salom dunyo")
        assert r == "Salom dunyo"


class TestReportSchema:
    def test_defaults(self):
        r = Stage1ObservationReport()
        assert r.total_users_observed == 0
        assert r.health_status == "green"
        assert r.pass_fail.passed is True

    def test_frozen(self):
        import pytest
        r = Stage1ObservationReport()
        with pytest.raises(AttributeError):
            r.health_status = "red"  # type: ignore[misc]

    def test_no_send_defaults(self):
        ns = Stage1NoSendSafetyMetrics()
        assert ns.followups_scheduled == 0
        assert ns.live_sender_executed == 0

    def test_pass_fail_defaults(self):
        pf = Stage1PassFailResult()
        assert pf.passed is True


class TestDBService:
    async def test_empty_db_safe(self):
        from datetime import UTC, datetime, timedelta
        from unittest.mock import AsyncMock, MagicMock
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar=MagicMock(return_value=0)),
        )
        s = Stage1ObservationReportService(session)
        now = datetime.now(UTC)
        r = await s.build_report(now - timedelta(hours=1), now)
        assert r.total_users_observed == 0
        assert r.pass_fail.passed is True

    async def test_db_exception_safe(self):
        from datetime import UTC, datetime, timedelta
        from unittest.mock import AsyncMock
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=Exception("DB down"))
        s = Stage1ObservationReportService(session)
        now = datetime.now(UTC)
        r = await s.build_report(now - timedelta(hours=1), now)
        assert r.total_users_observed == 0

    async def test_report_has_generated_at(self):
        from datetime import UTC, datetime, timedelta
        from unittest.mock import AsyncMock, MagicMock
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar=MagicMock(return_value=0)),
        )
        s = Stage1ObservationReportService(session)
        now = datetime.now(UTC)
        r = await s.build_report(now - timedelta(hours=1), now)
        assert r.generated_at != ""

    async def test_duration_calculated(self):
        from datetime import UTC, datetime, timedelta
        from unittest.mock import AsyncMock, MagicMock
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar=MagicMock(return_value=0)),
        )
        s = Stage1ObservationReportService(session)
        now = datetime.now(UTC)
        r = await s.build_report(now - timedelta(hours=2), now)
        assert r.duration_minutes == 120

    async def test_environment_set(self):
        from datetime import UTC, datetime, timedelta
        from unittest.mock import AsyncMock, MagicMock
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar=MagicMock(return_value=0)),
        )
        s = Stage1ObservationReportService(session)
        now = datetime.now(UTC)
        r = await s.build_report(now - timedelta(hours=1), now, environment="staging")
        assert r.environment == "staging"
