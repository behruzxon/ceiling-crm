"""Tests for Step AR — CANARY Report API."""
from __future__ import annotations
from dataclasses import asdict
from core.schemas.stage3_canary_report import Stage3CanaryReport

class TestEndpoint:
    def test_exists(self):
        from apps.api.main import create_app
        paths = [r.path for r in create_app().routes]
        assert any("stage3-canary-report" in p for p in paths)

    def test_auth(self):
        from apps.api.routes.admin_agent_observation import router
        assert len(router.dependencies) > 0

class TestResponse:
    def test_serializable(self):
        d = asdict(Stage3CanaryReport())
        assert "pass_fail" in d and "public_safety" in d and "recommendations" in d

    def test_no_secrets(self):
        assert "sk-" not in str(asdict(Stage3CanaryReport()))

    def test_pass_fail(self):
        assert asdict(Stage3CanaryReport())["pass_fail"]["passed"] is True

class TestNonRegression:
    def test_canary_gate(self):
        from apps.api.main import create_app
        assert any("canary-gate" in r.path for r in create_app().routes)

    def test_dryrun_report(self):
        from apps.api.main import create_app
        assert any("dryrun-report" in r.path for r in create_app().routes)

    def test_signal(self):
        from core.services.lead_signal_service import LeadSignalService
        assert LeadSignalService.extract_signals("narxi qancha").intent == "wants_price"
