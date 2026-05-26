"""Tests for Step AA — AgentEffectiveSettingsService."""
from __future__ import annotations

import pytest

from core.schemas.agent_effective_settings import (
    AgentAIComposerSettings,
    AgentAdminEscalationSettings,
    AgentDecisionSettings,
    AgentEffectiveSettingsSnapshot,
    AgentExecutionSettings,
    AgentFollowupSettings,
    AgentOrchestratorSettings,
)
from core.services.agent_effective_settings_service import (
    AgentEffectiveSettingsService,
)

svc_cls = AgentEffectiveSettingsService


def _svc(overrides: dict | None = None, runtime_enabled: bool = True):
    s = AgentEffectiveSettingsService(overrides or {})
    s._runtime_enabled = runtime_enabled
    return s


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Runtime disabled → env/default
# ═══════════════════════════════════════════════════════════════════════════════


class TestRuntimeDisabled:
    def test_disabled_uses_env(self):
        s = _svc({"agent_followups_enabled": True}, runtime_enabled=False)
        val, src = s.get_bool("agent_followups_enabled")
        assert src != "runtime"

    def test_disabled_default_fallback(self):
        s = _svc({}, runtime_enabled=False)
        val, src = s.get_bool("nonexistent_key")
        assert val is False
        assert src == "default"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. Runtime enabled + overrides
# ═══════════════════════════════════════════════════════════════════════════════


class TestRuntimeOverrides:
    def test_bool_override_wins(self):
        s = _svc({"agent_followups_enabled": True})
        val, src = s.get_bool("agent_followups_enabled")
        assert val is True
        assert src == "runtime"

    def test_int_override_wins(self):
        s = _svc({"agent_catalog_followup_delay_minutes": 5})
        val, src = s.get_int("agent_catalog_followup_delay_minutes", 10)
        assert val == 5
        assert src == "runtime"

    def test_str_override_wins(self):
        s = _svc({"agent_execution_mode": "canary"})
        val, src = s.get_str("agent_execution_mode", "log_only")
        assert val == "canary"
        assert src == "runtime"

    def test_no_override_falls_to_env(self):
        s = _svc({})
        val, src = s.get_bool("agent_followups_enabled")
        assert src in ("env", "default")

    def test_bool_str_coercion(self):
        s = _svc({"agent_followups_enabled": "true"})
        val, src = s.get_bool("agent_followups_enabled")
        assert val is True

    def test_int_str_coercion(self):
        s = _svc({"agent_catalog_followup_delay_minutes": "15"})
        val, _ = s.get_int("agent_catalog_followup_delay_minutes", 10)
        assert val == 15


# ═══════════════════════════════════════════════════════════════════════════════
# 3. Invalid values
# ═══════════════════════════════════════════════════════════════════════════════


class TestInvalidValues:
    def test_invalid_bool_ignored(self):
        s = _svc({"agent_followups_enabled": "maybe"})
        val, src = s.get_bool("agent_followups_enabled", False)
        assert val is False
        assert src == "default"

    def test_invalid_int_ignored(self):
        s = _svc({"agent_catalog_followup_delay_minutes": "abc"})
        val, src = s.get_int("agent_catalog_followup_delay_minutes", 10)
        assert val == 10
        assert src == "default"

    def test_none_value_default(self):
        s = _svc({"agent_followups_enabled": None})
        val, src = s.get_bool("agent_followups_enabled", False)
        assert src in ("env", "default")


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Followup settings snapshot
# ═══════════════════════════════════════════════════════════════════════════════


class TestFollowupSettings:
    def test_defaults(self):
        s = _svc({}, runtime_enabled=False)
        f = s.get_followup_settings()
        assert isinstance(f, AgentFollowupSettings)
        assert f.enabled is False

    def test_runtime_override(self):
        s = _svc({
            "agent_followups_enabled": True,
            "agent_catalog_followup_enabled": True,
            "agent_catalog_followup_delay_minutes": 5,
        })
        f = s.get_followup_settings()
        assert f.enabled is True
        assert f.catalog_enabled is True
        assert f.catalog_delay_minutes == 5

    def test_partial_override(self):
        s = _svc({"agent_followups_enabled": True})
        f = s.get_followup_settings()
        assert f.enabled is True
        assert f.catalog_delay_minutes == 10  # default

    def test_max_daily_default(self):
        s = _svc({})
        f = s.get_followup_settings()
        assert f.max_daily_per_user == 3


