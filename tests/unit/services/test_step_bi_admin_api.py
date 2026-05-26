"""Tests for Step BI — Admin Users & Audit API endpoints."""
from __future__ import annotations
import pytest
from unittest.mock import patch


class TestAdminUsersAPI:
    def test_router_importable(self):
        from apps.api.routers.admin_users import router
        assert router.prefix == "/api/v1/admin/users"

    def test_audit_router_importable(self):
        from apps.api.routers.admin_users import audit_router
        assert audit_router.prefix == "/api/v1/admin/audit"

    @pytest.mark.asyncio
    async def test_list_users(self):
        from apps.api.routers.admin_users import list_admin_users
        result = await list_admin_users()
        assert result["users"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_get_user(self):
        from apps.api.routers.admin_users import get_admin_user
        result = await get_admin_user("test1")
        assert result["user"] is None

    @pytest.mark.asyncio
    async def test_create_user_valid(self):
        from apps.api.routers.admin_users import create_admin_user, AdminUserCreateBody
        body = AdminUserCreateBody(admin_id="user1", role="admin")
        result = await create_admin_user(body)
        assert result["ok"] is True
        assert result["preview"]["admin_id"] == "user1"

    @pytest.mark.asyncio
    async def test_create_user_invalid_id(self):
        from apps.api.routers.admin_users import create_admin_user, AdminUserCreateBody
        body = AdminUserCreateBody(admin_id="user@bad", role="admin")
        result = await create_admin_user(body)
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_create_user_invalid_role(self):
        from apps.api.routers.admin_users import create_admin_user, AdminUserCreateBody
        body = AdminUserCreateBody(admin_id="user1", role="hacker")
        result = await create_admin_user(body)
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_update_user_valid(self):
        from apps.api.routers.admin_users import update_admin_user, AdminUserUpdateBody
        body = AdminUserUpdateBody(role="operator")
        result = await update_admin_user("user1", body)
        assert result["ok"] is True
        assert result["preview"]["role"] == "operator"

    @pytest.mark.asyncio
    async def test_update_user_invalid_role(self):
        from apps.api.routers.admin_users import update_admin_user, AdminUserUpdateBody
        body = AdminUserUpdateBody(role="hacker")
        result = await update_admin_user("user1", body)
        assert result["ok"] is False

    @pytest.mark.asyncio
    async def test_disable_user(self):
        from apps.api.routers.admin_users import disable_admin_user
        result = await disable_admin_user("user1")
        assert result["ok"] is False
        assert "not enabled" in result["error"]

    @pytest.mark.asyncio
    async def test_enable_user(self):
        from apps.api.routers.admin_users import enable_admin_user
        result = await enable_admin_user("user1")
        assert result["ok"] is False


class TestAuditAPI:
    @pytest.mark.asyncio
    async def test_list_audit_logs(self):
        from apps.api.routers.admin_users import list_audit_logs
        result = await list_audit_logs()
        assert result["entries"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_list_valid_actions(self):
        from apps.api.routers.admin_users import list_valid_actions
        result = await list_valid_actions()
        assert "admin_user.create" in result["actions"]

    @pytest.mark.asyncio
    async def test_list_valid_statuses(self):
        from apps.api.routers.admin_users import list_valid_statuses
        result = await list_valid_statuses()
        assert "success" in result["statuses"]
        assert len(result["statuses"]) == 4


class TestApiRegistration:
    def test_api_app_has_admin_routes(self):
        from apps.api.main import app
        paths = [r.path for r in app.routes]
        assert "/api/v1/admin/users" in paths or any("/admin/users" in p for p in paths)

    def test_api_app_has_audit_routes(self):
        from apps.api.main import app
        paths = [r.path for r in app.routes]
        assert "/api/v1/admin/audit" in paths or any("/admin/audit" in p for p in paths)


class TestDI:
    def test_admin_user_service_factory(self):
        from infrastructure.di import get_admin_user_service
        svc = get_admin_user_service(None)
        assert svc is not None

    def test_admin_audit_log_service_factory(self):
        from infrastructure.di import get_admin_audit_log_service
        svc = get_admin_audit_log_service(None)
        assert svc is not None
