"""Tests for Step AE — Control Center Polish + Operator UX."""
from __future__ import annotations

from pathlib import Path

_TEMPLATE = Path("apps/web/templates/agent.html").read_text(encoding="utf-8")


class TestAgentStatusHeader:
    def test_header_renders(self):
        assert "agentStatusHeader" in _TEMPLATE

    def test_stage_badge(self):
        assert "Stage:" in _TEMPLATE

    def test_health_badge(self):
        assert "Health:" in _TEMPLATE

    def test_mutation_status(self):
        assert "Mutation:" in _TEMPLATE

    def test_runtime_status(self):
        assert "Runtime:" in _TEMPLATE

    def test_live_sender_status(self):
        assert "Live Sender:" in _TEMPLATE

    def test_pending_count(self):
        assert "Pending:" in _TEMPLATE


class TestOperatorStatusCards:
    def test_cards_container(self):
        assert "operatorStatusCards" in _TEMPLATE

    def test_brain_card(self):
        assert "Agent Brain" in _TEMPLATE

    def test_followups_card(self):
        assert "Follow-ups" in _TEMPLATE

    def test_safety_card(self):
        assert "Safety" in _TEMPLATE

    def test_approval_card(self):
        assert "Approval Queue" in _TEMPLATE

    def test_metrics_card(self):
        assert "Metrics" in _TEMPLATE

    def test_settings_card(self):
        assert "Settings" in _TEMPLATE


class TestStageTimeline:
    def test_timeline_container(self):
        assert "stageTimeline" in _TEMPLATE

    def test_all_stages_present(self):
        assert "OFF" in _TEMPLATE
        assert "LOG ONLY" in _TEMPLATE
        assert "DRY RUN" in _TEMPLATE
        assert "CANARY" in _TEMPLATE
        assert "APPROVAL" in _TEMPLATE
        assert "LIVE SEND" in _TEMPLATE
        assert "LIMITED LIVE" in _TEMPLATE

    def test_current_stage_marker(self):
        assert "is_current" in _TEMPLATE

    def test_stage_warning(self):
        assert "stageWarning" in _TEMPLATE

    def test_dangerous_stages_styled(self):
        assert "critical" in _TEMPLATE.lower()

    def test_arrows_between_stages(self):
        assert "→" in _TEMPLATE

    def test_rollout_bosqichlari_label(self):
        assert "Rollout Bosqichlari" in _TEMPLATE


class TestApprovalQueue:
    def test_empty_state(self):
        assert "emptyApprovalQueue" in _TEMPLATE

    def test_empty_message(self):
        assert "Tasdiq kutayotgan actionlar yo" in _TEMPLATE

    def test_approve_button(self):
        assert "Tasdiqlash" in _TEMPLATE

    def test_reject_button(self):
        assert "Rad etish" in _TEMPLATE

    def test_risk_badges(self):
        assert "risk_level" in _TEMPLATE


class TestSettingsControl:
    def test_settings_table(self):
        assert "settingsTable" in _TEMPLATE

    def test_source_badges(self):
        assert "source" in _TEMPLATE.lower()

    def test_risk_badges(self):
        assert "risk" in _TEMPLATE.lower()

    def test_mutation_banner(self):
        assert "settingsMutationBanner" in _TEMPLATE


class TestSafetyPanel:
    def test_blockers_render(self):
        assert "BLOCKER" in _TEMPLATE

    def test_warnings_render(self):
        assert "WARNING" in _TEMPLATE

    def test_all_safe_badge(self):
        assert "All safe" in _TEMPLATE


class TestAuditLog:
    def test_audit_section(self):
        assert "auditLog" in _TEMPLATE

    def test_rollback_button(self):
        assert "rollbackSetting" in _TEMPLATE


class TestSecurity:
    def test_no_raw_token(self):
        assert "confirmation_token_hash" not in _TEMPLATE

    def test_no_raw_phone(self):
        assert "+998" not in _TEMPLATE

    def test_no_api_key(self):
        assert "api_key" not in _TEMPLATE.lower()

    def test_no_bot_token(self):
        assert "bot_token" not in _TEMPLATE.lower()


class TestErrorStates:
    def test_api_error_container(self):
        assert "apiErrorContainer" in _TEMPLATE

    def test_loading_container(self):
        assert "loadingContainer" in _TEMPLATE

    def test_error_text(self):
        assert "apiErrorText" in _TEMPLATE


class TestPresets:
    def test_preset_diff_panel(self):
        assert "presetDiff" in _TEMPLATE

    def test_preset_message(self):
        assert "presetMessage" in _TEMPLATE


class TestUzbekLabels:
    def test_uzbek_labels(self):
        assert "Rollout Bosqichlari" in _TEMPLATE
        assert "Oxirgi" in _TEMPLATE

    def test_refresh_link(self):
        assert "Yangilash" in _TEMPLATE


class TestResponsive:
    def test_grid_layout(self):
        assert "grid" in _TEMPLATE.lower()

    def test_flex_wrap(self):
        assert "flex-wrap" in _TEMPLATE


class TestRecommendedNextStage:
    def test_helper_exists(self):
        from core.services.agent_control_center_service import (
            AgentControlCenterService,
        )
        assert AgentControlCenterService.recommend_next_stage("off") == "log_only"

    def test_log_only_to_dry_run(self):
        from core.services.agent_control_center_service import (
            AgentControlCenterService,
        )
        assert AgentControlCenterService.recommend_next_stage("log_only") == "dry_run"

    def test_dry_run_to_canary(self):
        from core.services.agent_control_center_service import (
            AgentControlCenterService,
        )
        assert AgentControlCenterService.recommend_next_stage("dry_run") == "canary"

    def test_canary_to_approval(self):
        from core.services.agent_control_center_service import (
            AgentControlCenterService,
        )
        assert AgentControlCenterService.recommend_next_stage("canary") == "approval_required"

    def test_live_send_no_next(self):
        from core.services.agent_control_center_service import (
            AgentControlCenterService,
        )
        assert AgentControlCenterService.recommend_next_stage("approved_live_send") is None

    def test_unknown_defaults_off(self):
        from core.services.agent_control_center_service import (
            AgentControlCenterService,
        )
        assert AgentControlCenterService.recommend_next_stage("unknown") == "off"

    def test_no_secrets(self):
        from core.services.agent_control_center_service import (
            AgentControlCenterService,
        )
        result = AgentControlCenterService.recommend_next_stage("off")
        assert "sk-" not in str(result)
