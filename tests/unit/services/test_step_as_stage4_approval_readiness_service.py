"""Tests for Step AS — Stage4ApprovalReadinessService."""

from __future__ import annotations

from core.schemas.stage3_canary_report import (
    Stage3CanaryReport,
    Stage3PassFailResult,
    Stage3PublicSafetyMetrics,
)
from core.services.stage4_approval_readiness_service import (
    Stage4ApprovalReadinessService,
)

svc = Stage4ApprovalReadinessService


def _report(**kw) -> Stage3CanaryReport:
    defaults = {
        "generated_at": "t",
        "since": "t",
        "until": "t",
        "environment": "test",
        "duration_minutes": 720,
        "canary_user_count": 2,
        "canary_payload_count": 30,
        "canary_allowed_count": 25,
        "canary_blocked_count": 5,
        "non_canary_attempts": 10,
        "non_canary_blocked": 10,
        "block_reason_counts": {"non_canary_user": 10},
        "risk_counts": {"low": 25, "medium": 5},
        "public_safety": Stage3PublicSafetyMetrics(),
        "health_status": "green",
        "pass_fail": Stage3PassFailResult(passed=True),
    }
    defaults.update(kw)
    return Stage3CanaryReport(**defaults)


_SAFE = {"agent_execution_queue_enabled": True, "agent_execution_api_approval_enabled": True}


class TestReady:
    def test_clean(self):
        r = svc.evaluate_canary_to_approval(_report(), _SAFE)
        assert r.verdict == "ready" and r.allowed and r.readiness_score >= 90


class TestBlockers:
    def test_failed_report(self):
        r = svc.evaluate_canary_to_approval(
            _report(pass_fail=Stage3PassFailResult(passed=False, failures=["x"])), _SAFE
        )
        assert r.verdict == "not_ready"

    def test_public_send(self):
        r = svc.evaluate_canary_to_approval(
            _report(public_safety=Stage3PublicSafetyMetrics(public_user_send_count=1)), _SAFE
        )
        assert not r.allowed

    def test_non_canary_allowed(self):
        r = svc.evaluate_canary_to_approval(
            _report(public_safety=Stage3PublicSafetyMetrics(non_canary_allowed_count=1)), _SAFE
        )
        assert not r.allowed

    def test_high_risk_sent(self):
        r = svc.evaluate_canary_to_approval(
            _report(public_safety=Stage3PublicSafetyMetrics(high_risk_sent_count=1)), _SAFE
        )
        assert not r.allowed

    def test_critical_sent(self):
        r = svc.evaluate_canary_to_approval(
            _report(public_safety=Stage3PublicSafetyMetrics(critical_risk_sent_count=1)), _SAFE
        )
        assert not r.allowed

    def test_duplicate(self):
        r = svc.evaluate_canary_to_approval(
            _report(public_safety=Stage3PublicSafetyMetrics(duplicate_sent_count=1)), _SAFE
        )
        assert not r.allowed

    def test_leak(self):
        r = svc.evaluate_canary_to_approval(
            _report(public_safety=Stage3PublicSafetyMetrics(sensitive_leak_count=1)), _SAFE
        )
        assert not r.allowed

    def test_health_red(self):
        r = svc.evaluate_canary_to_approval(_report(health_status="red"), _SAFE)
        assert "health_red" in r.blockers

    def test_live_sender(self):
        r = svc.evaluate_canary_to_approval(
            _report(), {**_SAFE, "agent_execution_live_sender_enabled": True}
        )
        assert "live_sender_enabled" in r.blockers

    def test_auto_execute(self):
        r = svc.evaluate_canary_to_approval(
            _report(), {**_SAFE, "agent_execution_auto_execute_approved": True}
        )
        assert "auto_execute_enabled" in r.blockers

    def test_mode_live(self):
        r = svc.evaluate_canary_to_approval(_report(), {**_SAFE, "agent_execution_mode": "live"})
        assert "execution_mode_live" in r.blockers

    def test_queue_disabled(self):
        r = svc.evaluate_canary_to_approval(
            _report(),
            {"agent_execution_queue_enabled": False, "agent_execution_api_approval_enabled": True},
        )
        assert "queue_disabled" in r.blockers

    def test_api_approval_disabled(self):
        r = svc.evaluate_canary_to_approval(
            _report(),
            {"agent_execution_queue_enabled": True, "agent_execution_api_approval_enabled": False},
        )
        assert "api_approval_disabled" in r.blockers


