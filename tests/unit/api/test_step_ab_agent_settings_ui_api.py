"""Tests for Step AB — Settings UI API enhancements."""
from __future__ import annotations

from core.services.agent_settings_service import AgentSettingsService


class TestGetSettingsEnhanced:
    def test_settings_endpoint_exists(self):
        from apps.api.main import create_app
        app = create_app()
        paths = [r.path for r in app.routes]
        assert any("settings" in p and "agent" in p for p in paths)

    def test_sanitize_includes_source(self):
        items = AgentSettingsService.sanitize_settings_for_api({
            "agent_followups_enabled": False,
        })
        assert items[0].source == "effective"

    def test_sanitize_includes_risk(self):
        items = AgentSettingsService.sanitize_settings_for_api({
            "agent_followups_enabled": True,
        })
        assert items[0].risk_level == "high"

    def test_sanitize_includes_value_type(self):
        items = AgentSettingsService.sanitize_settings_for_api({
            "agent_followups_enabled": True,
        })
        assert items[0].value_type == "bool"

    def test_no_secrets_in_settings(self):
        from dataclasses import asdict
        items = AgentSettingsService.sanitize_settings_for_api({
            "agent_followups_enabled": False,
        })
        text = str([asdict(i) for i in items])
        assert "api_key" not in text.lower()


class TestPreviewAPI:
    def test_safe_preview_allowed(self):
        r = AgentSettingsService.validate_change(
            "agent_catalog_followup_delay_minutes", 5,
        )
        assert r.allowed is True

    def test_high_risk_requires_confirmation(self):
        r = AgentSettingsService.validate_change(
            "agent_followups_enabled", True,
        )
        assert r.requires_confirmation is True

    def test_critical_blocked_default(self):
        r = AgentSettingsService.validate_change(
            "agent_execution_live_sender_enabled", True,
        )
        assert r.allowed is False

    def test_unknown_key_rejected(self):
        r = AgentSettingsService.validate_change("random_key", True)
        assert r.allowed is False

    def test_invalid_value_rejected(self):
        r = AgentSettingsService.validate_change(
            "agent_execution_mode", "turbo",
        )
        assert r.allowed is False


class TestCacheInvalidation:
    def test_clear_cache_callable(self):
        from core.services.agent_effective_settings_service import (
            AgentEffectiveSettingsService,
        )
        AgentEffectiveSettingsService.clear_cache()

    def test_apply_clears_cache_import(self):
        from apps.api.routes.admin_agent_settings import apply_change
        assert callable(apply_change)

    def test_rollback_clears_cache_import(self):
        from apps.api.routes.admin_agent_settings import rollback_setting
        assert callable(rollback_setting)


class TestAuditAPI:
    def test_audit_endpoint_exists(self):
        from apps.api.main import create_app
        app = create_app()
        paths = [r.path for r in app.routes]
        assert any("audit" in p for p in paths)

    def test_no_token_in_schema(self):
        from core.services.agent_settings_service import AgentSettingsService
        token = AgentSettingsService.generate_confirmation_token("key", True)
        assert len(token) == 24
        assert "key" not in token


class TestMutationCheck:
    def test_disabled_blocks(self):
        from unittest.mock import patch

        import pytest
        from fastapi import HTTPException

        from apps.api.routes.admin_agent_settings import _check_mutation_enabled
        with patch("shared.config.get_settings") as mock:
            mock.return_value.business.agent_settings_mutation_enabled = False
            with pytest.raises(HTTPException) as exc:
                _check_mutation_enabled()
            assert exc.value.status_code == 403


class TestSourceTracking:
    def test_env_source_before_override(self):
        from core.services.agent_effective_settings_service import (
            AgentEffectiveSettingsService,
        )
        s = AgentEffectiveSettingsService({})
        s._runtime_enabled = False
        _, src = s.get_bool("agent_followups_enabled")
        assert src in ("env", "default")

    def test_runtime_source_after_override(self):
        from core.services.agent_effective_settings_service import (
            AgentEffectiveSettingsService,
        )
        s = AgentEffectiveSettingsService({"agent_followups_enabled": True})
        s._runtime_enabled = True
        _, src = s.get_bool("agent_followups_enabled")
        assert src == "runtime"


class TestDangerousCombos:
    def test_live_sender_without_queue(self):
        d = AgentSettingsService.detect_dangerous_combinations({
            "agent_execution_live_sender_enabled": True,
        })
        assert "live_sender_without_queue" in d

    def test_safe_combo_clean(self):
        d = AgentSettingsService.detect_dangerous_combinations({
            "agent_execution_queue_enabled": True,
            "agent_execution_live_sender_enabled": True,
        })
        assert "live_sender_without_queue" not in d


class TestNonRegression:
    def test_signal_works(self):
        from core.services.lead_signal_service import LeadSignalService
        sig = LeadSignalService.extract_signals("narxi qancha")
        assert sig.intent == "wants_price"

    def test_orchestrator_works(self):
        from core.services.agent_response_orchestrator import (
            AgentResponseOrchestrator,
        )
        mem = {"followup_enabled": True, "memory_data": {},
               "lead_temperature": "warm", "telegram_user_id": 1}
        p = AgentResponseOrchestrator.run_pipeline(mem, text="narxi qancha")
        assert p.action == "send_user_reply"

    def test_control_center_works(self):
        from core.services.agent_control_center_service import (
            AgentControlCenterService,
        )
        snap = AgentControlCenterService.build_control_center_snapshot(None)
        assert snap.rollout_stage.stage == "off"
