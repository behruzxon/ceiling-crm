"""Tests for Step AP — CANARY Gate API."""

from __future__ import annotations

from dataclasses import asdict

from core.schemas.stage3_canary_readiness import Stage3CanaryReadinessResult


class TestEndpoint:
    def test_exists(self):
        from apps.api.main import create_app

        paths = [r.path for r in create_app().routes]
        assert any("canary-gate" in p for p in paths)

    def test_auth(self):
        from apps.api.routes.admin_agent_observation import router

        assert len(router.dependencies) > 0


class TestResponse:
    def test_serializable(self):
        d = asdict(Stage3CanaryReadinessResult())
        assert "verdict" in d and "readiness_score" in d
        assert "blockers" in d and "warnings" in d

    def test_no_secrets(self):
        assert "sk-" not in str(asdict(Stage3CanaryReadinessResult()))

    def test_defaults(self):
        r = Stage3CanaryReadinessResult()
        assert r.verdict == "not_ready"


class TestNonRegression:
    def test_dryrun_report_exists(self):
        from apps.api.main import create_app

        paths = [r.path for r in create_app().routes]
        assert any("stage2-dryrun-report" in p for p in paths)

    def test_stage1_gate_exists(self):
        from apps.api.main import create_app

        paths = [r.path for r in create_app().routes]
        assert any("dryrun-gate" in p for p in paths)

    def test_signal_works(self):
        from core.services.lead_signal_service import LeadSignalService

        assert LeadSignalService.extract_signals("narxi qancha").intent == "wants_price"
