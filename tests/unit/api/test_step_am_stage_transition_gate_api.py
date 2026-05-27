"""Tests for Step AM — Stage Transition Gate API."""

from __future__ import annotations

from dataclasses import asdict

from core.schemas.stage_transition_gate import StageTransitionGateResult


class TestEndpoint:
    def test_gate_endpoint_exists(self):
        from apps.api.main import create_app

        app = create_app()
        paths = [r.path for r in app.routes]
        assert any("dryrun-gate" in p for p in paths)

    def test_router_has_auth(self):
        from apps.api.routes.admin_agent_observation import router

        assert len(router.dependencies) > 0


class TestResponseShape:
    def test_serializable(self):
        r = StageTransitionGateResult()
        d = asdict(r)
        assert "verdict" in d
        assert "readiness_score" in d
        assert "blockers" in d
        assert "warnings" in d
        assert "recommendations" in d

    def test_no_secrets(self):
        r = StageTransitionGateResult()
        text = str(asdict(r))
        assert "sk-" not in text
        assert "+998" not in text

    def test_defaults(self):
        r = StageTransitionGateResult()
        assert r.verdict == "not_ready"
        assert r.readiness_score == 0


class TestNonRegression:
    def test_report_endpoint_exists(self):
        from apps.api.main import create_app

        app = create_app()
        paths = [r.path for r in app.routes]
        assert any("stage1-report" in p for p in paths)

    def test_signal_works(self):
        from core.services.lead_signal_service import LeadSignalService

        sig = LeadSignalService.extract_signals("narxi qancha")
        assert sig.intent == "wants_price"

    def test_orchestrator_works(self):
        from core.services.agent_response_orchestrator import AgentResponseOrchestrator

        mem = {
            "followup_enabled": True,
            "memory_data": {},
            "lead_temperature": "warm",
            "telegram_user_id": 1,
        }
        p = AgentResponseOrchestrator.run_pipeline(mem, text="narxi qancha")
        assert p.action == "send_user_reply"
