"""Tests for Step AC — Rollout Preset API endpoints."""

from __future__ import annotations

from core.services.agent_rollout_preset_service import AgentRolloutPresetService


class TestPresetEndpoints:
    def test_list_endpoint_exists(self):
        from apps.api.main import create_app

        app = create_app()
        paths = [r.path for r in app.routes]
        assert any("presets" in p for p in paths)

    def test_preview_endpoint_exists(self):
        from apps.api.main import create_app

        app = create_app()
        paths = [r.path for r in app.routes]
        assert any("preview" in p and "preset" in p for p in paths)

    def test_apply_endpoint_exists(self):
        from apps.api.main import create_app

        app = create_app()
        paths = [r.path for r in app.routes]
        assert any("apply" in p and "preset" in p for p in paths)

    def test_router_has_auth(self):
        from apps.api.routes.admin_agent_settings import router

        assert len(router.dependencies) > 0


class TestPresetListResponse:
    def test_returns_presets(self):
        presets = AgentRolloutPresetService.list_presets()
        assert len(presets) == 6

    def test_has_descriptions(self):
        for p in AgentRolloutPresetService.list_presets():
            assert p.description

    def test_has_risk(self):
        for p in AgentRolloutPresetService.list_presets():
            assert p.risk_level


class TestPreviewResponse:
    def test_log_only_preview(self):
        r = AgentRolloutPresetService.preview_preset("log_only")
        assert r.allowed is True
        assert len(r.diff) > 0

    def test_canary_no_ids_blocker(self):
        r = AgentRolloutPresetService.preview_preset("canary", {})
        assert r.allowed is False
        assert len(r.blockers) > 0

    def test_live_send_blocked(self):
        r = AgentRolloutPresetService.preview_preset("approved_live_send")
        assert r.allowed is False

    def test_no_secrets(self):
        r = AgentRolloutPresetService.preview_preset("log_only")
        text = str(r)
        assert "api_key" not in text.lower()
        assert "token" not in text.lower() or "confirmation_token" in text.lower()


class TestMutationGate:
    def test_apply_requires_mutation(self):
        from unittest.mock import patch

        import pytest
        from fastapi import HTTPException

        from apps.api.routes.admin_agent_settings import _check_mutation_enabled

        with patch("shared.config.get_settings") as mock:
            mock.return_value.business.agent_settings_mutation_enabled = False
            with pytest.raises(HTTPException):
                _check_mutation_enabled()


class TestCacheClearing:
    def test_clear_cache_import(self):
        from core.services.agent_effective_settings_service import (
            AgentEffectiveSettingsService,
        )

        AgentEffectiveSettingsService.clear_cache()


class TestNonRegression:
    def test_settings_list_endpoint(self):
        from apps.api.main import create_app

        app = create_app()
        paths = [r.path for r in app.routes]
        assert any("settings" in p and "agent" in p for p in paths)

    def test_control_status_endpoint(self):
        from apps.api.main import create_app

        app = create_app()
        paths = [r.path for r in app.routes]
        assert any("control/status" in p for p in paths)

    def test_orchestrator_works(self):
        from core.services.agent_response_orchestrator import (
            AgentResponseOrchestrator,
        )

        mem = {
            "followup_enabled": True,
            "memory_data": {},
            "lead_temperature": "warm",
            "telegram_user_id": 1,
        }
        p = AgentResponseOrchestrator.run_pipeline(mem, text="narxi qancha")
        assert p.action == "send_user_reply"
