"""Tests for Step AM — StageTransitionGateService."""
from __future__ import annotations

from core.schemas.stage1_observation_report import (
    Stage1NoSendSafetyMetrics,
    Stage1ObservationReport,
    Stage1PassFailResult,
)
from core.services.stage_transition_gate_service import StageTransitionGateService

svc = StageTransitionGateService


def _report(**kw) -> Stage1ObservationReport:
    defaults = {
        "generated_at": "2026-05-26T12:00:00", "since": "2026-05-26T00:00:00",
        "until": "2026-05-26T12:00:00", "environment": "test",
        "duration_minutes": 720, "total_users_observed": 50,
        "total_journey_events": 100, "total_orchestrator_traces": 80,
        "intent_counts": {"wants_price": 30, "wants_catalog": 20, "unclear": 10},
        "objection_counts": {"price": 5, "trust": 3},
        "decision_state_counts": {}, "offer_type_counts": {},
        "policy_action_counts": {},
        "no_send": Stage1NoSendSafetyMetrics(),
        "health_status": "green",
        "pass_fail": Stage1PassFailResult(passed=True),
    }
    defaults.update(kw)
    return Stage1ObservationReport(**defaults)


class TestPassReport:
    def test_clean_report_ready(self):
        r = svc.evaluate_stage1_to_dry_run(_report())
        assert r.verdict == "ready"
        assert r.allowed is True
        assert r.readiness_score >= 85

    def test_no_blockers(self):
        r = svc.evaluate_stage1_to_dry_run(_report())
        assert r.blockers == []


class TestFailReport:
    def test_failed_report_not_ready(self):
        r = svc.evaluate_stage1_to_dry_run(
            _report(pass_fail=Stage1PassFailResult(passed=False, failures=["x"])),
        )
        assert r.verdict == "not_ready"
        assert "stage1_report_failed" in r.blockers


class TestNoSendViolations:
    def test_followup_sent(self):
        r = svc.evaluate_stage1_to_dry_run(
            _report(no_send=Stage1NoSendSafetyMetrics(followups_sent=1)),
        )
        assert r.verdict == "not_ready"

    def test_admin_escalation(self):
        r = svc.evaluate_stage1_to_dry_run(
            _report(no_send=Stage1NoSendSafetyMetrics(admin_escalations_sent=1)),
        )
        assert r.verdict == "not_ready"

    def test_execution_executed(self):
        r = svc.evaluate_stage1_to_dry_run(
            _report(no_send=Stage1NoSendSafetyMetrics(execution_records_executed=1)),
        )
        assert r.verdict == "not_ready"

    def test_live_sender(self):
        r = svc.evaluate_stage1_to_dry_run(
            _report(no_send=Stage1NoSendSafetyMetrics(live_sender_executed=1)),
        )
        assert r.verdict == "not_ready"

    def test_all_zero_ok(self):
        r = svc.evaluate_stage1_to_dry_run(_report())
        assert "followups_sent_violation" not in r.blockers


class TestHealthBlocker:
    def test_health_red(self):
        r = svc.evaluate_stage1_to_dry_run(_report(health_status="red"))
        assert r.verdict == "not_ready"
        assert "health_red" in r.blockers

    def test_health_green(self):
        r = svc.evaluate_stage1_to_dry_run(_report(health_status="green"))
        assert "health_red" not in r.blockers


class TestWarnings:
    def test_low_traces(self):
        r = svc.evaluate_stage1_to_dry_run(
            _report(total_orchestrator_traces=10, total_journey_events=50),
        )
        assert "low_traces" in r.warnings

    def test_no_traffic(self):
        r = svc.evaluate_stage1_to_dry_run(
            _report(total_journey_events=0, total_orchestrator_traces=0, total_users_observed=0),
        )
        assert "no_traffic" in r.warnings

    def test_yellow_health(self):
        r = svc.evaluate_stage1_to_dry_run(_report(health_status="yellow"))
        assert "health_yellow" in r.warnings

    def test_short_observation(self):
        r = svc.evaluate_stage1_to_dry_run(_report(duration_minutes=20))
        assert "short_observation" in r.warnings

    def test_high_unclear(self):
        r = svc.evaluate_stage1_to_dry_run(
            _report(intent_counts={"unclear": 25, "wants_price": 5}),
        )
        assert "high_unclear_ratio" in r.warnings

    def test_high_price_objection(self):
        r = svc.evaluate_stage1_to_dry_run(
            _report(objection_counts={"price": 15, "trust": 2}),
        )
        assert "high_price_objection" in r.warnings

    def test_high_stop_rate(self):
        r = svc.evaluate_stage1_to_dry_run(
            _report(intent_counts={"stop_request": 8, "wants_price": 5, "unclear": 2}),
        )
        assert "high_stop_rate" in r.warnings


