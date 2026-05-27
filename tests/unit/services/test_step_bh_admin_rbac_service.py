"""Tests for Step BH — AdminRBACService."""
from __future__ import annotations

from core.services.admin_rbac_service import AdminRBACService, PermissionCheckResult

svc = AdminRBACService


class TestRoles:
    def test_valid_roles(self):
        for r in ("owner", "admin", "operator", "analyst", "viewer"):
            assert svc.is_valid_role(r)
    def test_invalid(self):
        assert not svc.is_valid_role("hacker")


class TestOwner:
    def test_has_all(self):
        perms = svc.get_permissions_for_role("owner")
        assert "crm.view" in perms and "crm.reply" in perms
        assert "agent.rollout.apply" in perms and "admin.permissions" in perms

    def test_crm_reply(self): assert svc.has_permission("owner", "crm.reply")
    def test_export_sensitive(self): assert svc.has_permission("owner", "crm.export_sensitive")
    def test_rollout_apply(self): assert svc.has_permission("owner", "agent.rollout.apply")
    def test_settings_mutate(self): assert svc.has_permission("owner", "agent.settings.mutate")


class TestAdmin:
    def test_crm_view(self): assert svc.has_permission("admin", "crm.view")
    def test_crm_reply(self): assert svc.has_permission("admin", "crm.reply")
    def test_export_sensitive(self): assert svc.has_permission("admin", "crm.export_sensitive")
    def test_rollout_apply(self): assert svc.has_permission("admin", "agent.rollout.apply")
    def test_approve_delivery(self): assert svc.has_permission("admin", "crm.reports.approve_delivery")
    def test_no_admin_permissions(self): assert not svc.has_permission("admin", "admin.permissions")


class TestOperator:
    def test_crm_view(self): assert svc.has_permission("operator", "crm.view")
    def test_crm_reply(self): assert svc.has_permission("operator", "crm.reply")
    def test_crm_tasks(self): assert svc.has_permission("operator", "crm.tasks")
    def test_no_export_sensitive(self): assert not svc.has_permission("operator", "crm.export_sensitive")
    def test_no_export(self): assert not svc.has_permission("operator", "crm.export")
    def test_no_rollout(self): assert not svc.has_permission("operator", "agent.rollout.apply")
    def test_no_mutate(self): assert not svc.has_permission("operator", "agent.settings.mutate")
    def test_no_delivery_approve(self): assert not svc.has_permission("operator", "crm.reports.approve_delivery")


class TestAnalyst:
    def test_crm_view(self): assert svc.has_permission("analyst", "crm.view")
    def test_export(self): assert svc.has_permission("analyst", "crm.export")
    def test_reports_view(self): assert svc.has_permission("analyst", "crm.reports.view")
    def test_no_reply(self): assert not svc.has_permission("analyst", "crm.reply")
    def test_no_sensitive(self): assert not svc.has_permission("analyst", "crm.view_sensitive")
    def test_no_export_sensitive(self): assert not svc.has_permission("analyst", "crm.export_sensitive")
    def test_no_mutate(self): assert not svc.has_permission("analyst", "agent.settings.mutate")


class TestViewer:
    def test_crm_view(self): assert svc.has_permission("viewer", "crm.view")
    def test_reports_view(self): assert svc.has_permission("viewer", "crm.reports.view")
    def test_no_reply(self): assert not svc.has_permission("viewer", "crm.reply")
    def test_no_export(self): assert not svc.has_permission("viewer", "crm.export")
    def test_no_edit(self): assert not svc.has_permission("viewer", "crm.edit")
    def test_no_mutate(self): assert not svc.has_permission("viewer", "agent.settings.mutate")


class TestRoleLookup:
    def test_owner_ids(self):
        assert svc.get_role_for_admin("111", owner_ids="111,222") == "owner"

    def test_admin_ids(self):
        assert svc.get_role_for_admin("333", admin_ids="333") == "admin"

    def test_operator_ids(self):
        assert svc.get_role_for_admin("444", operator_ids="444") == "operator"

    def test_analyst_ids(self):
        assert svc.get_role_for_admin("555", analyst_ids="555") == "analyst"

    def test_viewer_ids(self):
        assert svc.get_role_for_admin("666", viewer_ids="666") == "viewer"

    def test_default_role(self):
        assert svc.get_role_for_admin("999") == "admin"

    def test_default_custom(self):
        assert svc.get_role_for_admin("999", default_role="viewer") == "viewer"

    def test_priority_owner_first(self):
        assert svc.get_role_for_admin("111", owner_ids="111", admin_ids="111") == "owner"


class TestCheckPermission:
    def test_allowed(self):
        r = svc.check_permission("admin", "crm.view")
        assert r.allowed and r.role == "admin"

    def test_denied(self):
        r = svc.check_permission("viewer", "crm.reply")
        assert not r.allowed and r.reason


class TestPrincipalSummary:
    def test_owner(self):
        s = svc.build_principal_summary("owner")
        assert s["can_reply"] and s["can_export_sensitive"] and s["can_apply_rollout"]

    def test_viewer(self):
        s = svc.build_principal_summary("viewer")
        assert not s["can_reply"] and not s["can_export"]

    def test_operator(self):
        s = svc.build_principal_summary("operator")
        assert s["can_reply"] and not s["can_export_sensitive"]


class TestRoleMatrix:
    def test_has_all_roles(self):
        m = svc.build_role_matrix()
        for r in ("owner", "admin", "operator", "analyst", "viewer"):
            assert r in m


class TestExplainDenial:
    def test_uzbek(self):
        msg = svc.explain_denial("crm.reply", "viewer")
        assert "ruxsat" in msg.lower() or "Ruxsat" in msg


class TestSettings:
    def test_rbac_disabled(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_rbac_enabled"].default is False

    def test_default_role(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_default_role"].default == "admin"


class TestImmutability:
    def test_frozen(self):
        import pytest
        r = PermissionCheckResult()
        with pytest.raises(AttributeError):
            r.allowed = True  # type: ignore[misc]
