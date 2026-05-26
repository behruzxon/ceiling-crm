"""Tests for Step AV — LIVE_SEND Gate API."""
from __future__ import annotations
from dataclasses import asdict
from core.schemas.stage5_live_send_readiness import Stage5LiveSendReadinessResult

class TestEndpoint:
    def test_exists(self):
        from apps.api.main import create_app
        assert any("live-send-gate" in r.path for r in create_app().routes)

    def test_auth(self):
        from apps.api.routes.admin_agent_observation import router
        assert len(router.dependencies) > 0

class TestResponse:
    def test_serializable(self):
        d = asdict(Stage5LiveSendReadinessResult())
        assert "verdict" in d and "readiness_score" in d and "blockers" in d

    def test_no_secrets(self):
        assert "sk-" not in str(asdict(Stage5LiveSendReadinessResult()))

    def test_defaults(self):
        assert Stage5LiveSendReadinessResult().verdict == "not_ready"

class TestNonRegression:
    def test_approval_report(self):
        from apps.api.main import create_app
        assert any("approval-report" in r.path for r in create_app().routes)

    def test_approval_gate(self):
        from apps.api.main import create_app
        assert any("approval-gate" in r.path for r in create_app().routes)

    def test_signal(self):
        from core.services.lead_signal_service import LeadSignalService
        assert LeadSignalService.extract_signals("narxi qancha").intent == "wants_price"