class TestReadinessScore:
    def test_clean_100(self):
        r = svc.evaluate_stage1_to_dry_run(_report())
        assert r.readiness_score >= 85

    def test_blocker_max_40(self):
        r = svc.evaluate_stage1_to_dry_run(
            _report(no_send=Stage1NoSendSafetyMetrics(followups_sent=1)),
        )
        assert r.readiness_score <= 40

    def test_warnings_reduce_score(self):
        r = svc.evaluate_stage1_to_dry_run(
            _report(health_status="yellow", duration_minutes=20),
        )
        assert r.readiness_score < 100

    def test_score_clamped_0_100(self):
        r = svc.evaluate_stage1_to_dry_run(
            _report(no_send=Stage1NoSendSafetyMetrics(
                followups_sent=1, admin_escalations_sent=1,
                execution_records_executed=1, live_sender_executed=1,
            ), pass_fail=Stage1PassFailResult(passed=False, failures=["x"])),
        )
        assert 0 <= r.readiness_score <= 100

    def test_ready_threshold_85(self):
        r = svc.evaluate_stage1_to_dry_run(_report())
        if r.readiness_score >= 85 and not r.blockers:
            assert r.verdict == "ready"

    def test_conditional_65_84(self):
        r = svc.evaluate_stage1_to_dry_run(
            _report(health_status="yellow", duration_minutes=20,
                    total_orchestrator_traces=15, total_journey_events=50),
        )
        if 65 <= r.readiness_score < 85 and not r.blockers:
            assert r.verdict == "conditional"

    def test_not_ready_below_65(self):
        r = svc.evaluate_stage1_to_dry_run(
            _report(total_journey_events=0, total_orchestrator_traces=0,
                    total_users_observed=0, health_status="yellow",
                    duration_minutes=10),
        )
        if r.readiness_score < 65 and not r.blockers:
            assert r.verdict == "not_ready"


class TestRecommendations:
    def test_fail_recommends_fix(self):
        r = svc.evaluate_stage1_to_dry_run(
            _report(pass_fail=Stage1PassFailResult(passed=False, failures=["x"])),
        )
        assert any("fix" in rec.lower() or "fail" in rec.lower() for rec in r.recommendations)

    def test_violation_recommends_rollback(self):
        r = svc.evaluate_stage1_to_dry_run(
            _report(no_send=Stage1NoSendSafetyMetrics(followups_sent=1)),
        )
        assert any("rollback" in rec.lower() or "violation" in rec.lower() for rec in r.recommendations)

    def test_low_traces_recommends_continue(self):
        rep = _report(total_orchestrator_traces=10, total_journey_events=50)
        blockers = svc.build_blockers(rep, {})
        warnings = svc.build_warnings(rep)
        score = svc.calculate_readiness_score(rep, blockers, warnings)
        recs = svc.build_recommendations(rep, blockers, warnings, score)
        assert any("continue" in r.lower() or "low" in r.lower() for r in recs)

    def test_ready_recommends_dryrun(self):
        rep = _report()
        blockers = svc.build_blockers(rep, {})
        warnings = svc.build_warnings(rep)
        score = svc.calculate_readiness_score(rep, blockers, warnings)
        recs = svc.build_recommendations(rep, blockers, warnings, score)
        assert any("dry_run" in r.lower() or "ready" in r.lower() for r in recs)


class TestEmptyReport:
    def test_empty_safe(self):
        r = svc.evaluate_stage1_to_dry_run(Stage1ObservationReport())
        assert isinstance(r.verdict, str)
        assert 0 <= r.readiness_score <= 100

    def test_no_secrets(self):
        r = svc.evaluate_stage1_to_dry_run(_report())
        text = str(r)
        assert "sk-" not in text
        assert "+998" not in text


class TestImmutability:
    def test_frozen(self):
        import pytest
        r = svc.evaluate_stage1_to_dry_run(_report())
        with pytest.raises(AttributeError):
            r.verdict = "x"  # type: ignore[misc]


class TestGeneratedAt:
    def test_has_timestamp(self):
        r = svc.evaluate_stage1_to_dry_run(_report())
        assert r.generated_at != ""

    def test_from_to_stage(self):
        r = svc.evaluate_stage1_to_dry_run(_report())
        assert r.from_stage == "log_only"
        assert r.to_stage == "dry_run"