# ═══════════════════════════════════════════════════════════════════════════════
# 5. AI Composer settings
# ═══════════════════════════════════════════════════════════════════════════════


class TestAIComposerSettings:
    def test_defaults(self):
        s = _svc({})
        a = s.get_ai_composer_settings()
        assert a.enabled is False
        assert a.model == "gpt-4o-mini"

    def test_model_override(self):
        s = _svc({"agent_ai_composer_model": "gpt-4o"})
        a = s.get_ai_composer_settings()
        assert a.model == "gpt-4o"

    def test_timeout_override(self):
        s = _svc({"agent_ai_composer_timeout_seconds": 15})
        a = s.get_ai_composer_settings()
        assert a.timeout_seconds == 15


# ═══════════════════════════════════════════════════════════════════════════════
# 6. Decision settings
# ═══════════════════════════════════════════════════════════════════════════════


class TestDecisionSettings:
    def test_defaults(self):
        s = _svc({})
        d = s.get_decision_settings()
        assert d.decision_enabled is False
        assert d.min_confidence == 60

    def test_all_enabled(self):
        s = _svc({
            "agent_decision_engine_enabled": True,
            "agent_lead_signal_enabled": True,
            "agent_dynamic_offer_enabled": True,
            "agent_conversation_policy_enabled": True,
        })
        d = s.get_decision_settings()
        assert d.decision_enabled is True
        assert d.lead_signal_enabled is True
        assert d.dynamic_offer_enabled is True


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Execution settings
# ═══════════════════════════════════════════════════════════════════════════════


class TestExecutionSettings:
    def test_defaults(self):
        s = _svc({})
        e = s.get_execution_settings()
        assert e.sandbox_enabled is False
        assert e.execution_mode == "log_only"
        assert e.live_sender_enabled is False

    def test_mode_override(self):
        s = _svc({"agent_execution_mode": "canary"})
        e = s.get_execution_settings()
        assert e.execution_mode == "canary"

    def test_live_sender_default_off(self):
        s = _svc({})
        e = s.get_execution_settings()
        assert e.live_sender_enabled is False

    def test_auto_execute_default_off(self):
        s = _svc({})
        e = s.get_execution_settings()
        assert e.auto_execute_approved is False

    def test_batch_limit_default(self):
        s = _svc({})
        e = s.get_execution_settings()
        assert e.batch_limit == 10


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Orchestrator settings
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrchestratorSettings:
    def test_defaults(self):
        s = _svc({})
        o = s.get_orchestrator_settings()
        assert o.enabled is False
        assert o.log_only is True

    def test_override(self):
        s = _svc({
            "agent_response_orchestrator_enabled": True,
            "agent_response_orchestrator_log_only": False,
        })
        o = s.get_orchestrator_settings()
        assert o.enabled is True
        assert o.log_only is False


# ═══════════════════════════════════════════════════════════════════════════════
# 9. Admin escalation settings
# ═══════════════════════════════════════════════════════════════════════════════


class TestAdminEscalationSettings:
    def test_defaults(self):
        s = _svc({})
        a = s.get_admin_escalation_settings()
        assert a.enabled is False
        assert a.after_followups == 2
        assert a.cooldown_minutes == 60

    def test_override(self):
        s = _svc({
            "agent_admin_escalation_enabled": True,
            "agent_admin_escalation_after_followups": 3,
        })
        a = s.get_admin_escalation_settings()
        assert a.enabled is True
        assert a.after_followups == 3


# ═══════════════════════════════════════════════════════════════════════════════
# 10. Full snapshot
# ═══════════════════════════════════════════════════════════════════════════════


