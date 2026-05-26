"""Tests for Step AV — Stage5LiveSendReadinessService (strictest gate)."""
from __future__ import annotations
from core.schemas.stage4_approval_report import (
    Stage4ApprovalReport, Stage4NoSendSafetyMetrics, Stage4PassFailResult,
)
from core.services.stage5_live_send_readiness_service import Stage5LiveSendReadinessService

svc = Stage5LiveSendReadinessService

def _report(**kw) -> Stage4ApprovalReport:
    defaults = {
        "generated_at": "t", "since": "t", "until": "t", "environment": "test",
        "duration_minutes": 720, "total_proposals": 30, "proposed_count": 5,
        "approved_count": 15, "rejected_count": 5, "expired_count": 3,
        "blocked_count": 2, "executed_count": 0, "pending_count": 0,
        "stale_pending_count": 0,
        "no_send": Stage4NoSendSafetyMetrics(), "health_status": "green",
        "pass_fail": Stage4PassFailResult(passed=True),
    }
    defaults.update(kw)
    return Stage4ApprovalReport(**defaults)

_SAFE = {"agent_settings_allow_live_flags": True}


class TestReady:
    def test_clean(self):
        r = svc.evaluate_approval_to_live_send(_report(), _SAFE)
        assert r.verdict == "ready" and r.allowed and r.readiness_score >= 95


class TestBlockers:
    def test_failed_report(self):
        r = svc.evaluate_approval_to_live_send(
            _report(pass_fail=Stage4PassFailResult(passed=False, failures=["x"])), _SAFE)
        assert r.verdict == "not_ready"

    def test_executed(self):
        assert not svc.evaluate_approval_to_live_send(
            _report(no_send=Stage4NoSendSafetyMetrics(executed_records_count=1)), _SAFE).allowed

    def test_live_sender(self):
        assert not svc.evaluate_approval_to_live_send(
            _report(no_send=Stage4NoSendSafetyMetrics(live_sender_executed=1)), _SAFE).allowed

    def test_auto_execute(self):
        assert not svc.evaluate_approval_to_live_send(
            _report(no_send=Stage4NoSendSafetyMetrics(auto_execute_count=1)), _SAFE).allowed

    def test_user_dm(self):
        assert not svc.evaluate_approval_to_live_send(
            _report(no_send=Stage4NoSendSafetyMetrics(user_dm_sent_count=1)), _SAFE).allowed

    def test_health_red(self):
        assert "health_red" in svc.evaluate_approval_to_live_send(
            _report(health_status="red"), _SAFE).blockers

    def test_no_proposals(self):
        assert "no_proposals" in svc.evaluate_approval_to_live_send(
            _report(total_proposals=0), _SAFE).blockers

    def test_no_approved(self):
        assert "no_approved_samples" in svc.evaluate_approval_to_live_send(
            _report(total_proposals=10, approved_count=0), _SAFE).blockers

    def test_stale_excessive(self):
        assert "stale_pending_excessive" in svc.evaluate_approval_to_live_send(
            _report(stale_pending_count=25), _SAFE).blockers

    def test_allow_live_false(self):
        assert "allow_live_flags_false" in svc.evaluate_approval_to_live_send(
            _report(), {}).blockers

    def test_mode_live(self):
        assert "execution_mode_already_live" in svc.evaluate_approval_to_live_send(
            _report(), {**_SAFE, "agent_execution_mode": "live"}).blockers


