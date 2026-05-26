"""Tests for Step BT — Campaign Send API."""
from __future__ import annotations
import pytest


class TestSendPreviewAPI:
    @pytest.mark.asyncio
    async def test_preview_blocked(self):
        from apps.api.routes.admin_crm_campaigns import send_preview, SendPreviewBody
        r = await send_preview(1, SendPreviewBody())
        assert not r["allowed"]
        assert "send_disabled" in r["blockers"]


class TestDryRunAPI:
    @pytest.mark.asyncio
    async def test_dry_run(self):
        from apps.api.routes.admin_crm_campaigns import dry_run, DryRunBody
        r = await dry_run(1, DryRunBody())
        assert r["dry_run"] is True
        assert r["would_send"] == 0


class TestSendLimitedAPI:
    @pytest.mark.asyncio
    async def test_disabled(self):
        from apps.api.routes.admin_crm_campaigns import send_limited, SendLimitedBody
        r = await send_limited(1, SendLimitedBody(confirm=True))
        assert not r["ok"]
        assert "send_disabled" in str(r.get("blockers") or r.get("error", ""))

    @pytest.mark.asyncio
    async def test_no_confirm(self):
        from apps.api.routes.admin_crm_campaigns import send_limited, SendLimitedBody
        r = await send_limited(1, SendLimitedBody(confirm=False))
        assert not r["ok"]


class TestSendAttemptsAPI:
    @pytest.mark.asyncio
    async def test_list(self):
        from apps.api.routes.admin_crm_campaigns import list_send_attempts
        r = await list_send_attempts(1)
        assert r["attempts"] == []
        assert r["campaign_id"] == 1


class TestRoutes:
    def test_api_has_send_routes(self):
        from apps.api.main import app
        paths = [str(r.path) for r in app.routes]
        assert any("send-preview" in p for p in paths)
        assert any("dry-run" in p for p in paths)
        assert any("send-limited" in p for p in paths)
        assert any("send-attempts" in p for p in paths)


class TestSettings:
    def test_canary_send(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_campaign_canary_send_enabled"].default is False

    def test_send_confirmation(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_campaign_send_require_confirmation"].default is True

    def test_max_recipients(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_campaign_send_max_recipients"].default == 10

    def test_batch_limit(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_campaign_send_batch_limit"].default == 5

    def test_dry_run_only(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_campaign_send_dry_run_only"].default is True

    def test_send_audit(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_campaign_send_audit_enabled"].default is True


class TestRBAC:
    def test_owner_send(self):
        from core.services.admin_rbac_service import AdminRBACService
        assert AdminRBACService.has_permission("owner", "crm.campaigns.send")

    def test_admin_send(self):
        from core.services.admin_rbac_service import AdminRBACService
        assert AdminRBACService.has_permission("admin", "crm.campaigns.send")

    def test_operator_no_send(self):
        from core.services.admin_rbac_service import AdminRBACService
        assert not AdminRBACService.has_permission("operator", "crm.campaigns.send")


class TestModelAndMigration:
    def test_model(self):
        from infrastructure.database.models.crm_campaign_send import CRMCampaignSendAttemptModel
        assert CRMCampaignSendAttemptModel.__tablename__ == "crm_campaign_send_attempts"

    def test_migration(self):
        import importlib
        mod = importlib.import_module(
            "infrastructure.database.migrations.versions."
            "20260526_1930_i0j1k2l3m4n5_add_crm_campaign_send_attempts"
        )
        assert callable(mod.upgrade)
        assert mod.revision == "i0j1k2l3m4n5"
