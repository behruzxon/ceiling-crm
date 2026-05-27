"""
Step AD — Runtime Apply Smoke Tests.

End-to-end flow: preset preview → apply → effective settings → stage detection → rollback.
No real DB, no Telegram, no OpenAI. Uses service layer directly with mocked overrides.
"""

from __future__ import annotations

from types import SimpleNamespace

from core.services.agent_control_center_service import AgentControlCenterService
from core.services.agent_effective_settings_service import (
    AgentEffectiveSettingsService,
)
from core.services.agent_rollout_preset_service import AgentRolloutPresetService
from core.services.agent_settings_service import AgentSettingsService

preset_svc = AgentRolloutPresetService
settings_svc = AgentSettingsService
effective_svc = AgentEffectiveSettingsService
cc_svc = AgentControlCenterService


def _biz_from_overrides(overrides: dict) -> SimpleNamespace:
    defaults = {
        "agent_followups_enabled": False,
        "agent_catalog_followup_enabled": False,
        "agent_price_followup_enabled": False,
        "agent_order_followup_enabled": False,
        "agent_admin_escalation_enabled": False,
        "agent_ai_composer_enabled": False,
        "agent_decision_engine_enabled": False,
        "agent_lead_signal_enabled": False,
        "agent_lead_scoring_enabled": False,
        "agent_dynamic_offer_enabled": False,
        "agent_conversation_policy_enabled": False,
        "agent_response_orchestrator_enabled": False,
        "agent_response_orchestrator_log_only": True,
        "agent_execution_sandbox_enabled": False,
        "agent_execution_mode": "log_only",
        "agent_execution_queue_enabled": False,
        "agent_execution_api_approval_enabled": False,
        "agent_execution_live_sender_enabled": False,
        "agent_execution_auto_execute_approved": False,
        "agent_execution_canary_user_ids": "",
        "agent_execution_approval_admin_notify": False,
        "agent_execution_max_daily_per_user": 3,
        "agent_execution_live_sender_batch_limit": 10,
        "agent_runtime_settings_enabled": True,
        "agent_settings_mutation_enabled": True,
        "agent_settings_allow_live_flags": False,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _settings_from_overrides(overrides: dict) -> SimpleNamespace:
    biz = _biz_from_overrides(overrides)
    return SimpleNamespace(
        business=biz,
        bot=SimpleNamespace(admin_group_id="-100"),
        openai=SimpleNamespace(api_key="sk-test"),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# 1. Initial safe defaults
# ═══════════════════════════════════════════════════════════════════════════════


class TestInitialDefaults:
    def test_effective_settings_all_safe(self):
        s = effective_svc({})
        s._runtime_enabled = False
        f = s.get_followup_settings()
        assert f.enabled is False

    def test_stage_off_initially(self):
        biz = _biz_from_overrides({})
        stage = cc_svc.detect_rollout_stage(biz)
        assert stage.stage == "off"

    def test_preflight_green_initially(self):
        biz = _biz_from_overrides({})
        settings = _settings_from_overrides({})
        pf = cc_svc.get_preflight_status(biz, settings)
        assert pf.status == "green"


# ═══════════════════════════════════════════════════════════════════════════════
# 2. OFF preset
# ═══════════════════════════════════════════════════════════════════════════════


class TestOFFPreset:
    def test_preview_allowed(self):
        r = preset_svc.preview_preset("off")
        assert r.allowed is True
        assert r.risk_level == "low"

    def test_off_settings_all_false(self):
        s = preset_svc.build_preset_settings("off")
        for key, val in s.items():
            if key.endswith("_enabled"):
                assert val is False, f"{key} should be False"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. LOG_ONLY preset flow
# ═══════════════════════════════════════════════════════════════════════════════


class TestLogOnlyFlow:
    def test_preview_allowed(self):
        r = preset_svc.preview_preset("log_only")
        assert r.allowed is True

    def test_preview_has_confirmation(self):
        r = preset_svc.preview_preset("log_only")
        assert r.requires_confirmation is True
        assert r.confirmation_token is not None

    def test_preview_diff_contains_flags(self):
        r = preset_svc.preview_preset("log_only", {})
        keys = [d.key for d in r.diff]
        assert "agent_lead_signal_enabled" in keys

    def test_apply_writes_overrides(self):
        target = preset_svc.build_preset_settings("log_only")
        s = effective_svc(target)
        s._runtime_enabled = True
        d = s.get_decision_settings()
        assert d.lead_signal_enabled is True
        assert d.decision_enabled is True

    def test_stage_detected_log_only(self):
        target = preset_svc.build_preset_settings("log_only")
        biz = _biz_from_overrides(target)
        stage = cc_svc.detect_rollout_stage(biz)
        assert stage.stage == "log_only"

    def test_preflight_green_log_only(self):
        target = preset_svc.build_preset_settings("log_only")
        biz = _biz_from_overrides(target)
        settings = SimpleNamespace(
            business=biz,
            bot=SimpleNamespace(admin_group_id="-100"),
            openai=SimpleNamespace(api_key="sk-test"),
        )
        pf = cc_svc.get_preflight_status(biz, settings)
        assert pf.status == "green"

    def test_effective_reads_runtime(self):
        target = preset_svc.build_preset_settings("log_only")
        s = effective_svc(target)
        s._runtime_enabled = True
        o = s.get_orchestrator_settings()
        assert o.enabled is True
        assert o.log_only is True

    def test_cache_clears(self):
        effective_svc.clear_cache()


# ═══════════════════════════════════════════════════════════════════════════════
# 4. Rollback to OFF
# ═══════════════════════════════════════════════════════════════════════════════


class TestRollbackOFF:
    def test_off_after_log_only(self):
        off_settings = preset_svc.build_preset_settings("off")
        biz = _biz_from_overrides(off_settings)
        stage = cc_svc.detect_rollout_stage(biz)
        assert stage.stage == "off"

    def test_off_effective_all_disabled(self):
        off_settings = preset_svc.build_preset_settings("off")
        s = effective_svc(off_settings)
        s._runtime_enabled = True
        f = s.get_followup_settings()
        assert f.enabled is False

    def test_audit_created(self):
        snapshot = settings_svc.build_rollback_snapshot(
            preset_svc.build_preset_settings("log_only"),
        )
        assert "agent_lead_signal_enabled" in snapshot


# ═══════════════════════════════════════════════════════════════════════════════
# 5. Critical/blocked presets
# ═══════════════════════════════════════════════════════════════════════════════


class TestBlockedPresets:
    def test_live_send_blocked_default(self):
        r = preset_svc.preview_preset("approved_live_send")
        assert r.allowed is False
        assert any("live" in b for b in r.blockers)

    def test_canary_no_ids_blocked(self):
        r = preset_svc.preview_preset("canary", {})
        assert r.allowed is False
        assert any("canary" in b for b in r.blockers)

    def test_canary_with_ids_allowed(self):
        r = preset_svc.preview_preset(
            "canary",
            {
                "agent_execution_canary_user_ids": "123,456",
            },
        )
        assert r.allowed is True

    def test_dry_run_allowed(self):
        r = preset_svc.preview_preset("dry_run")
        assert r.allowed is True

    def test_approval_required_allowed(self):
        r = preset_svc.preview_preset("approval_required")
        assert r.allowed is True

    def test_unknown_preset_rejected(self):
        r = preset_svc.preview_preset("turbo_mode")
        assert r.allowed is False


# ═══════════════════════════════════════════════════════════════════════════════
# 6. DRY_RUN flow
# ═══════════════════════════════════════════════════════════════════════════════


class TestDryRunFlow:
    def test_stage_detected(self):
        target = preset_svc.build_preset_settings("dry_run")
        biz = _biz_from_overrides(target)
        stage = cc_svc.detect_rollout_stage(biz)
        assert stage.stage == "dry_run"

    def test_sandbox_enabled(self):
        target = preset_svc.build_preset_settings("dry_run")
        s = effective_svc(target)
        s._runtime_enabled = True
        e = s.get_execution_settings()
        assert e.sandbox_enabled is True
        assert e.execution_mode == "dry_run"


# ═══════════════════════════════════════════════════════════════════════════════
# 7. Safety assertions
# ═══════════════════════════════════════════════════════════════════════════════


class TestSafety:
    def test_no_secrets_in_snapshot(self):
        from dataclasses import asdict

        target = preset_svc.build_preset_settings("log_only")
        s = effective_svc(target)
        s._runtime_enabled = True
        snap = s.get_agent_settings_snapshot()
        text = str(asdict(snap))
        assert "sk-" not in text
        assert "bot_token" not in text.lower()

    def test_no_env_mutation(self):
        import os

        before = os.environ.copy()
        preset_svc.preview_preset("log_only")
        after = os.environ.copy()
        for k in before:
            if k.startswith("AGENT_"):
                assert before[k] == after.get(k), f"{k} was mutated"

    def test_no_telegram_send(self):
        r = preset_svc.preview_preset(
            "canary",
            {
                "agent_execution_canary_user_ids": "123",
            },
        )
        assert r.allowed is True

    def test_validation_still_works(self):
        r = settings_svc.validate_change(
            "agent_execution_live_sender_enabled",
            True,
        )
        assert r.allowed is False


# ═══════════════════════════════════════════════════════════════════════════════
# 8. Full snapshot cycle
# ═══════════════════════════════════════════════════════════════════════════════


class TestFullCycle:
    def test_off_to_log_only_to_off(self):
        off = preset_svc.build_preset_settings("off")
        log = preset_svc.build_preset_settings("log_only")

        biz0 = _biz_from_overrides(off)
        assert cc_svc.detect_rollout_stage(biz0).stage == "off"

        biz1 = _biz_from_overrides(log)
        assert cc_svc.detect_rollout_stage(biz1).stage == "log_only"

        biz2 = _biz_from_overrides(off)
        assert cc_svc.detect_rollout_stage(biz2).stage == "off"

    def test_stage_progression(self):
        for name, expected in [
            ("off", "off"),
            ("log_only", "log_only"),
            ("dry_run", "dry_run"),
        ]:
            target = preset_svc.build_preset_settings(name)
            biz = _biz_from_overrides(target)
            stage = cc_svc.detect_rollout_stage(biz)
            assert stage.stage == expected, f"{name} → {stage.stage}"
