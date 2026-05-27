"""
Step AN — DRY_RUN No-Send Guarantee Tests.

Verifies DRY_RUN preset never triggers real sends, follow-ups,
or admin escalations. Sandbox validates but does not execute.
"""

from __future__ import annotations

from types import SimpleNamespace

from core.services.agent_control_center_service import AgentControlCenterService
from core.services.agent_effective_settings_service import AgentEffectiveSettingsService
from core.services.agent_execution_sandbox_service import AgentExecutionSandboxService
from core.services.agent_response_orchestrator import AgentResponseOrchestrator
from core.services.agent_rollout_preset_service import AgentRolloutPresetService


def _dryrun_overrides() -> dict:
    return AgentRolloutPresetService.build_preset_settings("dry_run")


def _dryrun_effective() -> AgentEffectiveSettingsService:
    s = AgentEffectiveSettingsService(_dryrun_overrides())
    s._runtime_enabled = True
    return s


def _mem() -> dict:
    return {
        "followup_enabled": True,
        "memory_data": {},
        "lead_temperature": "warm",
        "telegram_user_id": 12345,
    }


class TestDryRunFlags:
    def test_sandbox_enabled(self):
        s = _dryrun_effective()
        assert s.get_execution_settings().sandbox_enabled is True

    def test_mode_dry_run(self):
        s = _dryrun_effective()
        assert s.get_execution_settings().execution_mode == "dry_run"

    def test_live_sender_disabled(self):
        s = _dryrun_effective()
        assert s.get_execution_settings().live_sender_enabled is False

    def test_auto_execute_disabled(self):
        s = _dryrun_effective()
        assert s.get_execution_settings().auto_execute_approved is False

    def test_followups_disabled(self):
        s = _dryrun_effective()
        assert s.get_followup_settings().enabled is False

    def test_orchestrator_log_only(self):
        s = _dryrun_effective()
        assert s.get_orchestrator_settings().log_only is True


class TestPipelineNoSend:
    def test_price_question_no_live(self):
        p = AgentResponseOrchestrator.run_pipeline(_mem(), text="20 kv qancha")
        assert p.action in ("send_user_reply", "store_memory_only")
        assert "source" in p.debug_trace

    def test_objection_no_live(self):
        p = AgentResponseOrchestrator.run_pipeline(_mem(), text="qimmat ekan")
        assert p.debug_trace is not None

    def test_stop_blocks(self):
        p = AgentResponseOrchestrator.run_pipeline(_mem(), text="kerak emas")
        assert p.action == "disable_agent"

    def test_operator_no_live(self):
        p = AgentResponseOrchestrator.run_pipeline(_mem(), text="operator kerak")
        assert p.debug_trace is not None


class TestSandboxBlocking:
    def test_high_risk_user_dm_blocked(self):
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
            "dry_run",
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

    def test_token_blocked(self):
        ex = AgentExecutionSandboxService.prepare_execution(
            {
                "action": "send_user_reply",
                "channel": "user_dm",
                "user_message_text": "sk-secret123",
                "target_user_id": 123,
            },
            {
                "followup_enabled": True,
                "lead_temperature": "warm",
                "followup_count": 0,
                "memory_data": {},
            },
            "dry_run",
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
                "user_message_text": "Call +998901234567",
                "target_user_id": 123,
            },
            {
                "followup_enabled": True,
                "lead_temperature": "warm",
                "followup_count": 0,
                "memory_data": {},
            },
            "dry_run",
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
            "dry_run",
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

    def test_same_day_blocked(self):
        ex = AgentExecutionSandboxService.prepare_execution(
            {
                "action": "send_user_reply",
                "channel": "user_dm",
                "user_message_text": "Bugun qilamiz!",
                "target_user_id": 123,
            },
            {
                "followup_enabled": True,
                "lead_temperature": "warm",
                "followup_count": 0,
                "memory_data": {},
            },
            "dry_run",
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

    def test_safe_message_would_execute(self):
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
            "dry_run",
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
        assert r.would_execute is True
        assert r.blocked is False


class TestStageDetection:
    def test_dry_run_detected(self):
        overrides = _dryrun_overrides()
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
        stage = AgentControlCenterService.detect_rollout_stage(biz)
        assert stage.stage == "dry_run"


class TestRollbackOFF:
    def test_off_safe(self):
        off = AgentRolloutPresetService.build_preset_settings("off")
        s = AgentEffectiveSettingsService(off)
        s._runtime_enabled = True
        e = s.get_execution_settings()
        assert e.sandbox_enabled is False
        assert e.live_sender_enabled is False


class TestNoSecrets:
    def test_trace_no_secrets(self):
        from dataclasses import asdict

        s = _dryrun_effective()
        snap = s.get_agent_settings_snapshot()
        text = str(asdict(snap))
        assert "sk-" not in text
        assert "bot_token" not in text.lower()