class TestWarnings:
    def test_low_proposals(self):
        assert "low_proposal_count" in svc.evaluate_approval_to_live_send(
            _report(total_proposals=10), _SAFE).warnings

    def test_low_approved(self):
        assert "low_approved_count" in svc.evaluate_approval_to_live_send(
            _report(approved_count=3), _SAFE).warnings

    def test_high_rejection(self):
        assert "high_rejection_rate" in svc.evaluate_approval_to_live_send(
            _report(total_proposals=20, rejected_count=18), _SAFE).warnings

    def test_high_expiration(self):
        assert "high_expiration_rate" in svc.evaluate_approval_to_live_send(
            _report(total_proposals=20, expired_count=15), _SAFE).warnings

    def test_pending_high(self):
        assert "pending_count_high" in svc.evaluate_approval_to_live_send(
            _report(pending_count=25), _SAFE).warnings

    def test_yellow_health(self):
        assert "health_yellow" in svc.evaluate_approval_to_live_send(
            _report(health_status="yellow"), _SAFE).warnings

    def test_short_observation(self):
        assert "short_observation" in svc.evaluate_approval_to_live_send(
            _report(duration_minutes=20), _SAFE).warnings


class TestScore:
    def test_clean_high(self):
        assert svc.evaluate_approval_to_live_send(_report(), _SAFE).readiness_score >= 95

    def test_blocker_max_40(self):
        assert svc.evaluate_approval_to_live_send(
            _report(health_status="red"), _SAFE).readiness_score <= 40

    def test_warnings_reduce(self):
        r = svc.evaluate_approval_to_live_send(
            _report(health_status="yellow", duration_minutes=20), _SAFE)
        assert r.readiness_score < 100

    def test_clamped(self):
        r = svc.evaluate_approval_to_live_send(
            _report(no_send=Stage4NoSendSafetyMetrics(executed_records_count=1),
                    pass_fail=Stage4PassFailResult(passed=False), health_status="red"), _SAFE)
        assert 0 <= r.readiness_score <= 100

    def test_ready_95(self):
        r = svc.evaluate_approval_to_live_send(_report(), _SAFE)
        if r.readiness_score >= 95 and not r.blockers:
            assert r.verdict == "ready"

    def test_conditional_80_94(self):
        r = svc.evaluate_approval_to_live_send(
            _report(health_status="yellow", total_proposals=15, approved_count=3), _SAFE)
        if 80 <= r.readiness_score < 95 and not r.blockers:
            assert r.verdict == "conditional"


class TestRecommendations:
    def test_ready(self):
        r = svc.evaluate_approval_to_live_send(_report(), _SAFE)
        assert any("ready" in rec.lower() or "live" in rec.lower() for rec in r.recommendations)

    def test_violation_rollback(self):
        r = svc.evaluate_approval_to_live_send(
            _report(no_send=Stage4NoSendSafetyMetrics(executed_records_count=1)), _SAFE)
        assert any("rollback" in rec.lower() for rec in r.recommendations)

    def test_allow_live_false(self):
        r = svc.evaluate_approval_to_live_send(_report(), {})
        assert any("allow_live" in rec.lower() or "live" in rec.lower() for rec in r.recommendations)

    def test_no_proposals(self):
        r = svc.evaluate_approval_to_live_send(_report(total_proposals=0), _SAFE)
        assert any("proposal" in rec.lower() or "continue" in rec.lower() for rec in r.recommendations)

    def test_no_approved(self):
        r = svc.evaluate_approval_to_live_send(
            _report(total_proposals=10, approved_count=0), _SAFE)
        assert any("approve" in rec.lower() for rec in r.recommendations)


class TestEmpty:
    def test_safe(self):
        r = svc.evaluate_approval_to_live_send(Stage4ApprovalReport(), {})
        assert isinstance(r.verdict, str) and 0 <= r.readiness_score <= 100

    def test_no_secrets(self):
        assert "sk-" not in str(svc.evaluate_approval_to_live_send(_report(), _SAFE))


class TestImmutability:
    def test_frozen(self):
        import pytest
        r = svc.evaluate_approval_to_live_send(_report(), _SAFE)
        with pytest.raises(AttributeError):
            r.verdict = "x"  # type: ignore[misc]

    def test_meta(self):
        r = svc.evaluate_approval_to_live_send(_report(), _SAFE)
        assert r.generated_at != ""
        assert r.from_stage == "approval_required"
        assert r.to_stage == "approved_live_send"
