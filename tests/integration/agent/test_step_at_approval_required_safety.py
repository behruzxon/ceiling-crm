"""Step AT — APPROVAL_REQUIRED safety integration tests."""

from __future__ import annotations

from types import SimpleNamespace

from core.services.agent_control_center_service import AgentControlCenterService
from core.services.agent_effective_settings_service import AgentEffectiveSettingsService
from core.services.agent_execution_sandbox_service import AgentExecutionSandboxService
from core.services.agent_rollout_preset_service import AgentRolloutPresetService


def _approval_overrides():
    return AgentRolloutPresetService.build_preset_settings("approval_required")


def _approval_effective():
    s = AgentEffectiveSettingsService(_approval_overrides())
    s._runtime_enabled = True
    return s


class TestApprovalPreset:
    def test_queue_enabled(self):
        assert _approval_effective().get_execution_settings().queue_enabled is True

    def test_api_approval_enabled(self):
        assert _approval_effective().get_execution_settings().api_approval_enabled is True

    def test_mode_approval(self):
        assert _approval_effective().get_execution_settings().execution_mode == "approval_required"

    def test_live_sender_off(self):
        assert _approval_effective().get_execution_settings().live_sender_enabled is False

    def test_auto_execute_off(self):
        assert _approval_effective().get_execution_settings().auto_execute_approved is False

    def test_sandbox_enabled(self):
        assert _approval_effective().get_execution_settings().sandbox_enabled is True


class TestSandboxApproval:
    def test_safe_payload_proposed(self):
        ex = AgentExecutionSandboxService.prepare_execution(
            {
                "action": "send_user_reply",
                "channel": "user_dm",
                "user_message_text": "Salom!",
                "target_user_id": 123,
            },
            {
                "followup_enabled": True,
                "lead_temperature": "warm",
                "followup_count": 0,
                "memory_data": {},
            },
            "approval_required",
        )
        r = AgentExecutionSandboxService.validate_execution(
            ex,
            {
                "followup_enabled": True,
                "lead_temperature": "warm",
                "followup_count": 0,
                "memory_data": {},
            },
        )
        assert r.requires_approval is True
        assert r.would_execute is False

    def test_token_blocked(self):
        ex = AgentExecutionSandboxService.prepare_execution(
            {
                "action": "send_user_reply",
                "channel": "user_dm",
                "user_message_text": "sk-secret",
                "target_user_id": 123,
            },
            {
                "followup_enabled": True,
                "lead_temperature": "warm",
                "followup_count": 0,
                "memory_data": {},
            },
            "approval_required",
        )
        r = AgentExecutionSandboxService.validate_execution(
            ex,
            {
                "followup_enabled": True,
                "lead_temperature": "warm",
                "followup_count": 0,
                "memory_data": {},
            },
        )
        assert r.blocked is True

    def test_phone_blocked(self):
        ex = AgentExecutionSandboxService.prepare_execution(
            {
                "action": "send_user_reply",
                "channel": "user_dm",
                "user_message_text": "+998901234567",
                "target_user_id": 123,
            },
            {
                "followup_enabled": True,
                "lead_temperature": "warm",
                "followup_count": 0,
                "memory_data": {},
            },
            "approval_required",
        )
        r = AgentExecutionSandboxService.validate_execution(
            ex,
            {
                "followup_enabled": True,
                "lead_temperature": "warm",
                "followup_count": 0,
                "memory_data": {},
            },
        )
        assert r.blocked is True

    def test_high_risk_blocked(self):
        ex = AgentExecutionSandboxService.prepare_execution(
            {
                "action": "send_user_reply",
                "channel": "user_dm",
                "user_message_text": "test",
                "target_user_id": 123,
            },
            {
                "followup_enabled": True,
                "lead_temperature": "warm",
                "followup_count": 5,
                "memory_data": {},
            },
            "approval_required",
        )
        r = AgentExecutionSandboxService.validate_execution(
            ex,
            {
                "followup_enabled": True,
                "lead_temperature": "warm",
                "followup_count": 5,
                "memory_data": {},
            },
        )
        assert r.blocked is True

    def test_fake_discount_blocked(self):
        ex = AgentExecutionSandboxService.prepare_execution(
            {
                "action": "send_user_reply",
                "channel": "user_dm",
                "user_message_text": "20% chegirma!",
                "target_user_id": 123,
            },
            {
                "followup_enabled": True,
                "lead_temperature": "warm",
                "followup_count": 0,
                "memory_data": {},
            },
            "approval_required",
        )
        r = AgentExecutionSandboxService.validate_execution(
            ex,
            {
                "followup_enabled": True,
                "lead_temperature": "warm",
                "followup_count": 0,
                "memory_data": {},
            },
        )
        assert r.blocked is True


class TestStageDetection:
    def test_detected(self):
        overrides = _approval_overrides()
        biz = SimpleNamespace(
            **{
                **overrides,
                **{
                    "agent_execution_canary_user_ids": "",
                    "agent_execution_approval_admin_notify": False,
                    "agent_execution_max_daily_per_user": 3,
                    "agent_execution_live_sender_batch_limit": 10,
                },
            }
        )
        assert AgentControlCenterService.detect_rollout_stage(biz).stage == "approval_required"


class TestRollback:
    def test_off_safe(self):
        off = AgentRolloutPresetService.build_preset_settings("off")
        s = AgentEffectiveSettingsService(off)
        s._runtime_enabled = True
        e = s.get_execution_settings()
        assert not e.queue_enabled and not e.live_sender_enabled


class TestSenderJobNoOp:
    def test_sender_disabled(self):
        assert _approval_effective().get_execution_settings().live_sender_enabled is False

    def test_auto_execute_disabled(self):
        assert _approval_effective().get_execution_settings().auto_execute_approved is False


class TestCallbackSafety:
    def test_admin_check_exists(self):
        from apps.bot.handlers.callbacks.agent_execution_callbacks import _is_admin

        assert callable(_is_admin)


class TestQueueService:
    def test_can_execute_proposed_false(self):
        from unittest.mock import MagicMock

        from core.services.agent_execution_queue_service import AgentExecutionQueueService

        r = MagicMock()
        r.status = "proposed"
        assert AgentExecutionQueueService.can_execute(r) is False

    def test_can_execute_approved_true(self):
        from unittest.mock import MagicMock

        from core.services.agent_execution_queue_service import AgentExecutionQueueService

        r = MagicMock()
        r.status = "approved"
        assert AgentExecutionQueueService.can_execute(r) is True


class TestNoSecrets:
    def test_snapshot_clean(self):
        from dataclasses import asdict

        s = _approval_effective()
        text = str(asdict(s.get_agent_settings_snapshot()))
        assert "sk-" not in text and "bot_token" not in text.lower()
