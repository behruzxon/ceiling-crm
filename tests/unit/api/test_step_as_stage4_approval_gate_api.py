"""Tests for Step AS — APPROVAL Gate API."""
from __future__ import annotations

from dataclasses import asdict

from core.schemas.stage4_approval_readiness import Stage4ApprovalReadinessResult


class TestEndpoint:
    def test_exists(self):
        from apps.api.main import create_app
        assert any("approval-gate" in r.path for r in create_app().routes)

    def test_auth(self):
        from apps.api.routes.admin_agent_observation import router
        assert len(router.dependencies) > 0

class TestResponse:
    def test_serializable(self):
        d = asdict(Stage4ApprovalReadinessResult())
        assert "verdict" in d and "readiness_score" in d and "blockers" in d

    def test_no_secrets(self):
        assert "sk-" not in str(asdict(Stage4ApprovalReadinessResult()))

    def test_defaults(self):
        assert Stage4ApprovalReadinessResult().verdict == "not_ready"

class TestNonRegression:
    def test_canary_report(self):
        from apps.api.main import create_app
        assert any("canary-report" in r.path for r in create_app().routes)

    def test_canary_gate(self):
        from apps.api.main import create_app
        assert any("canary-gate" in r.path for r in create_app().routes)

    def test_signal(self):
        from core.services.lead_signal_service import LeadSignalService
        assert LeadSignalService.extract_signals("narxi qancha").intent == "wants_price"
