"""Tests for Step BI — AdminRBACService DB-backed resolution."""
from __future__ import annotations
from core.services.admin_rbac_service import AdminRBACService

svc = AdminRBACService


class TestResolveRoleWithDb:
    def test_db_active_user(self):
        db_user = {"role": "operator", "is_active": True}
        role, src = svc.resolve_role_with_db("u1", db_user, db_rbac_enabled=True)
        assert role == "operator"
        assert src == "db"

    def test_db_inactive_user_falls_back(self):
        db_user = {"role": "admin", "is_active": False}
        role, src = svc.resolve_role_with_db(
            "u1", db_user, db_rbac_enabled=True, fallback_to_env=True,
            owner_ids="u1",
        )
        assert role == "owner"
        assert src == "env"

    def test_db_none_user_falls_back(self):
        role, src = svc.resolve_role_with_db(
            "u1", None, db_rbac_enabled=True, fallback_to_env=True,
            admin_ids="u1",
        )
        assert role == "admin"
        assert src == "env"

    def test_db_disabled_no_fallback(self):
        role, src = svc.resolve_role_with_db(
            "u1", None, db_rbac_enabled=False, fallback_to_env=True,
            operator_ids="u1",
        )
        assert role == "operator"
        assert src == "env"

    def test_db_enabled_no_fallback(self):
        role, src = svc.resolve_role_with_db(
            "u1", None, db_rbac_enabled=True, fallback_to_env=False,
        )
        assert role == "admin"
        assert src == "env"

    def test_db_user_missing_role_defaults_viewer(self):
        db_user = {"is_active": True}
        role, src = svc.resolve_role_with_db("u1", db_user, db_rbac_enabled=True)
        assert role == "viewer"
        assert src == "db"

    def test_db_takes_priority_over_env(self):
        db_user = {"role": "analyst", "is_active": True}
        role, src = svc.resolve_role_with_db(
            "u1", db_user, db_rbac_enabled=True,
            owner_ids="u1",
        )
        assert role == "analyst"
        assert src == "db"

    def test_env_fallback_uses_all_id_lists(self):
        role, src = svc.resolve_role_with_db(
            "u5", None, db_rbac_enabled=False,
            viewer_ids="u5",
        )
        assert role == "viewer"
        assert src == "env"


class TestGetEffectivePermissions:
    def test_no_override(self):
        perms = svc.get_effective_permissions("viewer")
        assert "crm.view" in perms
        assert "crm.reply" not in perms

    def test_add_permission(self):
        perms = svc.get_effective_permissions("viewer", {"crm.reply": True})
        assert "crm.reply" in perms
        assert "crm.view" in perms

    def test_remove_permission(self):
        perms = svc.get_effective_permissions("operator", {"crm.reply": False})
        assert "crm.reply" not in perms
        assert "crm.view" in perms

    def test_add_and_remove(self):
        perms = svc.get_effective_permissions(
            "viewer",
            {"crm.export": True, "crm.view": False},
        )
        assert "crm.export" in perms
        assert "crm.view" not in perms

    def test_none_override(self):
        perms = svc.get_effective_permissions("admin", None)
        assert perms == svc.get_permissions_for_role("admin")

    def test_empty_override(self):
        perms = svc.get_effective_permissions("admin", {})
        assert perms == svc.get_permissions_for_role("admin")

    def test_unknown_role(self):
        perms = svc.get_effective_permissions("unknown")
        assert len(perms) == 0

    def test_override_on_unknown_role(self):
        perms = svc.get_effective_permissions("unknown", {"crm.view": True})
        assert perms == frozenset({"crm.view"})


class TestCheckPermissionWithOverride:
    def test_allowed_by_role(self):
        r = svc.check_permission_with_override("admin", "crm.view")
        assert r.allowed

    def test_denied_by_role(self):
        r = svc.check_permission_with_override("viewer", "crm.reply")
        assert not r.allowed

    def test_allowed_by_override(self):
        r = svc.check_permission_with_override("viewer", "crm.reply", {"crm.reply": True})
        assert r.allowed

    def test_denied_by_override(self):
        r = svc.check_permission_with_override("admin", "crm.reply", {"crm.reply": False})
        assert not r.allowed
        assert "crm.reply" in r.reason

    def test_no_override(self):
        r = svc.check_permission_with_override("operator", "crm.notes")
        assert r.allowed

    def test_role_in_result(self):
        r = svc.check_permission_with_override("analyst", "crm.view")
        assert r.role == "analyst"

    def test_permission_in_result(self):
        r = svc.check_permission_with_override("viewer", "crm.export")
        assert r.permission == "crm.export"


class TestExistingEnvRbac:
    """Ensure existing env-based RBAC still works unchanged."""

    def test_get_role_for_admin_owner(self):
        role = svc.get_role_for_admin("123", owner_ids="123,456")
        assert role == "owner"

    def test_get_role_for_admin_default(self):
        role = svc.get_role_for_admin("999")
        assert role == "admin"

    def test_has_permission(self):
        assert svc.has_permission("owner", "admin.users")
        assert not svc.has_permission("viewer", "admin.users")

    def test_check_permission(self):
        r = svc.check_permission("admin", "crm.view")
        assert r.allowed

    def test_build_role_matrix(self):
        m = svc.build_role_matrix()
        assert len(m) == 5
        assert "owner" in m

    def test_explain_denial(self):
        msg = svc.explain_denial("crm.reply", "viewer")
        assert "viewer" in msg


class TestSettings:
    def test_db_rbac_default_false(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_db_rbac_enabled"].default is False

    def test_fallback_default_true(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_db_rbac_fallback_to_env"].default is True
