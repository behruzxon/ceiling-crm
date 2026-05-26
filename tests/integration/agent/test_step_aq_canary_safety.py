"""
Step AQ — CANARY safety integration tests.
Verifies canary-only send, non-canary blocking, and safety guarantees.
"""
from __future__ import annotations

from types import SimpleNamespace

from core.services.agent_control_center_service import AgentControlCenterService
from core.services.agent_effective_settings_service import AgentEffectiveSettingsService
from core.services.agent_execution_sandbox_service import AgentExecutionSandboxService
from core.services.agent_response_orchestrator import AgentResponseOrchestrator
from core.services.agent_rollout_preset_service import AgentRolloutPresetService


def _canary_overrides() -> dict:
    return AgentRolloutPresetService.build_preset_settings("canary")


def _canary_effective() -> AgentEffectiveSettingsService:
    s = AgentEffectiveSettingsService(_canary_overrides())
    s._runtime_enabled = True
    return s


def _mem() -> dict:
    return {"followup_enabled": True, "memory_data": {},
            "lead_temperature": "warm", "telegram_user_id": 12345}


class TestCanaryPreset:
    def test_requires_ids(self):
        r = AgentRolloutPresetService.preview_preset("canary", {})
        assert not r.allowed

    def test_with_ids_allowed(self):
        r = AgentRolloutPresetService.preview_preset("canary", {
            "agent_execution_canary_user_ids": "123",
        })
        assert r.allowed

    def test_mode_canary(self):
        s = _canary_effective()
        assert s.get_execution_settings().execution_mode == "canary"

    def test_sandbox_enabled(self):
        s = _canary_effective()
        assert s.get_execution_settings().sandbox_enabled is True

    def test_live_sender_disabled(self):
        s = _canary_effective()
        assert s.get_execution_settings().live_sender_enabled is False

    def test_auto_execute_disabled(self):
        s = _canary_effective()
        assert s.get_execution_settings().auto_execute_approved is False


class TestCanarySandbox:
    def test_canary_user_allowed(self):
        ex = AgentExecutionSandboxService.prepare_execution(
            {"action": "send_user_reply", "channel": "user_dm",
             "user_message_text": "Salom!", "target_user_id": 111},
            {"followup_enabled": True, "lead_temperature": "warm",
             "followup_count": 0, "memory_data": {}, "telegram_user_id": 111},
            "canary",
        )
        r = AgentExecutionSandboxService.validate_execution(
            ex, {"followup_enabled": True, "lead_temperature": "warm",
                 "followup_count": 0, "memory_data": {}},
            canary_user_ids=[111],
        )
        assert r.would_execute is True

    def test_non_canary_blocked(self):
        ex = AgentExecutionSandboxService.prepare_execution(
            {"action": "send_user_reply", "channel": "user_dm",
             "user_message_text": "Salom!", "target_user_id": 999},
            {"followup_enabled": True, "lead_temperature": "warm",
             "followup_count": 0, "memory_data": {}, "telegram_user_id": 999},
            "canary",
        )
        r = AgentExecutionSandboxService.validate_execution(
            ex, {"followup_enabled": True, "lead_temperature": "warm",
                 "followup_count": 0, "memory_data": {}},
            canary_user_ids=[111],
        )
        assert r.blocked is True
        assert r.blocked_reason == "non_canary_user"

    def test_token_blocked(self):
        ex = AgentExecutionSandboxService.prepare_execution(
            {"action": "send_user_reply", "channel": "user_dm",
             "user_message_text": "sk-secret", "target_user_id": 111},
            {"followup_enabled": True, "lead_temperature": "warm",
             "followup_count": 0, "memory_data": {}},
            "canary",
        )
        r = AgentExecutionSandboxService.validate_execution(
            ex, {"followup_enabled": True, "lead_temperature": "warm",
                 "followup_count": 0, "memory_data": {}},
            canary_user_ids=[111],
        )
        assert r.blocked is True

    def test_phone_blocked(self):
        ex = AgentExecutionSandboxService.prepare_execution(
            {"action": "send_user_reply", "channel": "user_dm",
             "user_message_text": "+998901234567", "target_user_id": 111},
            {"followup_enabled": True, "lead_temperature": "warm",
             "followup_count": 0, "memory_data": {}},
            "canary",
        )
        r = AgentExecutionSandboxService.validate_execution(
            ex, {"followup_enabled": True, "lead_temperature": "warm",
                 "followup_count": 0, "memory_data": {}},
            canary_user_ids=[111],
        )
        assert r.blocked is True

    def test_fake_discount_blocked(self):
        ex = AgentExecutionSandboxService.prepare_execution(
            {"action": "send_user_reply", "channel": "user_dm",
             "user_message_text": "20% chegirma!", "target_user_id": 111},
            {"followup_enabled": True, "lead_temperature": "warm",
             "followup_count": 0, "memory_data": {}},
            "canary",
        )
        r = AgentExecutionSandboxService.validate_execution(
            ex, {"followup_enabled": True, "lead_temperature": "warm",
                 "followup_count": 0, "memory_data": {}},
            canary_user_ids=[111],
        )
        assert r.blocked is True

    def test_high_risk_blocked(self):
        ex = AgentExecutionSandboxService.prepare_execution(
            {"action": "send_user_reply", "channel": "user_dm",
             "user_message_text": "test", "target_user_id": 111},
            {"followup_enabled": True, "lead_temperature": "warm",
             "followup_count": 5, "memory_data": {}},
            "canary",
        )
        r = AgentExecutionSandboxService.validate_execution(
            ex, {"followup_enabled": True, "lead_temperature": "warm",
                 "followup_count": 5, "memory_data": {}},
            canary_user_ids=[111],
        )
        assert r.blocked is True


class TestStageDetection:
    def test_canary_detected(self):
        overrides = _canary_overrides()
        biz = SimpleNamespace(**{**overrides, **{
            "agent_execution_canary_user_ids": "123",
            "agent_execution_approval_admin_notify": False,
            "agent_execution_max_daily_per_user": 3,
            "agent_execution_live_sender_batch_limit": 10,
        }})
        assert AgentControlCenterService.detect_rollout_stage(biz).stage == "canary"


class TestRollbackOFF:
    def test_off_safe(self):
        off = AgentRolloutPresetService.build_preset_settings("off")
        s = AgentEffectiveSettingsService(off)
        s._runtime_enabled = True
        e = s.get_execution_settings()
        assert e.sandbox_enabled is False
        assert e.live_sender_enabled is False


class TestPipeline:
    def test_orchestrator_produces_trace(self):
        p = AgentResponseOrchestrator.run_pipeline(_mem(), text="20 kv qancha")
        assert p.debug_trace is not None


class TestNoSecrets:
    def test_no_raw_ids_in_snapshot(self):
        from dataclasses import asdict
        s = _canary_effective()
        snap = s.get_agent_settings_snapshot()
        text = str(asdict(snap))
        assert "bot_token" not in text.lower()
