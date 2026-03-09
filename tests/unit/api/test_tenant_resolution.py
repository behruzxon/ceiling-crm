"""Unit tests for TenantMiddleware — slug resolution, error cases."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from apps.api.middlewares.tenant_middleware import TenantMiddleware


def _build_test_app() -> FastAPI:
    """Minimal app with TenantMiddleware + a test route."""
    app = FastAPI()
    app.add_middleware(TenantMiddleware)

    @app.get("/test")
    async def test_route():
        return {"ok": True}

    @app.get("/check-state")
    async def check_state(request: Request):
        return {"tenant_id": request.state.tenant_id}

    return app


def _make_session_factory_patch(tenant_obj=None):
    """Build mock get_session_factory + get_tenant_repo returning *tenant_obj*."""
    mock_repo = AsyncMock()
    mock_repo.get_by_slug = AsyncMock(return_value=tenant_obj)

    mock_session = AsyncMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    mock_factory_instance = MagicMock()
    mock_factory_instance.return_value = mock_cm

    return mock_factory_instance, mock_repo


async def test_missing_slug_returns_400():
    app = _build_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/test")

    assert resp.status_code == 400
    assert "X-Tenant-Slug" in resp.json()["detail"]


async def test_unknown_slug_returns_404():
    app = _build_test_app()
    mock_factory, mock_repo = _make_session_factory_patch(tenant_obj=None)

    with patch("apps.api.middlewares.tenant_middleware.get_session_factory", return_value=mock_factory):
        with patch("apps.api.middlewares.tenant_middleware.get_tenant_repo", return_value=mock_repo):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/test", headers={"X-Tenant-Slug": "nonexistent"})

    assert resp.status_code == 404
    assert "nonexistent" in resp.json()["detail"]


async def test_inactive_tenant_returns_403():
    app = _build_test_app()
    tenant = MagicMock()
    tenant.id = 99
    tenant.is_active = False
    mock_factory, mock_repo = _make_session_factory_patch(tenant_obj=tenant)

    with patch("apps.api.middlewares.tenant_middleware.get_session_factory", return_value=mock_factory):
        with patch("apps.api.middlewares.tenant_middleware.get_tenant_repo", return_value=mock_repo):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/test", headers={"X-Tenant-Slug": "inactive-co"})

    assert resp.status_code == 403
    assert "inactive" in resp.json()["detail"].lower()


async def test_valid_slug_sets_state():
    app = _build_test_app()
    tenant = MagicMock()
    tenant.id = 42
    tenant.is_active = True
    mock_factory, mock_repo = _make_session_factory_patch(tenant_obj=tenant)

    with patch("apps.api.middlewares.tenant_middleware.get_session_factory", return_value=mock_factory):
        with patch("apps.api.middlewares.tenant_middleware.get_tenant_repo", return_value=mock_repo):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.get("/check-state", headers={"X-Tenant-Slug": "my-tenant"})

    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == 42
