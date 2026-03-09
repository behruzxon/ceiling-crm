"""Unit tests for admin authentication endpoints.

POST /admin/api/auth/login
GET  /admin/api/auth/me
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import bcrypt as _bcrypt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from apps.admin.deps import create_access_token, get_current_admin
from apps.admin.routes.auth import router as auth_router
from infrastructure.database.models.admin_user import AdminUserModel
from infrastructure.database.session import get_db

_TENANT_ID = 1
_ADMIN_ID = 42
_EMAIL = "admin@test.com"
_PASSWORD = "secret123"


def _bcrypt_hash(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def _make_admin(
    *,
    id: int = _ADMIN_ID,
    tenant_id: int = _TENANT_ID,
    email: str = _EMAIL,
    password: str = _PASSWORD,
    is_active: bool = True,
) -> AdminUserModel:
    """Build a mock AdminUserModel with a real bcrypt hash."""
    admin = MagicMock(spec=AdminUserModel)
    admin.id = id
    admin.tenant_id = tenant_id
    admin.email = email
    admin.password_hash = _bcrypt_hash(password)
    admin.name = "Test Admin"
    admin.is_active = is_active
    admin.created_at = datetime.now(timezone.utc)
    admin.updated_at = datetime.now(timezone.utc)
    return admin


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router, prefix="/admin/api/auth")
    app.dependency_overrides[get_db] = lambda: AsyncMock(spec=AsyncSession)
    return app


# ── Login tests ───────────────────────────────────────────────────────────────

async def test_login_success():
    """Valid credentials → 200 + JWT access_token."""
    app = _build_app()
    admin = _make_admin()

    # Mock tenant lookup
    mock_tenant = MagicMock()
    mock_tenant.id = _TENANT_ID
    mock_tenant.is_active = True

    mock_execute = AsyncMock()
    mock_session = AsyncMock(spec=AsyncSession)

    # First execute = tenant lookup, second = admin lookup
    mock_session.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tenant)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=admin)),
    ]
    app.dependency_overrides[get_db] = lambda: mock_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/admin/api/auth/login",
            json={"tenant_slug": "test-co", "email": _EMAIL, "password": _PASSWORD},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_login_invalid_password():
    """Wrong password → 401."""
    app = _build_app()
    admin = _make_admin()

    mock_tenant = MagicMock(id=_TENANT_ID, is_active=True)
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tenant)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=admin)),
    ]
    app.dependency_overrides[get_db] = lambda: mock_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/admin/api/auth/login",
            json={"tenant_slug": "test-co", "email": _EMAIL, "password": "wrongpassword"},
        )

    assert resp.status_code == 401
    assert "Invalid credentials" in resp.json()["detail"]


async def test_login_user_not_found():
    """Unknown email → 401 (same message as wrong password for security)."""
    app = _build_app()

    mock_tenant = MagicMock(id=_TENANT_ID, is_active=True)
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=mock_tenant)),
        MagicMock(scalar_one_or_none=MagicMock(return_value=None)),  # admin not found
    ]
    app.dependency_overrides[get_db] = lambda: mock_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/admin/api/auth/login",
            json={"tenant_slug": "test-co", "email": "nobody@example.com", "password": "x"},
        )

    assert resp.status_code == 401


async def test_me_valid_token():
    """Valid JWT → 200 + admin profile."""
    app = _build_app()
    admin = _make_admin()

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute.return_value = MagicMock(
        scalar_one_or_none=MagicMock(return_value=admin)
    )
    app.dependency_overrides[get_db] = lambda: mock_session

    token = create_access_token(admin_id=_ADMIN_ID, tenant_id=_TENANT_ID)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/admin/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == _ADMIN_ID
    assert data["email"] == _EMAIL
    assert data["tenant_id"] == _TENANT_ID


async def test_me_invalid_token():
    """Garbled or expired JWT → 401."""
    app = _build_app()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/admin/api/auth/me",
            headers={"Authorization": "Bearer not.a.real.token"},
        )

    assert resp.status_code == 401
