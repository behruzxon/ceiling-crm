"""Tests for Step AP — Stage3CanaryReadinessService."""

from __future__ import annotations

from core.schemas.stage2_dryrun_report import (
    Stage2DryRunReport,
    Stage2NoSendSafetyMetrics,
    Stage2PassFailResult,
)
from core.services.stage3_canary_readiness_service import Stage3CanaryReadinessService

svc = Stage3CanaryReadinessService


def _report(**kw) -> Stage2DryRunReport:
    defaults = {
        "generated_at": "2026-05-26T12:00:00",
        "since": "2026-05-26T00:00:00",
        "until": "2026-05-26T12:00:00",
        "environment": "test",
        "duration_minutes": 720,
        "total_payloads": 50,
        "total_would_execute": 35,
        "total_blocked": 15,
        "action_counts": {"send_user_reply": 25, "handoff_operator": 5},
        "channel_counts": {"user_dm": 25},
        "risk_counts": {"low": 40, "medium": 10},
        "block_reason_counts": {"stop_signal": 5},
        "no_send": Stage2NoSendSafetyMetrics(),
        "health_status": "green",
        "pass_fail": Stage2PassFailResult(passed=True),
    }
    defaults.update(kw)
    return Stage2DryRunReport(**defaults)


_IDS = {"agent_execution_canary_user_ids": "123,456"}


class TestReadyReport:
    def test_clean_ready(self):
        r = svc.evaluate_dryrun_to_canary(_report(), _IDS)
        assert r.verdict == "ready"
        assert r.allowed is True
        assert r.readiness_score >= 90

    def test_no_blockers(self):
        r = svc.evaluate_dryrun_to_canary(_report(), _IDS)
        assert r.blockers == []


class TestFailReport:
    def test_failed_dryrun(self):
        r = svc.evaluate_dryrun_to_canary(
            _report(pass_fail=Stage2PassFailResult(passed=False, failures=["x"])),
            _IDS,
        )
        assert r.verdict == "not_ready"


class TestNoSendViolations:
    def test_actual_sent(self):
        r = svc.evaluate_dryrun_to_canary(
            _report(no_send=Stage2NoSendSafetyMetrics(actual_sent_count=1)),
            _IDS,
        )
        assert r.verdict == "not_ready"

    def test_executed(self):
        r = svc.evaluate_dryrun_to_canary(
            _report(no_send=Stage2NoSendSafetyMetrics(executed_records_count=1)),
            _IDS,
        )
        assert r.verdict == "not_ready"

    def test_live_sender(self):
        r = svc.evaluate_dryrun_to_canary(
            _report(no_send=Stage2NoSendSafetyMetrics(live_sender_executed=1)),
            _IDS,
        )
        assert r.verdict == "not_ready"


class TestHealthBlocker:
    def test_red(self):
        r = svc.evaluate_dryrun_to_canary(_report(health_status="red"), _IDS)
        assert "health_red" in r.blockers

    def test_green_ok(self):
        r = svc.evaluate_dryrun_to_canary(_report(health_status="green"), _IDS)
        assert "health_red" not in r.blockers


class TestCanarySettings:
    def test_missing_ids(self):
        r = svc.evaluate_dryrun_to_canary(_report(), {})
        assert "missing_canary_user_ids" in r.blockers

    def test_with_ids_ok(self):
        r = svc.evaluate_dryrun_to_canary(_report(), _IDS)
        assert "missing_canary_user_ids" not in r.blockers

    def test_live_sender_enabled_blocker(self):
        r = svc.evaluate_dryrun_to_canary(
            _report(),
            {
                **_IDS,
                "agent_execution_live_sender_enabled": True,
            },
        )
        assert "live_sender_already_enabled" in r.blockers

    def test_auto_execute_blocker(self):
        r = svc.evaluate_dryrun_to_canary(
            _report(),
            {
                **_IDS,
                "agent_execution_auto_execute_approved": True,
            },
        )
        assert "auto_execute_already_enabled" in r.blockers

    def test_mode_live_blocker(self):
        r = svc.evaluate_dryrun_to_canary(
            _report(),
            {
                **_IDS,
                "agent_execution_mode": "live",
            },
        )
        assert "execution_mode_live" in r.blockers


class TestCriticalRisk:
    def test_critical_blocks(self):
        r = svc.evaluate_dryrun_to_canary(
            _report(risk_counts={"low": 40, "critical": 1}),
            _IDS,
        )
        assert "critical_risk_payloads_exist" in r.blockers


