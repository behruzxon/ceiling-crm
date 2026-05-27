"""Tests for Step BL — Security Actions UI elements."""

from __future__ import annotations

from pathlib import Path


class TestSecurityTemplate:
    def test_template_exists(self):
        assert Path("apps/web/templates/security.html").exists()

    def test_no_script_injection(self):
        content = Path("apps/web/templates/security.html").read_text(encoding="utf-8")
        assert "<script>" not in content.lower()

    def test_no_session_hash_rendered(self):
        content = Path("apps/web/templates/security.html").read_text(encoding="utf-8")
        assert "session_id_hash" not in content


class TestSchemas:
    def test_action_request(self):
        from core.schemas.admin_security_action import AdminSecurityActionRequest

        r = AdminSecurityActionRequest(action="revoke")
        assert r.action == "revoke"

    def test_action_result(self):
        from core.schemas.admin_security_action import AdminSecurityActionResult

        r = AdminSecurityActionResult(ok=True, action="revoke")
        assert r.ok

    def test_revoke_request(self):
        from core.schemas.admin_security_action import AdminSessionRevokeRequest

        r = AdminSessionRevokeRequest(session_record_id=1)
        assert r.session_record_id == 1

    def test_disable_request(self):
        from core.schemas.admin_security_action import AdminUserDisableRequest

        r = AdminUserDisableRequest(target_admin_id="u1")
        assert r.target_admin_id == "u1"

    def test_ip_rule_create(self):
        from core.schemas.admin_security_action import AdminIPRuleCreate

        r = AdminIPRuleCreate(ip_pattern="1.2.3.4", rule_type="block")
        assert r.ip_pattern == "1.2.3.4"

    def test_ip_rule_response(self):
        from core.schemas.admin_security_action import AdminIPRuleResponse

        r = AdminIPRuleResponse(id=1, ip_pattern="1.2.3.4", rule_type="watch")
        assert r.rule_type == "watch"

    def test_audit_item(self):
        from core.schemas.admin_security_action import AdminSecurityActionAuditItem

        a = AdminSecurityActionAuditItem(action="revoke", status="success")
        assert a.status == "success"

    def test_all_frozen(self):
        import pytest

        from core.schemas.admin_security_action import (
            AdminIPRuleCreate,
            AdminIPRuleResponse,
            AdminSecurityActionAuditItem,
            AdminSecurityActionRequest,
            AdminSecurityActionResult,
            AdminSessionRevokeRequest,
            AdminUserDisableRequest,
        )

        for cls in [
            AdminSecurityActionRequest,
            AdminSecurityActionResult,
            AdminSessionRevokeRequest,
            AdminUserDisableRequest,
            AdminIPRuleCreate,
            AdminIPRuleResponse,
            AdminSecurityActionAuditItem,
        ]:
            obj = cls()
            with pytest.raises(AttributeError):
                obj.action = "x"  # type: ignore[misc]


class TestRBACSecurityPermissions:
    def test_owner_has_security_manage(self):
        from core.services.admin_rbac_service import AdminRBACService

        assert AdminRBACService.has_permission("owner", "security.manage")

    def test_admin_has_security_view(self):
        from core.services.admin_rbac_service import AdminRBACService

        assert AdminRBACService.has_permission("admin", "security.view")

    def test_admin_has_session_revoke(self):
        from core.services.admin_rbac_service import AdminRBACService

        assert AdminRBACService.has_permission("admin", "security.sessions.revoke")

    def test_operator_no_security_manage(self):
        from core.services.admin_rbac_service import AdminRBACService

        assert not AdminRBACService.has_permission("operator", "security.manage")

    def test_viewer_no_security(self):
        from core.services.admin_rbac_service import AdminRBACService

        assert not AdminRBACService.has_permission("viewer", "security.manage")
        assert not AdminRBACService.has_permission("viewer", "security.view")


class TestModelAndMigration:
    def test_ip_rule_model(self):
        from infrastructure.database.models.admin_ip_rule import AdminIPAccessRuleModel

        assert AdminIPAccessRuleModel.__tablename__ == "admin_ip_access_rules"

    def test_ip_rule_columns(self):
        from infrastructure.database.models.admin_ip_rule import AdminIPAccessRuleModel

        cols = {c.name for c in AdminIPAccessRuleModel.__table__.columns}
        assert "ip_pattern" in cols
        assert "rule_type" in cols
        assert "is_active" in cols
        assert "reason" in cols

    def test_migration_importable(self):
        import importlib

        mod = importlib.import_module(
            "infrastructure.database.migrations.versions."
            "20260526_1700_f7g8h9i0j1k2_add_admin_ip_access_rules"
        )
        assert callable(mod.upgrade)
        assert mod.revision == "f7g8h9i0j1k2"
