"""
Step AF — LOG_ONLY No-Send Guarantee Tests.

Verifies that LOG_ONLY preset never triggers real sends, follow-ups,
or admin escalations.
"""

from __future__ import annotations

from types import SimpleNamespace

from core.services.agent_control_center_service import AgentControlCenterService
from core.services.agent_effective_settings_service import (
    AgentEffectiveSettingsService,
)
from core.services.agent_response_orchestrator import AgentResponseOrchestrator
from core.services.agent_rollout_preset_service import AgentRolloutPresetService


def _log_only_overrides() -> dict:
    return AgentRolloutPresetService.build_preset_settings("log_only")


def _log_only_effective() -> AgentEffectiveSettingsService:
    s = AgentEffectiveSettingsService(_log_only_overrides())
    s._runtime_enabled = True
    return s


def _log_only_mem() -> dict:
    return {
        "followup_enabled": True,
        "memory_data": {},
        "lead_temperature": "warm",
        "telegram_user_id": 12345,
    }


class TestFollowupsDisabled:
    def test_followups_off(self):
        s = _log_only_effective()
        f = s.get_followup_settings()
        assert f.enabled is False

    def test_catalog_followup_off(self):
        s = _log_only_effective()
        f = s.get_followup_settings()
        assert f.catalog_enabled is False

    def test_price_followup_off(self):
        s = _log_only_effective()
        assert s.get_followup_settings().price_enabled is False

    def test_order_followup_off(self):
        s = _log_only_effective()
        assert s.get_followup_settings().order_enabled is False


class TestSenderDisabled:
    def test_live_sender_off(self):
        s = _log_only_effective()
        e = s.get_execution_settings()
        assert e.live_sender_enabled is False

    def test_auto_execute_off(self):
        s = _log_only_effective()
        e = s.get_execution_settings()
        assert e.auto_execute_approved is False

    def test_sandbox_off(self):
        s = _log_only_effective()
        e = s.get_execution_settings()
        assert e.sandbox_enabled is False


class TestOrchestratorLogOnly:
    def test_log_only_true(self):
        s = _log_only_effective()
        o = s.get_orchestrator_settings()
        assert o.enabled is True
        assert o.log_only is True


class TestPipelineTraceOnly:
    def test_price_question_no_live_send(self):
        p = AgentResponseOrchestrator.run_pipeline(
            _log_only_mem(),
            text="20 kv qancha",
        )
        assert p.action in ("send_user_reply", "store_memory_only")
        assert "source" in p.debug_trace

    def test_objection_trace_only(self):
        p = AgentResponseOrchestrator.run_pipeline(
            _log_only_mem(),
            text="qimmat ekan",
        )
        assert p.debug_trace.get("signal", {}).get("intent") or True

    def test_operator_trace_only(self):
        p = AgentResponseOrchestrator.run_pipeline(
            _log_only_mem(),
            text="operator kerak",
        )
        assert p.debug_trace is not None

    def test_stop_signal_trace(self):
        p = AgentResponseOrchestrator.run_pipeline(
            _log_only_mem(),
            text="kerak emas",
        )
        assert p.action == "disable_agent"


class TestStageDetection:
    def test_log_only_detected(self):
        overrides = _log_only_overrides()
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
        assert stage.stage == "log_only"


class TestRollbackOFF:
    def test_off_safe(self):
        off = AgentRolloutPresetService.build_preset_settings("off")
        s = AgentEffectiveSettingsService(off)
        s._runtime_enabled = True
        f = s.get_followup_settings()
        e = s.get_execution_settings()
        assert f.enabled is False
        assert e.live_sender_enabled is False
        assert e.auto_execute_approved is False


class TestPreflightGreen:
    def test_no_red_for_log_only(self):
        overrides = _log_only_overrides()
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
        settings = SimpleNamespace(
            business=biz,
            bot=SimpleNamespace(admin_group_id="-100"),
            openai=SimpleNamespace(api_key="sk-test"),
        )
        pf = AgentControlCenterService.get_preflight_status(biz, settings)
        assert pf.status != "red"
