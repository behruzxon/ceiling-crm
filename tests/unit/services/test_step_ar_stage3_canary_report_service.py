"""Tests for Step AR — Stage3CanaryReportService (pure pass/fail logic)."""
from __future__ import annotations

from core.schemas.stage3_canary_report import (
    Stage3CanaryReport,
    Stage3PublicSafetyMetrics,
)
from core.services.stage3_canary_report_service import Stage3CanaryReportService

svc = Stage3CanaryReportService


def _report(**kw) -> Stage3CanaryReport:
    defaults = {
        "generated_at": "2026-05-26T12:00:00", "since": "2026-05-26T00:00:00",
        "until": "2026-05-26T12:00:00", "environment": "test",
        "duration_minutes": 720, "canary_user_count": 2,
        "canary_payload_count": 30, "canary_allowed_count": 25,
        "canary_blocked_count": 5, "non_canary_attempts": 10,
        "non_canary_blocked": 10,
        "block_reason_counts": {"non_canary_user": 10, "stop_signal": 3},
        "risk_counts": {"low": 20, "medium": 10},
        "public_safety": Stage3PublicSafetyMetrics(),
        "health_status": "green",
    }
    defaults.update(kw)
    return Stage3CanaryReport(**defaults)


class TestPassClean:
    def test_clean_passes(self):
        assert svc.evaluate_pass_fail(_report()).passed is True

    def test_no_failures(self):
        assert svc.evaluate_pass_fail(_report()).failures == []


class TestPassFailPublicSafety:
    def test_public_send(self):
        pf = svc.evaluate_pass_fail(_report(
            public_safety=Stage3PublicSafetyMetrics(public_user_send_count=1),
        ))
        assert not pf.passed

    def test_non_canary_allowed(self):
        pf = svc.evaluate_pass_fail(_report(
            public_safety=Stage3PublicSafetyMetrics(non_canary_allowed_count=1),
        ))
        assert not pf.passed

    def test_high_risk_sent(self):
        pf = svc.evaluate_pass_fail(_report(
            public_safety=Stage3PublicSafetyMetrics(high_risk_sent_count=1),
        ))
        assert not pf.passed

    def test_critical_sent(self):
        pf = svc.evaluate_pass_fail(_report(
            public_safety=Stage3PublicSafetyMetrics(critical_risk_sent_count=1),
        ))
        assert not pf.passed

    def test_duplicate_sent(self):
        pf = svc.evaluate_pass_fail(_report(
            public_safety=Stage3PublicSafetyMetrics(duplicate_sent_count=1),
        ))
        assert not pf.passed

    def test_sensitive_leak(self):
        pf = svc.evaluate_pass_fail(_report(
            public_safety=Stage3PublicSafetyMetrics(sensitive_leak_count=1),
        ))
        assert not pf.passed

    def test_all_zero_passes(self):
        assert svc.evaluate_pass_fail(_report(
            public_safety=Stage3PublicSafetyMetrics(),
        )).passed is True


class TestHealthBlocker:
    def test_red_fails(self):
        assert not svc.evaluate_pass_fail(_report(health_status="red")).passed

    def test_green_passes(self):
        assert svc.evaluate_pass_fail(_report(health_status="green")).passed


class TestWarnings:
    def test_no_canary_sends(self):
        pf = svc.evaluate_pass_fail(_report(canary_payload_count=0))
        assert "no_canary_sends" in pf.warnings


class TestRecommendations:
    def test_fail_public(self):
        r = _report(public_safety=Stage3PublicSafetyMetrics(public_user_send_count=1))
        pf = svc.evaluate_pass_fail(r)
        recs = svc.build_recommendations(r, pf)
        assert any("rollback" in rec.lower() for rec in recs)

    def test_fail_generic(self):
        r = _report(health_status="red")
        pf = svc.evaluate_pass_fail(r)
        recs = svc.build_recommendations(r, pf)
        assert any("fail" in rec.lower() or "rollback" in rec.lower() for rec in recs)

    def test_no_sends_continue(self):
        r = _report(canary_payload_count=0)
        pf = svc.evaluate_pass_fail(r)
        recs = svc.build_recommendations(r, pf)
        assert any("continue" in rec.lower() for rec in recs)

    def test_enough_sends_approval(self):
        r = _report(canary_payload_count=25)
        pf = svc.evaluate_pass_fail(r)
        recs = svc.build_recommendations(r, pf)
        assert any("approval" in rec.lower() or "stage 4" in rec.lower() for rec in recs)

    def test_few_sends_continue(self):
        r = _report(canary_payload_count=5)
        pf = svc.evaluate_pass_fail(r)
        recs = svc.build_recommendations(r, pf)
        assert any("continue" in rec.lower() for rec in recs)


class TestDefaults:
    def test_empty_report(self):
        r = Stage3CanaryReport()
        assert r.canary_payload_count == 0
        assert r.pass_fail.passed is True

    def test_public_safety_defaults(self):
        ps = Stage3PublicSafetyMetrics()
        assert ps.public_user_send_count == 0

    def test_frozen(self):
        import pytest
        r = Stage3CanaryReport()
        with pytest.raises(AttributeError):
            r.health_status = "red"  # type: ignore[misc]


class TestDBService:
    async def test_empty_db(self):
        from datetime import UTC, datetime, timedelta
        from unittest.mock import AsyncMock, MagicMock
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar=MagicMock(return_value=0)),
        )
        s = Stage3CanaryReportService(session)
        now = datetime.now(UTC)
        r = await s.build_report(now - timedelta(hours=1), now)
        assert r.canary_payload_count == 0
        assert r.pass_fail.passed is True

    async def test_db_error(self):
        from datetime import UTC, datetime, timedelta
        from unittest.mock import AsyncMock
        session = AsyncMock()
        session.execute = AsyncMock(side_effect=Exception("DB"))
        s = Stage3CanaryReportService(session)
        now = datetime.now(UTC)
        r = await s.build_report(now - timedelta(hours=1), now)
        assert r.canary_payload_count == 0

    async def test_generated_at(self):
        from datetime import UTC, datetime, timedelta
        from unittest.mock import AsyncMock, MagicMock
        session = AsyncMock()
        session.execute = AsyncMock(
            return_value=MagicMock(scalar=MagicMock(return_value=0)),
        )
        s = Stage3CanaryReportService(session)
        now = datetime.now(UTC)
        r = await s.build_report(now - timedelta(hours=2), now)
        assert r.generated_at != ""
        assert r.duration_minutes == 120


class TestNoSecrets:
    def test_clean(self):
        from dataclasses import asdict
        assert "sk-" not in str(asdict(Stage3CanaryReport()))
