"""Tests for Step Z — Agent Settings Mutation API."""
from __future__ import annotations

from dataclasses import asdict

from core.services.agent_settings_service import AgentSettingsService


class TestAPIRoutes:
    def test_settings_router_exists(self):
        from apps.api.routes.admin_agent_settings import router
        assert router.prefix == "/api/v1/admin/agent/settings"

    def test_settings_router_has_auth(self):
        from apps.api.routes.admin_agent_settings import router
        assert len(router.dependencies) > 0

    def test_app_includes_settings_router(self):
        from apps.api.main import create_app
        app = create_app()
        paths = [r.path for r in app.routes]
        assert any("settings" in p and "agent" in p for p in paths)

    def test_preview_endpoint_exists(self):
        from apps.api.main import create_app
        app = create_app()
        paths = [r.path for r in app.routes]
        assert any("preview" in p for p in paths)

    def test_apply_endpoint_exists(self):
        from apps.api.main import create_app
        app = create_app()
        paths = [r.path for r in app.routes]
        assert any("apply" in p for p in paths)

    def test_rollback_endpoint_exists(self):
        from apps.api.main import create_app
        app = create_app()
        paths = [r.path for r in app.routes]
        assert any("rollback" in p for p in paths)

    def test_audit_endpoint_exists(self):
        from apps.api.main import create_app
        app = create_app()
        paths = [r.path for r in app.routes]
        assert any("audit" in p for p in paths)


class TestMutationCheck:
    def test_mutation_disabled_raises(self):
        from unittest.mock import patch
        from fastapi import HTTPException
        import pytest
        from apps.api.routes.admin_agent_settings import _check_mutation_enabled
        with patch("shared.config.get_settings") as mock:
            mock.return_value.business.agent_settings_mutation_enabled = False
            with pytest.raises(HTTPException) as exc:
                _check_mutation_enabled()
            assert exc.value.status_code == 403


class TestSettingsNoSecrets:
    def test_sanitize_no_secrets(self):
        items = AgentSettingsService.sanitize_settings_for_api({
            "agent_followups_enabled": False,
        })
        text = str([asdict(i) for i in items])
        assert "api_key" not in text.lower()
        assert "token" not in text.lower()
        assert "password" not in text.lower()


class TestPreviewValidation:
    def test_unknown_key_rejected(self):
        r = AgentSettingsService.validate_change("random_key", True)
        assert r.allowed is False

    def test_dangerous_blocked(self):
        r = AgentSettingsService.validate_change(
            "agent_execution_live_sender_enabled", True,
        )
        assert r.allowed is False

    def test_safe_setting_allowed(self):
        r = AgentSettingsService.validate_change(
            "agent_catalog_followup_delay_minutes", 5,
        )
        assert r.allowed is True

    def test_preview_returns_token(self):
        r = AgentSettingsService.validate_change(
            "agent_lead_signal_enabled", True,
        )
        assert r.confirmation_token is not None


class TestConfigSettings:
    def test_mutation_default_false(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields[
            "agent_settings_mutation_enabled"
        ].default is False

    def test_confirmation_default_true(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields[
            "agent_settings_require_confirmation"
        ].default is True

    def test_allow_live_default_false(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields[
            "agent_settings_allow_live_flags"
        ].default is False


class TestDBModels:
    def test_runtime_setting_importable(self):
        from infrastructure.database.models.agent_runtime_setting import (
            AgentRuntimeSettingModel,
        )
        assert AgentRuntimeSettingModel.__tablename__ == "agent_runtime_settings"

    def test_audit_log_importable(self):
        from infrastructure.database.models.agent_setting_audit_log import (
            AgentSettingAuditLogModel,
        )
        assert AgentSettingAuditLogModel.__tablename__ == "agent_setting_audit_logs"

    def test_migration_importable(self):
        import importlib
        mod = importlib.import_module(
            "infrastructure.database.migrations.versions."
            "20260526_0650_x9y0z1a2b3c4_add_agent_settings_and_audit"
        )
        assert callable(mod.upgrade)


class TestNonRegression:
    def test_control_center_still_works(self):
        from core.services.agent_control_center_service import (
            AgentControlCenterService,
        )
        snap = AgentControlCenterService.build_control_center_snapshot(None)
        assert snap.rollout_stage.stage == "off"

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

    def test_sandbox_still_works(self):
        from core.services.agent_execution_sandbox_service import (
            AgentExecutionSandboxService,
        )
        assert AgentExecutionSandboxService is not None
