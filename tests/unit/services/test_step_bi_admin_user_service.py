"""Tests for Step BI — AdminUserService."""

from __future__ import annotations

from core.services.admin_user_service import AdminUserService

svc = AdminUserService


class TestValidateAdminId:
    def test_valid(self):
        assert svc.validate_admin_id("user123") is None

    def test_empty(self):
        assert svc.validate_admin_id("") is not None

    def test_whitespace_only(self):
        assert svc.validate_admin_id("   ") is not None

    def test_special_chars(self):
        assert svc.validate_admin_id("user@#$") is not None

    def test_hyphen_underscore(self):
        assert svc.validate_admin_id("user-123_abc") is None

    def test_too_long(self):
        assert svc.validate_admin_id("a" * 101) is not None

    def test_max_length(self):
        assert svc.validate_admin_id("a" * 100) is None


class TestValidateRole:
    def test_owner(self):
        assert svc.validate_role("owner") is None

    def test_admin(self):
        assert svc.validate_role("admin") is None

    def test_operator(self):
        assert svc.validate_role("operator") is None

    def test_analyst(self):
        assert svc.validate_role("analyst") is None

    def test_viewer(self):
        assert svc.validate_role("viewer") is None

    def test_invalid(self):
        assert svc.validate_role("superadmin") is not None

    def test_empty(self):
        assert svc.validate_role("") is not None


class TestValidateDisplayName:
    def test_valid(self):
        assert svc.validate_display_name("Admin User") is None

    def test_too_long(self):
        assert svc.validate_display_name("x" * 129) is not None

    def test_empty(self):
        assert svc.validate_display_name("") is None

    def test_token_pattern(self):
        assert svc.validate_display_name("sk-secret123") is not None


class TestCanCreate:
    def test_owner_creates_owner(self):
        r = svc.can_create("owner", "owner")
        assert r.ok

    def test_owner_creates_admin(self):
        r = svc.can_create("owner", "admin")
        assert r.ok

    def test_admin_creates_viewer(self):
        r = svc.can_create("admin", "viewer")
        assert r.ok

    def test_admin_cannot_create_owner(self):
        r = svc.can_create("admin", "owner")
        assert not r.ok
        assert "owner" in r.error

    def test_operator_cannot_create(self):
        r = svc.can_create("operator", "viewer")
        assert not r.ok

    def test_analyst_cannot_create(self):
        r = svc.can_create("analyst", "viewer")
        assert not r.ok

    def test_viewer_cannot_create(self):
        r = svc.can_create("viewer", "viewer")
        assert not r.ok


class TestCanUpdateRole:
    def test_owner_changes_admin(self):
        r = svc.can_update_role("owner", "admin", "operator")
        assert r.ok

    def test_owner_promotes_to_owner(self):
        r = svc.can_update_role("owner", "admin", "owner")
        assert r.ok

    def test_admin_changes_operator(self):
        r = svc.can_update_role("admin", "operator", "analyst")
        assert r.ok

    def test_admin_cannot_change_owner(self):
        r = svc.can_update_role("admin", "owner", "admin")
        assert not r.ok

    def test_admin_cannot_promote_to_owner(self):
        r = svc.can_update_role("admin", "admin", "owner")
        assert not r.ok

    def test_operator_cannot_change(self):
        r = svc.can_update_role("operator", "viewer", "admin")
        assert not r.ok


class TestCanDisable:
    def test_owner_disables_admin(self):
        r = svc.can_disable("owner", "own1", "adm1", "admin", False, 2)
        assert r.ok

    def test_cannot_disable_super_owner(self):
        r = svc.can_disable("owner", "own1", "own2", "owner", True, 2)
        assert not r.ok
        assert "super owner" in r.error

    def test_cannot_disable_self(self):
        r = svc.can_disable("owner", "own1", "own1", "owner", False, 2)
        assert not r.ok
        assert "yourself" in r.error

    def test_cannot_disable_last_owner(self):
        r = svc.can_disable("owner", "own1", "own2", "owner", False, 1)
        assert not r.ok
        assert "last" in r.error

    def test_admin_cannot_disable_owner(self):
        r = svc.can_disable("admin", "adm1", "own1", "owner", False, 2)
        assert not r.ok

    def test_operator_cannot_disable(self):
        r = svc.can_disable("operator", "op1", "adm1", "admin", False, 2)
        assert not r.ok

    def test_admin_disables_operator(self):
        r = svc.can_disable("admin", "adm1", "op1", "operator", False, 2)
        assert r.ok


class TestCanEnable:
    def test_owner_enables(self):
        assert svc.can_enable("owner").ok

    def test_admin_enables(self):
        assert svc.can_enable("admin").ok

    def test_operator_cannot(self):
        assert not svc.can_enable("operator").ok

    def test_analyst_cannot(self):
        assert not svc.can_enable("analyst").ok

    def test_viewer_cannot(self):
        assert not svc.can_enable("viewer").ok


class TestBuildCreateDict:
    def test_basic(self):
        d = svc.build_create_dict("user1", "User One", "admin")
        assert d["admin_id"] == "user1"
        assert d["display_name"] == "User One"
        assert d["role"] == "admin"
        assert d["is_active"] is True
        assert d["is_super_owner"] is False

    def test_super_owner(self):
        d = svc.build_create_dict("own1", role="owner", is_super_owner=True)
        assert d["is_super_owner"] is True

    def test_trims_id(self):
        d = svc.build_create_dict("  user1  ")
        assert d["admin_id"] == "user1"

    def test_long_name_truncated(self):
        d = svc.build_create_dict("u1", display_name="x" * 200)
        assert len(d["display_name"]) == 128


class TestBuildUpdateDict:
    def test_role_change(self):
        d = svc.build_update_dict(role="admin", updated_by="own1")
        assert d["role"] == "admin"
        assert d["updated_by"] == "own1"
        assert "updated_at" in d

    def test_disable(self):
        d = svc.build_update_dict(is_active=False)
        assert d["is_active"] is False
        assert d["disabled_at"] is not None

    def test_enable(self):
        d = svc.build_update_dict(is_active=True)
        assert d["is_active"] is True
        assert d["disabled_at"] is None

    def test_no_changes(self):
        d = svc.build_update_dict(updated_by="own1")
        assert "role" not in d
        assert "display_name" not in d


class TestSanitize:
    def test_clean(self):
        d = svc.sanitize_for_response({"admin_id": "user1", "display_name": "User"})
        assert d["admin_id"] == "user1"

    def test_token_redacted(self):
        d = svc.sanitize_for_response({"name": "sk-secret123"})
        assert "[REDACTED]" in d["name"]


class TestGetValidRoles:
    def test_five_roles(self):
        roles = svc.get_valid_roles()
        assert len(roles) == 5
        assert "owner" in roles
        assert "viewer" in roles


class TestImmutability:
    def test_result_frozen(self):
        import pytest

        from core.services.admin_user_service import AdminUserResult

        r = AdminUserResult(ok=True)
        with pytest.raises(AttributeError):
            r.ok = False  # type: ignore[misc]
