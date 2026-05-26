"""Tests for Step Y — Agent Control Center API endpoint."""
from __future__ import annotations

from dataclasses import asdict

from core.services.agent_control_center_service import AgentControlCenterService


class TestAPIEndpoint:
    def test_control_status_endpoint_exists(self):
        from apps.api.main import create_app
        app = create_app()
        paths = [r.path for r in app.routes]
        assert any("control/status" in p for p in paths)

    def test_endpoint_has_auth(self):
        from apps.api.routes.admin_agent_metrics import router
        assert len(router.dependencies) > 0


class TestResponseShape:
    def test_snapshot_serializable(self):
        from types import SimpleNamespace
        settings = SimpleNamespace(
            business=SimpleNamespace(
                agent_followups_enabled=False,
                agent_catalog_followup_enabled=False,
                agent_price_followup_enabled=False,
                agent_order_followup_enabled=False,
                agent_admin_escalation_enabled=False,
                agent_ai_composer_enabled=False,
                agent_decision_engine_enabled=False,
                agent_lead_signal_enabled=False,
                agent_lead_scoring_enabled=False,
                agent_dynamic_offer_enabled=False,
                agent_conversation_policy_enabled=False,
                agent_response_orchestrator_enabled=False,
                agent_response_orchestrator_log_only=True,
                agent_execution_sandbox_enabled=False,
                agent_execution_mode="log_only",
                agent_execution_queue_enabled=False,
                agent_execution_live_sender_enabled=False,
                agent_execution_live_sender_batch_limit=10,
                agent_execution_api_approval_enabled=False,
                agent_execution_auto_execute_approved=False,
                agent_execution_canary_user_ids="",
                agent_execution_approval_admin_notify=False,
                agent_execution_max_daily_per_user=3,
            ),
            bot=SimpleNamespace(admin_group_id="-100"),
            openai=SimpleNamespace(api_key="sk-test"),
        )
        snap = AgentControlCenterService.build_control_center_snapshot(settings)
        d = asdict(snap)
        assert "rollout_stage" in d
        assert "preflight" in d
        assert "canary" in d
        assert "safety" in d
        assert "flags" in d

    def test_no_secret_in_response(self):
        from types import SimpleNamespace
        settings = SimpleNamespace(
            business=SimpleNamespace(
                agent_followups_enabled=False,
                agent_catalog_followup_enabled=False,
                agent_price_followup_enabled=False,
                agent_order_followup_enabled=False,
                agent_admin_escalation_enabled=False,
                agent_ai_composer_enabled=False,
                agent_decision_engine_enabled=False,
                agent_lead_signal_enabled=False,
                agent_lead_scoring_enabled=False,
                agent_dynamic_offer_enabled=False,
                agent_conversation_policy_enabled=False,
                agent_response_orchestrator_enabled=False,
                agent_response_orchestrator_log_only=True,
                agent_execution_sandbox_enabled=False,
                agent_execution_mode="log_only",
                agent_execution_queue_enabled=False,
                agent_execution_live_sender_enabled=False,
                agent_execution_live_sender_batch_limit=10,
                agent_execution_api_approval_enabled=False,
                agent_execution_auto_execute_approved=False,
                agent_execution_canary_user_ids="12345",
                agent_execution_approval_admin_notify=False,
                agent_execution_max_daily_per_user=3,
            ),
            bot=SimpleNamespace(admin_group_id="-100"),
            openai=SimpleNamespace(api_key="sk-secret-key-test"),
        )
        snap = AgentControlCenterService.build_control_center_snapshot(settings)
        text = str(asdict(snap))
        assert "sk-secret" not in text
        assert "12345" not in text

    def test_all_off_returns_off(self):
        from types import SimpleNamespace
        settings = SimpleNamespace(
            business=SimpleNamespace(
                agent_followups_enabled=False,
                agent_catalog_followup_enabled=False,
                agent_price_followup_enabled=False,
                agent_order_followup_enabled=False,
                agent_admin_escalation_enabled=False,
                agent_ai_composer_enabled=False,
                agent_decision_engine_enabled=False,
                agent_lead_signal_enabled=False,
                agent_lead_scoring_enabled=False,
                agent_dynamic_offer_enabled=False,
                agent_conversation_policy_enabled=False,
                agent_response_orchestrator_enabled=False,
                agent_response_orchestrator_log_only=True,
                agent_execution_sandbox_enabled=False,
                agent_execution_mode="log_only",
                agent_execution_queue_enabled=False,
                agent_execution_live_sender_enabled=False,
                agent_execution_live_sender_batch_limit=10,
                agent_execution_api_approval_enabled=False,
                agent_execution_auto_execute_approved=False,
                agent_execution_canary_user_ids="",
                agent_execution_approval_admin_notify=False,
                agent_execution_max_daily_per_user=3,
            ),
            bot=SimpleNamespace(admin_group_id="-100"),
            openai=SimpleNamespace(api_key="sk-test"),
        )
        snap = AgentControlCenterService.build_control_center_snapshot(settings)
        assert snap.rollout_stage.stage == "off"

    def test_dangerous_combo_returns_blockers(self):
        from types import SimpleNamespace
        settings = SimpleNamespace(
            business=SimpleNamespace(
                agent_followups_enabled=False,
                agent_catalog_followup_enabled=False,
                agent_price_followup_enabled=False,
                agent_order_followup_enabled=False,
                agent_admin_escalation_enabled=False,
                agent_ai_composer_enabled=False,
                agent_decision_engine_enabled=False,
                agent_lead_signal_enabled=False,
                agent_lead_scoring_enabled=False,
                agent_dynamic_offer_enabled=False,
                agent_conversation_policy_enabled=False,
                agent_response_orchestrator_enabled=False,
                agent_response_orchestrator_log_only=True,
                agent_execution_sandbox_enabled=False,
                agent_execution_mode="log_only",
                agent_execution_queue_enabled=False,
                agent_execution_live_sender_enabled=True,
                agent_execution_live_sender_batch_limit=10,
                agent_execution_api_approval_enabled=False,
                agent_execution_auto_execute_approved=True,
                agent_execution_canary_user_ids="",
                agent_execution_approval_admin_notify=False,
                agent_execution_max_daily_per_user=3,
            ),
            bot=SimpleNamespace(admin_group_id="-100"),
            openai=SimpleNamespace(api_key="sk-test"),
        )
        snap = AgentControlCenterService.build_control_center_snapshot(settings)
        assert snap.preflight.status == "red"
        assert len(snap.safety.dangerous_combos) > 0


