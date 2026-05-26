"""Tests for Step AU — APPROVAL Report API."""
from __future__ import annotations
from dataclasses import asdict
from core.schemas.stage4_approval_report import Stage4ApprovalReport

class TestEndpoint:
    def test_exists(self):
        from apps.api.main import create_app
        assert any("stage4-approval-report" in r.path for r in create_app().routes)

    def test_auth(self):
        from apps.api.routes.admin_agent_observation import router
        assert len(router.dependencies) > 0

class TestResponse:
    def test_serializable(self):
        d = asdict(Stage4ApprovalReport())
        assert "pass_fail" in d and "no_send" in d and "recommendations" in d

    def test_no_secrets(self):
        assert "sk-" not in str(asdict(Stage4ApprovalReport()))

class TestNonRegression:
    def test_approval_gate(self):
        from apps.api.main import create_app
        assert any("approval-gate" in r.path for r in create_app().routes)

    def test_canary_report(self):
        from apps.api.main import create_app
        assert any("canary-report" in r.path for r in create_app().routes)

    def test_signal(self):
        from core.services.lead_signal_service import LeadSignalService
        assert LeadSignalService.extract_signals("narxi qancha").intent == "wants_price"
