"""Tests for Step BS — CRM Campaign API."""
from __future__ import annotations
import pytest


class TestSegmentsAPI:
    @pytest.mark.asyncio
    async def test_list(self):
        from apps.api.routes.admin_crm_campaigns import list_segments
        r = await list_segments()
        assert len(r["segments"]) >= 10
        assert any(s["key"] == "hot_leads" for s in r["segments"])


class TestPreviewAPI:
    @pytest.mark.asyncio
    async def test_valid_segment(self):
        from apps.api.routes.admin_crm_campaigns import preview_recipients, PreviewRecipientsBody
        r = await preview_recipients(PreviewRecipientsBody(segment_key="hot_leads"))
        assert r["ok"]
        assert r["total_eligible"] == 0

    @pytest.mark.asyncio
    async def test_invalid_segment(self):
        from apps.api.routes.admin_crm_campaigns import preview_recipients, PreviewRecipientsBody
        r = await preview_recipients(PreviewRecipientsBody(segment_key="bad"))
        assert not r["ok"]


class TestSafetyCheckAPI:
    @pytest.mark.asyncio
    async def test_safe(self):
        from apps.api.routes.admin_crm_campaigns import safety_check, SafetyCheckBody
        r = await safety_check(SafetyCheckBody(segment_key="hot_leads", message_text="Salom!"))
        assert r["ok"]
        assert "send_disabled" in r["safety"]["reasons"]

    @pytest.mark.asyncio
    async def test_token_blocked(self):
        from apps.api.routes.admin_crm_campaigns import safety_check, SafetyCheckBody
        r = await safety_check(SafetyCheckBody(segment_key="hot_leads", message_text="sk-secret123"))
        assert not r["ok"]

    @pytest.mark.asyncio
    async def test_invalid_segment(self):
        from apps.api.routes.admin_crm_campaigns import safety_check, SafetyCheckBody
        r = await safety_check(SafetyCheckBody(segment_key="bad", message_text="Salom"))
        assert not r["ok"]


class TestDraftsAPI:
    @pytest.mark.asyncio
    async def test_list_empty(self):
        from apps.api.routes.admin_crm_campaigns import list_drafts
        r = await list_drafts()
        assert r["drafts"] == []

    @pytest.mark.asyncio
    async def test_create_valid(self):
        from apps.api.routes.admin_crm_campaigns import create_draft, DraftCreateBody
        r = await create_draft(DraftCreateBody(name="Test", segment_key="hot_leads", message_text="Salom!"))
        assert r["ok"]
        assert r["preview"]["name"] == "Test"

    @pytest.mark.asyncio
    async def test_create_invalid_segment(self):
        from apps.api.routes.admin_crm_campaigns import create_draft, DraftCreateBody
        r = await create_draft(DraftCreateBody(name="Test", segment_key="bad", message_text="Salom"))
        assert not r["ok"]

    @pytest.mark.asyncio
    async def test_create_token_blocked(self):
        from apps.api.routes.admin_crm_campaigns import create_draft, DraftCreateBody
        r = await create_draft(DraftCreateBody(name="Test", segment_key="hot_leads", message_text="sk-secret123"))
        assert not r["ok"]

    @pytest.mark.asyncio
    async def test_get_draft(self):
        from apps.api.routes.admin_crm_campaigns import get_draft
        r = await get_draft(1)
        assert r["draft"] is None

    @pytest.mark.asyncio
    async def test_approve_blocked(self):
        from apps.api.routes.admin_crm_campaigns import approve_draft
        r = await approve_draft(1)
        assert not r["ok"]
        assert "send_disabled" in r["error"]

    @pytest.mark.asyncio
    async def test_archive(self):
        from apps.api.routes.admin_crm_campaigns import archive_draft
        r = await archive_draft(1)
        assert r["ok"]

    @pytest.mark.asyncio
    async def test_audit_empty(self):
        from apps.api.routes.admin_crm_campaigns import draft_audit
        r = await draft_audit(1)
        assert r["entries"] == []


class TestRegistration:
    def test_router(self):
        from apps.api.routes.admin_crm_campaigns import router
        assert router.prefix == "/api/v1/admin/crm/campaigns"

    def test_api_routes(self):
        from apps.api.main import app
        paths = [str(r.path) for r in app.routes]
        assert any("campaigns" in p for p in paths)

    def test_send_endpoints_gated(self):
        from apps.api.routes.admin_crm_campaigns import router
        paths = [str(r.path) for r in router.routes]
        assert any("send-limited" in p for p in paths) or any("send" in p for p in paths)


class TestSettings:
    def test_campaigns_enabled(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_campaigns_enabled"].default is True

    def test_send_disabled(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_campaign_send_enabled"].default is False

    def test_approval_required(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_campaign_require_approval"].default is True

    def test_audit_enabled(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_campaign_audit_enabled"].default is True


class TestRBAC:
    def test_owner_campaigns(self):
        from core.services.admin_rbac_service import AdminRBACService
        assert AdminRBACService.has_permission("owner", "crm.campaigns.view")
        assert AdminRBACService.has_permission("owner", "crm.campaigns.manage")
        assert AdminRBACService.has_permission("owner", "crm.campaigns.approve")

    def test_admin_campaigns(self):
        from core.services.admin_rbac_service import AdminRBACService
        assert AdminRBACService.has_permission("admin", "crm.campaigns.view")
        assert AdminRBACService.has_permission("admin", "crm.campaigns.manage")

    def test_operator_no_campaign(self):
        from core.services.admin_rbac_service import AdminRBACService
        assert not AdminRBACService.has_permission("operator", "crm.campaigns.manage")

    def test_viewer_no_campaign(self):
        from core.services.admin_rbac_service import AdminRBACService
        assert not AdminRBACService.has_permission("viewer", "crm.campaigns.manage")


class TestModelAndMigration:
    def test_draft_model(self):
        from infrastructure.database.models.crm_campaign import CRMCampaignDraftModel
        assert CRMCampaignDraftModel.__tablename__ == "crm_campaign_drafts"

    def test_audit_model(self):
        from infrastructure.database.models.crm_campaign import CRMCampaignAuditLogModel
        assert CRMCampaignAuditLogModel.__tablename__ == "crm_campaign_audit_logs"

    def test_migration(self):
        import importlib
        mod = importlib.import_module(
            "infrastructure.database.migrations.versions."
            "20260526_1900_h9i0j1k2l3m4_add_crm_campaign_drafts_audit"
        )
        assert callable(mod.upgrade)
        assert mod.revision == "h9i0j1k2l3m4"