class TestFullSnapshot:
    def test_snapshot_has_all_sections(self):
        s = _svc({})
        snap = s.get_agent_settings_snapshot()
        assert isinstance(snap, AgentEffectiveSettingsSnapshot)
        assert snap.followup is not None
        assert snap.ai_composer is not None
        assert snap.decision is not None
        assert snap.execution is not None
        assert snap.orchestrator is not None
        assert snap.escalation is not None

    def test_snapshot_sources_tracked(self):
        s = _svc({"agent_followups_enabled": True})
        snap = s.get_agent_settings_snapshot()
        src_keys = [ss.key for ss in snap.sources]
        assert "agent_followups_enabled" in src_keys

    def test_snapshot_no_secrets(self):
        from dataclasses import asdict
        s = _svc({"agent_followups_enabled": True})
        snap = s.get_agent_settings_snapshot()
        text = str(asdict(snap))
        assert "api_key" not in text.lower()
        assert "bot_token" not in text.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# 11. Cache
# ═══════════════════════════════════════════════════════════════════════════════


class TestCache:
    def test_clear_cache(self):
        AgentEffectiveSettingsService.clear_cache()

    def test_cache_clears_without_error(self):
        from core.services.agent_effective_settings_service import _CACHE
        AgentEffectiveSettingsService.clear_cache()
        from core.services.agent_effective_settings_service import _CACHE as c
        assert c == {}


# ═══════════════════════════════════════════════════════════════════════════════
# 12. Source tracking
# ═══════════════════════════════════════════════════════════════════════════════


class TestSourceTracking:
    def test_runtime_source(self):
        s = _svc({"agent_followups_enabled": True})
        _, src = s.get_bool("agent_followups_enabled")
        assert src == "runtime"

    def test_env_source(self):
        s = _svc({})
        _, src = s.get_bool("agent_followups_enabled")
        assert src in ("env", "default")

    def test_default_source_unknown_key(self):
        s = _svc({})
        _, src = s.get_bool("nonexistent_agent_flag")
        assert src == "default"


# ═══════════════════════════════════════════════════════════════════════════════
# 13. Immutability
# ═══════════════════════════════════════════════════════════════════════════════


class TestImmutability:
    def test_followup_frozen(self):
        s = _svc({})
        f = s.get_followup_settings()
        with pytest.raises(AttributeError):
            f.enabled = True  # type: ignore[misc]

    def test_snapshot_frozen(self):
        s = _svc({})
        snap = s.get_agent_settings_snapshot()
        with pytest.raises(AttributeError):
            snap.followup = AgentFollowupSettings()  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════════════════
# 14. DI + imports
# ═══════════════════════════════════════════════════════════════════════════════


class TestDI:
    def test_di_importable(self):
        from infrastructure.di import get_agent_effective_settings_service
        assert callable(get_agent_effective_settings_service)

    def test_service_returns_instance(self):
        from infrastructure.di import get_agent_effective_settings_service
        s = get_agent_effective_settings_service()
        assert isinstance(s, AgentEffectiveSettingsService)


