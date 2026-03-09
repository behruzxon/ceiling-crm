"""Unit tests for admin leads management endpoints.

GET   /admin/api/leads
GET   /admin/api/leads/{lead_id}
PATCH /admin/api/leads/{lead_id}
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from apps.admin.deps import create_access_token, get_current_admin
from apps.admin.routes.leads import router as leads_router
from infrastructure.database.models.admin_user import AdminUserModel
from infrastructure.database.models.lead import LeadModel
from infrastructure.database.session import get_db

_TENANT_ID = 1
_ADMIN_ID = 42
_OTHER_TENANT_ID = 99


def _make_admin(tenant_id: int = _TENANT_ID) -> AdminUserModel:
    a = MagicMock(spec=AdminUserModel)
    a.id = _ADMIN_ID
    a.tenant_id = tenant_id
    a.email = "admin@test.com"
    a.name = "Test Admin"
    a.is_active = True
    return a


def _make_lead(
    lead_id: int = 1,
    tenant_id: int = _TENANT_ID,
    lead_status: str = "warm",
) -> LeadModel:
    l = MagicMock(spec=LeadModel)
    l.id = lead_id
    l.tenant_id = tenant_id
    l.name = "John Doe"
    l.phone = "+998901234567"
    l.district = "Tashkent"
    l.source = "web"
    l.lead_status = lead_status
    l.score = 55
    l.category = "gulli"
    l.notes = None
    l.assigned_manager_id = None
    l.lead_temperature = "warm"
    l.closing_confidence = 0.6
    l.follow_up_count = 2
    l.created_at = datetime.now(timezone.utc)
    l.updated_at = datetime.now(timezone.utc)
    return l


def _build_app(admin: AdminUserModel) -> FastAPI:
    app = FastAPI()
    app.include_router(leads_router, prefix="/admin/api/leads")
    app.dependency_overrides[get_db] = lambda: AsyncMock(spec=AsyncSession)
    app.dependency_overrides[get_current_admin] = lambda: admin
    return app


def _valid_token(tenant_id: int = _TENANT_ID) -> str:
    return create_access_token(admin_id=_ADMIN_ID, tenant_id=tenant_id)


# ── Auth guard ────────────────────────────────────────────────────────────────

async def test_list_leads_unauthenticated():
    """No token → 401."""
    app = FastAPI()
    app.include_router(leads_router, prefix="/admin/api/leads")
    app.dependency_overrides[get_db] = lambda: AsyncMock(spec=AsyncSession)
    # NOTE: do NOT override get_current_admin so real JWT validation runs

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/admin/api/leads")

    assert resp.status_code == 401


# ── List leads ────────────────────────────────────────────────────────────────

async def test_list_leads_returns_tenant_scoped_data():
    """Authenticated request returns leads list."""
    admin = _make_admin()
    lead = _make_lead()
    app = _build_app(admin)

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[lead])))
    )
    app.dependency_overrides[get_db] = lambda: mock_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/admin/api/leads",
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == 1
    assert data[0]["name"] == "John Doe"


# ── Get single lead ───────────────────────────────────────────────────────────

async def test_get_lead_by_id():
    """Get lead by id returns detail response."""
    admin = _make_admin()
    lead = _make_lead()
    app = _build_app(admin)

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute.return_value = MagicMock(
        scalar_one_or_none=MagicMock(return_value=lead)
    )
    app.dependency_overrides[get_db] = lambda: mock_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/admin/api/leads/1")

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 1
    assert data["category"] == "gulli"


async def test_get_lead_not_found():
    """Lead not in tenant → 404."""
    admin = _make_admin()
    app = _build_app(admin)

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute.return_value = MagicMock(
        scalar_one_or_none=MagicMock(return_value=None)
    )
    app.dependency_overrides[get_db] = lambda: mock_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/admin/api/leads/9999")

    assert resp.status_code == 404


# ── Patch lead ────────────────────────────────────────────────────────────────

async def test_patch_lead_status():
    """PATCH lead_status updates the lead and returns updated data."""
    admin = _make_admin()
    lead = _make_lead(lead_status="warm")
    updated_lead = _make_lead(lead_status="hot")
    app = _build_app(admin)

    mock_session = AsyncMock(spec=AsyncSession)
    # First execute = select (verify existence), second execute = update
    mock_session.execute.side_effect = [
        MagicMock(scalar_one_or_none=MagicMock(return_value=lead)),
        MagicMock(),  # UPDATE result
    ]
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock(side_effect=lambda obj: None)
    app.dependency_overrides[get_db] = lambda: mock_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            "/admin/api/leads/1",
            json={"lead_status": "hot"},
        )

    assert resp.status_code == 200
    mock_session.commit.assert_called_once()


async def test_patch_lead_cross_tenant():
    """Lead belonging to different tenant → 404 (tenant isolation)."""
    admin = _make_admin(tenant_id=_TENANT_ID)
    app = _build_app(admin)

    mock_session = AsyncMock(spec=AsyncSession)
    # SELECT returns None because WHERE includes tenant_id = _TENANT_ID
    # but the lead belongs to _OTHER_TENANT_ID
    mock_session.execute.return_value = MagicMock(
        scalar_one_or_none=MagicMock(return_value=None)
    )
    app.dependency_overrides[get_db] = lambda: mock_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            "/admin/api/leads/1",
            json={"lead_status": "hot"},
        )

    assert resp.status_code == 404