class TestFrontendTemplate:
    def test_template_has_control_center(self):
        from pathlib import Path
        html = Path("apps/web/templates/agent.html").read_text(encoding="utf-8")
        assert "Control Center" in html

    def test_template_has_rollout_stage(self):
        from pathlib import Path
        html = Path("apps/web/templates/agent.html").read_text(encoding="utf-8")
        assert "Rollout Stage" in html

    def test_template_has_preflight(self):
        from pathlib import Path
        html = Path("apps/web/templates/agent.html").read_text(encoding="utf-8")
        assert "Preflight" in html

    def test_template_has_feature_flags(self):
        from pathlib import Path
        html = Path("apps/web/templates/agent.html").read_text(encoding="utf-8")
        assert "Feature Flags" in html

    def test_template_has_mutation_disabled(self):
        from pathlib import Path
        html = Path("apps/web/templates/agent.html").read_text(encoding="utf-8")
        assert "mutation" in html.lower()

    def test_template_no_secret_placeholders(self):
        from pathlib import Path
        html = Path("apps/web/templates/agent.html").read_text(encoding="utf-8")
        assert "api_key" not in html.lower()
        assert "bot_token" not in html.lower()


class TestNonRegression:
    def test_signal_still_works(self):
        from core.services.lead_signal_service import LeadSignalService
        sig = LeadSignalService.extract_signals("narxi qancha")
        assert sig.intent == "wants_price"

    def test_orchestrator_still_works(self):
        from core.services.agent_response_orchestrator import (
            AgentResponseOrchestrator,
        )
        mem = {"followup_enabled": True, "memory_data": {},
               "lead_temperature": "warm", "telegram_user_id": 1}
        p = AgentResponseOrchestrator.run_pipeline(mem, text="narxi qancha")
        assert p.action == "send_user_reply"
