"""Tests for Step BL — Admin Security Actions API."""
from __future__ import annotations
import pytest


class TestRevokeSessionAPI:
    @pytest.mark.asyncio
    async def test_disabled(self):
        from apps.api.routes.admin_security_actions import revoke_session, RevokeBody
        r = await revoke_session(1, RevokeBody(confirm=True))
        assert not r["ok"]
        assert "disabled" in r["error"]

    @pytest.mark.asyncio
    async def test_no_confirm(self):
        from apps.api.routes.admin_security_actions import revoke_session, RevokeBody
        r = await revoke_session(1, RevokeBody(confirm=False))
        assert not r["ok"]

    @pytest.mark.asyncio
    async def test_no_session_hash_in_response(self):
        from apps.api.routes.admin_security_actions import revoke_session, RevokeBody
        r = await revoke_session(1, RevokeBody(confirm=True))
        assert "session_id_hash" not in str(r)


class TestDisableAdminAPI:
    @pytest.mark.asyncio
    async def test_disabled(self):
        from apps.api.routes.admin_security_actions import disable_admin, DisableBody
        r = await disable_admin("u1", DisableBody(confirm=True))
        assert not r["ok"]
        assert "disabled" in r["error"]


class TestEnableAdminAPI:
    @pytest.mark.asyncio
    async def test_disabled(self):
        from apps.api.routes.admin_security_actions import enable_admin, EnableBody
        r = await enable_admin("u1", EnableBody(confirm=True))
        assert not r["ok"]


class TestIPRulesAPI:
    @pytest.mark.asyncio
    async def test_list_empty(self):
        from apps.api.routes.admin_security_actions import list_ip_rules
        r = await list_ip_rules()
        assert r["rules"] == []

    @pytest.mark.asyncio
    async def test_create_valid(self):
        from apps.api.routes.admin_security_actions import create_ip_rule, IPRuleCreateBody
        r = await create_ip_rule(IPRuleCreateBody(ip_pattern="1.2.3.4", rule_type="watch"))
        assert r["ok"]
        assert r["preview"]["ip_pattern"] == "1.2.3.4"

    @pytest.mark.asyncio
    async def test_create_invalid_ip(self):
        from apps.api.routes.admin_security_actions import create_ip_rule, IPRuleCreateBody
        r = await create_ip_rule(IPRuleCreateBody(ip_pattern="bad", rule_type="block"))
        assert not r["ok"]
        assert "invalid" in r["error"]

    @pytest.mark.asyncio
    async def test_create_invalid_type(self):
        from apps.api.routes.admin_security_actions import create_ip_rule, IPRuleCreateBody
        r = await create_ip_rule(IPRuleCreateBody(ip_pattern="1.2.3.4", rule_type="hack"))
        assert not r["ok"]

    @pytest.mark.asyncio
    async def test_disable_rule(self):
        from apps.api.routes.admin_security_actions import disable_ip_rule, IPRuleDisableBody
        r = await disable_ip_rule(1, IPRuleDisableBody(confirm=True))
        assert r["ok"]
        assert r["preview"]["is_active"] is False


class TestRouterRegistration:
    def test_router_importable(self):
        from apps.api.routes.admin_security_actions import router
        assert router.prefix == "/api/v1/admin/security"

    def test_api_app_has_action_routes(self):
        from apps.api.main import app
        paths = [str(r.path) for r in app.routes]
        assert any("ip-rules" in p for p in paths)


class TestNoTokenInResponse:
    @pytest.mark.asyncio
    async def test_create_rule_sanitized(self):
        from apps.api.routes.admin_security_actions import create_ip_rule, IPRuleCreateBody
        r = await create_ip_rule(IPRuleCreateBody(
            ip_pattern="1.2.3.4", rule_type="watch", reason="sk-secret test",
        ))
        assert "sk-" not in str(r["preview"].get("reason", ""))


class TestDI:
    def test_security_action_service_factory(self):
        from infrastructure.di import get_admin_security_action_service
        svc = get_admin_security_action_service()
        assert svc is not None


class TestSettings:
    def test_actions_enabled_default_false(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_security_actions_enabled"].default is False

    def test_session_revoke_default_true(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_session_revoke_enabled"].default is True

    def test_ip_rules_default_false(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_ip_rules_enabled"].default is False

    def test_enforcement_default_false(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_ip_block_enforcement_enabled"].default is False

    def test_confirmation_required(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_security_action_require_confirmation"].default is True

    def test_audit_default_true(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_security_action_audit_enabled"].default is True