# ═══════════════════════════════════════════════════════════════════════════════
# 15. Settings config
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfig:
    def test_runtime_default_false(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields[
            "agent_runtime_settings_enabled"
        ].default is False

    def test_cache_ttl_default(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields[
            "agent_runtime_settings_cache_ttl_seconds"
        ].default == 30

    def test_fail_open_default_true(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields[
            "agent_runtime_settings_fail_open_to_env"
        ].default is True


# ═══════════════════════════════════════════════════════════════════════════════
# 16. Non-regression
# ═══════════════════════════════════════════════════════════════════════════════


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

    def test_settings_service_still_works(self):
        from core.services.agent_settings_service import AgentSettingsService
        r = AgentSettingsService.validate_change("agent_followups_enabled", True)
        assert r.allowed is True

    def test_control_center_still_works(self):
        from core.services.agent_control_center_service import (
            AgentControlCenterService,
        )
        snap = AgentControlCenterService.build_control_center_snapshot(None)
        assert snap.rollout_stage.stage == "off"

    def test_sandbox_still_works(self):
        from core.services.agent_execution_sandbox_service import (
            AgentExecutionSandboxService,
        )
        assert AgentExecutionSandboxService is not None

    def test_db_loader_importable(self):
        from core.services.agent_effective_settings_service import (
            load_runtime_overrides_from_db,
        )
        assert callable(load_runtime_overrides_from_db)


# ═══════════════════════════════════════════════════════════════════════════════
# 17. Extended type coercion
# ═══════════════════════════════════════════════════════════════════════════════


class TestTypeCoercion:
    def test_bool_true_string(self):
        s = _svc({"agent_followups_enabled": "true"})
        val, _ = s.get_bool("agent_followups_enabled")
        assert val is True

    def test_bool_false_string(self):
        s = _svc({"agent_followups_enabled": "false"})
        val, _ = s.get_bool("agent_followups_enabled")
        assert val is False

    def test_bool_True_native(self):
        s = _svc({"agent_followups_enabled": True})
        val, _ = s.get_bool("agent_followups_enabled")
        assert val is True

    def test_bool_False_native(self):
        s = _svc({"agent_followups_enabled": False})
        val, _ = s.get_bool("agent_followups_enabled")
        assert val is False

    def test_int_from_string(self):
        s = _svc({"agent_catalog_followup_delay_minutes": "20"})
        val, _ = s.get_int("agent_catalog_followup_delay_minutes", 10)
        assert val == 20

    def test_int_native(self):
        s = _svc({"agent_catalog_followup_delay_minutes": 30})
        val, _ = s.get_int("agent_catalog_followup_delay_minutes", 10)
        assert val == 30

    def test_str_from_any(self):
        s = _svc({"agent_execution_mode": 123})
        val, _ = s.get_str("agent_execution_mode", "log_only")
        assert val == "123"


# ═══════════════════════════════════════════════════════════════════════════════
# 18. Edge cases per settings group
# ═══════════════════════════════════════════════════════════════════════════════


class TestFollowupEdge:
    def test_all_followups_enabled(self):
        s = _svc({
            "agent_followups_enabled": True,
            "agent_catalog_followup_enabled": True,
            "agent_price_followup_enabled": True,
            "agent_order_followup_enabled": True,
        })
        f = s.get_followup_settings()
        assert f.enabled and f.catalog_enabled and f.price_enabled and f.order_enabled

    def test_delays_override(self):
        s = _svc({
            "agent_catalog_followup_delay_minutes": 1,
            "agent_price_followup_delay_minutes": 2,
            "agent_order_followup_delay_minutes": 3,
        })
        f = s.get_followup_settings()
        assert f.catalog_delay_minutes == 1
        assert f.price_delay_minutes == 2
        assert f.order_delay_minutes == 3


class TestAIComposerEdge:
    def test_all_overrides(self):
        s = _svc({
            "agent_ai_composer_enabled": True,
            "agent_ai_composer_model": "gpt-4o",
            "agent_ai_composer_timeout_seconds": 15,
            "agent_ai_composer_max_tokens": 300,
        })
        a = s.get_ai_composer_settings()
        assert a.enabled is True
        assert a.model == "gpt-4o"
        assert a.timeout_seconds == 15
        assert a.max_tokens == 300


class TestExecutionEdge:
    def test_full_live_config(self):
        s = _svc({
            "agent_execution_sandbox_enabled": True,
            "agent_execution_mode": "live",
            "agent_execution_queue_enabled": True,
            "agent_execution_live_sender_enabled": True,
            "agent_execution_auto_execute_approved": True,
            "agent_execution_live_sender_batch_limit": 20,
        })
        e = s.get_execution_settings()
        assert e.sandbox_enabled is True
        assert e.execution_mode == "live"
        assert e.queue_enabled is True
        assert e.live_sender_enabled is True
        assert e.auto_execute_approved is True
        assert e.batch_limit == 20

    def test_canary_config(self):
        s = _svc({"agent_execution_mode": "canary"})
        e = s.get_execution_settings()
        assert e.execution_mode == "canary"


class TestOrchestratorEdge:
    def test_full_config(self):
        s = _svc({
            "agent_response_orchestrator_enabled": True,
            "agent_response_orchestrator_log_only": False,
            "agent_response_orchestrator_min_confidence": 80,
            "agent_response_orchestrator_trace_enabled": False,
        })
        o = s.get_orchestrator_settings()
        assert o.enabled is True
        assert o.log_only is False
        assert o.min_confidence == 80
        assert o.trace_enabled is False


class TestEscalationEdge:
    def test_full_config(self):
        s = _svc({
            "agent_admin_escalation_enabled": True,
            "agent_admin_escalation_after_followups": 5,
            "agent_admin_escalation_cooldown_minutes": 120,
        })
        a = s.get_admin_escalation_settings()
        assert a.enabled is True
        assert a.after_followups == 5
        assert a.cooldown_minutes == 120


# ═══════════════════════════════════════════════════════════════════════════════
# 19. Multiple overrides in snapshot
# ═══════════════════════════════════════════════════════════════════════════════


class TestMultipleOverrides:
    def test_many_overrides_tracked(self):
        overrides = {
            "agent_followups_enabled": True,
            "agent_lead_signal_enabled": True,
            "agent_execution_mode": "dry_run",
        }
        s = _svc(overrides)
        snap = s.get_agent_settings_snapshot()
        assert len(snap.sources) == 3

    def test_empty_overrides_no_sources(self):
        s = _svc({})
        snap = s.get_agent_settings_snapshot()
        assert len(snap.sources) == 0

    def test_snapshot_sources_have_runtime_label(self):
        s = _svc({"agent_followups_enabled": True})
        snap = s.get_agent_settings_snapshot()
        assert all(ss.source == "runtime" for ss in snap.sources)


# ═══════════════════════════════════════════════════════════════════════════════
# 20. Schema defaults
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchemaDefaults:
    def test_followup_defaults(self):
        f = AgentFollowupSettings()
        assert f.enabled is False
        assert f.catalog_delay_minutes == 10

    def test_ai_defaults(self):
        a = AgentAIComposerSettings()
        assert a.model == "gpt-4o-mini"

    def test_execution_defaults(self):
        e = AgentExecutionSettings()
        assert e.execution_mode == "log_only"

    def test_orchestrator_defaults(self):
        o = AgentOrchestratorSettings()
        assert o.log_only is True

    def test_escalation_defaults(self):
        a = AgentAdminEscalationSettings()
        assert a.after_followups == 2

    def test_snapshot_defaults(self):
        snap = AgentEffectiveSettingsSnapshot()
        assert snap.followup.enabled is False

    def test_decision_defaults(self):
        d = AgentDecisionSettings()
        assert d.min_confidence == 60

    def test_setting_source_defaults(self):
        from core.schemas.agent_effective_settings import SettingSource
        ss = SettingSource(key="test", value=True)
        assert ss.source == "default"


class TestGetStrEdge:
    def test_str_none_default(self):
        s = _svc({})
        val, src = s.get_str("nonexistent_key", "fallback")
        assert val == "fallback"

    def test_str_runtime(self):
        s = _svc({"agent_execution_mode": "canary"})
        val, src = s.get_str("agent_execution_mode")
        assert val == "canary"
        assert src == "runtime"

    def test_int_bool_not_confused(self):
        s = _svc({"agent_catalog_followup_delay_minutes": True})
        val, _ = s.get_int("agent_catalog_followup_delay_minutes", 10)
        assert val == 10  # bool is not valid int for this purpose

    def test_get_bool_default_true(self):
        s = _svc({}, runtime_enabled=False)
        val, _ = s.get_bool("agent_response_orchestrator_log_only", True)
        # Should get True from env or default
        assert isinstance(val, bool)

    def test_constructor_default(self):
        s = AgentEffectiveSettingsService()
        assert isinstance(s._overrides, dict)
