"""Tests for Step BR — CRM Contact Merge API."""
from __future__ import annotations
import pytest


class TestDataQualityAPI:
    @pytest.mark.asyncio
    async def test_summary(self):
        from apps.api.routes.admin_crm_merge import data_quality_summary
        r = await data_quality_summary()
        assert r["total_contacts"] == 0
        assert "missing_phone" in r


class TestDuplicatesAPI:
    @pytest.mark.asyncio
    async def test_list_empty(self):
        from apps.api.routes.admin_crm_merge import list_duplicates
        r = await list_duplicates(min_confidence=60, limit=50)
        assert r["candidates"] == []

    @pytest.mark.asyncio
    async def test_contact_duplicates(self):
        from apps.api.routes.admin_crm_merge import get_contact_duplicates
        r = await get_contact_duplicates(1)
        assert r["contact_id"] == 1
        assert r["candidates"] == []


class TestPreviewAPI:
    @pytest.mark.asyncio
    async def test_preview(self):
        from apps.api.routes.admin_crm_merge import merge_preview, MergePreviewBody
        r = await merge_preview(MergePreviewBody(source_contact_id=1, target_contact_id=2))
        assert r["source_id"] == 1
        assert "allowed" in r
        assert "blockers" in r


class TestMergeAPI:
    @pytest.mark.asyncio
    async def test_disabled(self):
        from apps.api.routes.admin_crm_merge import merge_contacts, MergeBody
        r = await merge_contacts(MergeBody(source_contact_id=1, target_contact_id=2, confirm=True))
        assert not r["ok"]
        assert "disabled" in r["error"]

    @pytest.mark.asyncio
    async def test_no_confirm(self):
        from apps.api.routes.admin_crm_merge import merge_contacts, MergeBody
        r = await merge_contacts(MergeBody(source_contact_id=1, target_contact_id=2))
        assert not r["ok"]


class TestAuditAPI:
    @pytest.mark.asyncio
    async def test_list(self):
        from apps.api.routes.admin_crm_merge import merge_audit
        r = await merge_audit()
        assert r["entries"] == []


class TestRegistration:
    def test_router(self):
        from apps.api.routes.admin_crm_merge import router
        assert router.prefix == "/api/v1/admin/crm"

    def test_api_has_routes(self):
        from apps.api.main import app
        paths = [str(r.path) for r in app.routes]
        assert any("data-quality" in p for p in paths)
        assert any("duplicates" in p for p in paths)


class TestSettings:
    def test_detection_enabled(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_duplicate_detection_enabled"].default is True

    def test_merge_disabled(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_contact_merge_enabled"].default is False

    def test_confirmation(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_contact_merge_require_confirmation"].default is True

    def test_min_confidence(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_contact_merge_min_confidence"].default == 80

    def test_audit(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_contact_merge_audit_enabled"].default is True


class TestRBAC:
    def test_owner_merge(self):
        from core.services.admin_rbac_service import AdminRBACService
        assert AdminRBACService.has_permission("owner", "crm.merge")

    def test_admin_merge(self):
        from core.services.admin_rbac_service import AdminRBACService
        assert AdminRBACService.has_permission("admin", "crm.merge")

    def test_operator_no_merge(self):
        from core.services.admin_rbac_service import AdminRBACService
        assert not AdminRBACService.has_permission("operator", "crm.merge")

    def test_viewer_no_merge(self):
        from core.services.admin_rbac_service import AdminRBACService
        assert not AdminRBACService.has_permission("viewer", "crm.merge")


class TestModelAndMigration:
    def test_model(self):
        from infrastructure.database.models.crm_contact_merge_audit import CRMContactMergeAuditModel
        assert CRMContactMergeAuditModel.__tablename__ == "crm_contact_merge_audit"

    def test_migration(self):
        import importlib
        mod = importlib.import_module(
            "infrastructure.database.migrations.versions."
            "20260526_1830_g8h9i0j1k2l3_add_crm_contact_merge"
        )
        assert callable(mod.upgrade)
        assert mod.revision == "g8h9i0j1k2l3"