class TestWarnings:
    def test_low_payload(self):
        r = svc.evaluate_dryrun_to_canary(_report(total_payloads=10), _IDS)
        assert "low_payload_count" in r.warnings

    def test_no_payloads(self):
        r = svc.evaluate_dryrun_to_canary(
            _report(total_payloads=0, total_would_execute=0, total_blocked=0),
            _IDS,
        )
        assert "no_payloads" in r.warnings

    def test_low_would_execute(self):
        r = svc.evaluate_dryrun_to_canary(
            _report(total_payloads=50, total_would_execute=5),
            _IDS,
        )
        assert "low_would_execute_ratio" in r.warnings

    def test_high_blocked(self):
        r = svc.evaluate_dryrun_to_canary(
            _report(total_payloads=50, total_blocked=40),
            _IDS,
        )
        assert "high_blocked_ratio" in r.warnings

    def test_high_risk(self):
        r = svc.evaluate_dryrun_to_canary(
            _report(risk_counts={"high": 15, "low": 35}, total_payloads=50),
            _IDS,
        )
        assert "high_risk_ratio" in r.warnings

    def test_yellow_health(self):
        r = svc.evaluate_dryrun_to_canary(_report(health_status="yellow"), _IDS)
        assert "health_yellow" in r.warnings

    def test_short_observation(self):
        r = svc.evaluate_dryrun_to_canary(_report(duration_minutes=20), _IDS)
        assert "short_observation" in r.warnings

    def test_no_operator(self):
        r = svc.evaluate_dryrun_to_canary(
            _report(action_counts={"send_user_reply": 50}),
            _IDS,
        )
        assert "no_operator_scenarios" in r.warnings


class TestScore:
    def test_clean_high(self):
        r = svc.evaluate_dryrun_to_canary(_report(), _IDS)
        assert r.readiness_score >= 90

    def test_blocker_max_40(self):
        r = svc.evaluate_dryrun_to_canary(_report(health_status="red"), _IDS)
        assert r.readiness_score <= 40

    def test_warnings_reduce(self):
        r = svc.evaluate_dryrun_to_canary(
            _report(health_status="yellow", duration_minutes=20),
            _IDS,
        )
        assert r.readiness_score < 100

    def test_clamped(self):
        r = svc.evaluate_dryrun_to_canary(
            _report(
                no_send=Stage2NoSendSafetyMetrics(
                    actual_sent_count=1,
                    executed_records_count=1,
                ),
                pass_fail=Stage2PassFailResult(passed=False),
            ),
            _IDS,
        )
        assert 0 <= r.readiness_score <= 100

    def test_ready_90(self):
        r = svc.evaluate_dryrun_to_canary(_report(), _IDS)
        if r.readiness_score >= 90 and not r.blockers:
            assert r.verdict == "ready"

    def test_conditional_70_89(self):
        r = svc.evaluate_dryrun_to_canary(
            _report(
                health_status="yellow", total_payloads=15, action_counts={"send_user_reply": 15}
            ),
            _IDS,
        )
        if 70 <= r.readiness_score < 90 and not r.blockers:
            assert r.verdict == "conditional"


class TestRecommendations:
    def test_ready(self):
        r = svc.evaluate_dryrun_to_canary(_report(), _IDS)
        assert any("ready" in rec.lower() or "canary" in rec.lower() for rec in r.recommendations)

    def test_missing_ids(self):
        r = svc.evaluate_dryrun_to_canary(_report(), {})
        assert any("canary" in rec.lower() or "ids" in rec.lower() for rec in r.recommendations)

    def test_fail_recommends_fix(self):
        r = svc.evaluate_dryrun_to_canary(
            _report(pass_fail=Stage2PassFailResult(passed=False, failures=["x"])),
            _IDS,
        )
        assert any("fail" in rec.lower() or "fix" in rec.lower() for rec in r.recommendations)


class TestEmpty:
    def test_empty_safe(self):
        r = svc.evaluate_dryrun_to_canary(Stage2DryRunReport(), {})
        assert isinstance(r.verdict, str)
        assert 0 <= r.readiness_score <= 100

    def test_no_secrets(self):
        r = svc.evaluate_dryrun_to_canary(_report(), _IDS)
        assert "sk-" not in str(r) and "+998" not in str(r)


class TestImmutability:
    def test_frozen(self):
        import pytest

        r = svc.evaluate_dryrun_to_canary(_report(), _IDS)
        with pytest.raises(AttributeError):
            r.verdict = "x"  # type: ignore[misc]

    def test_generated_at(self):
        r = svc.evaluate_dryrun_to_canary(_report(), _IDS)
        assert r.generated_at != ""
        assert r.from_stage == "dry_run"
        assert r.to_stage == "canary"