class TestWarnings:
    def test_low_canary(self):
        r = svc.evaluate_canary_to_approval(_report(canary_payload_count=5), _SAFE)
        assert "low_canary_sends" in r.warnings

    def test_no_canary(self):
        r = svc.evaluate_canary_to_approval(
            _report(canary_payload_count=0, canary_allowed_count=0, canary_blocked_count=0), _SAFE
        )
        assert "no_canary_sends" in r.warnings

    def test_high_blocked(self):
        r = svc.evaluate_canary_to_approval(
            _report(canary_payload_count=20, canary_blocked_count=18), _SAFE
        )
        assert "high_blocked_ratio" in r.warnings

    def test_yellow_health(self):
        r = svc.evaluate_canary_to_approval(_report(health_status="yellow"), _SAFE)
        assert "health_yellow" in r.warnings

    def test_short(self):
        r = svc.evaluate_canary_to_approval(_report(duration_minutes=20), _SAFE)
        assert "short_observation" in r.warnings


class TestScore:
    def test_clean_high(self):
        r = svc.evaluate_canary_to_approval(_report(), _SAFE)
        assert r.readiness_score >= 90

    def test_blocker_max_40(self):
        r = svc.evaluate_canary_to_approval(_report(health_status="red"), _SAFE)
        assert r.readiness_score <= 40

    def test_warnings_reduce(self):
        r = svc.evaluate_canary_to_approval(
            _report(health_status="yellow", duration_minutes=20), _SAFE
        )
        assert r.readiness_score < 100

    def test_clamped(self):
        r = svc.evaluate_canary_to_approval(
            _report(
                health_status="red",
                public_safety=Stage3PublicSafetyMetrics(public_user_send_count=1),
                pass_fail=Stage3PassFailResult(passed=False),
            ),
            _SAFE,
        )
        assert 0 <= r.readiness_score <= 100


class TestRecommendations:
    def test_ready(self):
        r = svc.evaluate_canary_to_approval(_report(), _SAFE)
        assert any("ready" in rec.lower() or "approval" in rec.lower() for rec in r.recommendations)

    def test_violation_rollback(self):
        r = svc.evaluate_canary_to_approval(
            _report(public_safety=Stage3PublicSafetyMetrics(public_user_send_count=1)), _SAFE
        )
        assert any("rollback" in rec.lower() for rec in r.recommendations)

    def test_queue_missing(self):
        r = svc.evaluate_canary_to_approval(
            _report(),
            {"agent_execution_queue_enabled": False, "agent_execution_api_approval_enabled": True},
        )
        assert any("queue" in rec.lower() for rec in r.recommendations)


class TestEmpty:
    def test_safe(self):
        r = svc.evaluate_canary_to_approval(Stage3CanaryReport(), {})
        assert isinstance(r.verdict, str) and 0 <= r.readiness_score <= 100

    def test_no_secrets(self):
        assert "sk-" not in str(svc.evaluate_canary_to_approval(_report(), _SAFE))


class TestImmutability:
    def test_frozen(self):
        import pytest

        r = svc.evaluate_canary_to_approval(_report(), _SAFE)
        with pytest.raises(AttributeError):
            r.verdict = "x"  # type: ignore[misc]

    def test_meta(self):
        r = svc.evaluate_canary_to_approval(_report(), _SAFE)
        assert (
            r.generated_at != "" and r.from_stage == "canary" and r.to_stage == "approval_required"
        )
