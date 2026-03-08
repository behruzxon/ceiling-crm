"""Unit tests for TenantService.

Covers:
  1. get_by_admin_user — delegates to repo
  2. slug_exists — delegates to repo
  3. create_tenant — calls repo.create, returns result
  4. update_tenant_field — lookup + setattr + repo.update
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from core.repositories.tenant_repo import AbstractTenantRepository
from core.services.tenant_service import TenantService


def _make_tenant(**overrides) -> MagicMock:
    defaults = {
        "id": 1,
        "name": "TestTenant",
        "slug": "test",
        "admin_user_id": 12345,
        "is_active": True,
    }
    defaults.update(overrides)
    t = MagicMock()
    for k, v in defaults.items():
        setattr(t, k, v)
    return t


class TestGetByAdminUser:
    """get_by_admin_user delegates to repo."""

    def setup_method(self) -> None:
        self.repo = AsyncMock(spec=AbstractTenantRepository)
        self.svc = TenantService(self.repo)

    async def test_returns_tenant_when_found(self) -> None:
        tenant = _make_tenant()
        self.repo.get_by_admin_user_id = AsyncMock(return_value=tenant)
        result = await self.svc.get_by_admin_user(12345)
        assert result is tenant
        self.repo.get_by_admin_user_id.assert_awaited_once_with(12345)

    async def test_returns_none_when_not_found(self) -> None:
        self.repo.get_by_admin_user_id = AsyncMock(return_value=None)
        result = await self.svc.get_by_admin_user(99999)
        assert result is None


class TestSlugExists:
    """slug_exists delegates to repo."""

    def setup_method(self) -> None:
        self.repo = AsyncMock(spec=AbstractTenantRepository)
        self.svc = TenantService(self.repo)

    async def test_returns_true_when_exists(self) -> None:
        self.repo.slug_exists = AsyncMock(return_value=True)
        assert await self.svc.slug_exists("existing-slug") is True

    async def test_returns_false_when_missing(self) -> None:
        self.repo.slug_exists = AsyncMock(return_value=False)
        assert await self.svc.slug_exists("new-slug") is False


class TestCreateTenant:
    """create_tenant calls repo.create and returns the result."""

    def setup_method(self) -> None:
        self.repo = AsyncMock(spec=AbstractTenantRepository)
        self.svc = TenantService(self.repo)

    async def test_creates_and_returns_tenant(self) -> None:
        tenant_in = _make_tenant(id=0, slug="newco")
        tenant_out = _make_tenant(id=42, slug="newco")
        self.repo.create = AsyncMock(return_value=tenant_out)

        result = await self.svc.create_tenant(tenant_in)

        assert result is tenant_out
        assert result.id == 42
        self.repo.create.assert_awaited_once_with(tenant_in)


class TestUpdateTenantField:
    """update_tenant_field looks up tenant, applies changes, saves."""

    def setup_method(self) -> None:
        self.repo = AsyncMock(spec=AbstractTenantRepository)
        self.svc = TenantService(self.repo)

    async def test_updates_single_field(self) -> None:
        tenant = _make_tenant(name="Old Name")
        self.repo.get_by_admin_user_id = AsyncMock(return_value=tenant)
        self.repo.update = AsyncMock(return_value=tenant)

        result = await self.svc.update_tenant_field(12345, name="New Name")

        assert result is tenant
        assert tenant.name == "New Name"
        self.repo.update.assert_awaited_once_with(tenant)

    async def test_updates_multiple_fields(self) -> None:
        tenant = _make_tenant(name="Old", is_active=True)
        self.repo.get_by_admin_user_id = AsyncMock(return_value=tenant)
        self.repo.update = AsyncMock(return_value=tenant)

        await self.svc.update_tenant_field(
            12345, name="New", is_active=False,
        )

        assert tenant.name == "New"
        assert tenant.is_active is False

    async def test_returns_none_when_no_tenant(self) -> None:
        self.repo.get_by_admin_user_id = AsyncMock(return_value=None)

        result = await self.svc.update_tenant_field(99999, name="X")

        assert result is None
        self.repo.update.assert_not_awaited()
