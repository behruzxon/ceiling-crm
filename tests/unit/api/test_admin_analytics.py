"""Unit tests for admin analytics endpoints.

GET /admin/api/analytics/overview
GET /admin/api/analytics/leads-by-source
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from apps.admin.deps import create_access_token, get_current_admin
from apps.admin.routes.analytics import router as analytics_router
from core.services.owner_analytics_service import (
    AIMetrics,
    FollowUpMetrics,
    LeadFunnelMetrics,
    OperatorMetrics,
    OwnerAnalytics,
)
from infrastructure.database.models.admin_user import AdminUserModel
from infrastructure.database.session import get_db

_TENANT_ID = 1
_ADMIN_ID = 42


def _make_admin() -> AdminUserModel:
    a = MagicMock(spec=AdminUserModel)
    a.id = _ADMIN_ID
    a.tenant_id = _TENANT_ID
    a.is_active = True
    return a


def _build_app(admin: AdminUserModel | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(analytics_router, prefix="/admin/api/analytics")
    app.dependency_overrides[get_db] = lambda: AsyncMock(spec=AsyncSession)
    if admin is not None:
        app.dependency_overrides[get_current_admin] = lambda: admin
    return app


def _make_analytics() -> OwnerAnalytics:
    return OwnerAnalytics(
        window_days=7,
        funnel=LeadFunnelMetrics(
            total_leads=100,
            leads_today=5,
            leads_7d=30,
            hot_leads=10,
            warm_leads=40,
            cold_leads=50,
            won_leads=23,
            lost_leads=5,
            active_leads=72,
            conversion_rate=0.23,
        ),
        operators=OperatorMetrics(
            assigned_leads=60,
            unassigned_leads=40,
            attention_queue=8,
            operators_count=3,
        ),
        ai=AIMetrics(
            ai_messages_today=38,
            ai_messages_7d=210,
            cache_hit_count=50,
            cache_miss_count=160,
            cache_hit_rate=0.24,
        ),
        followups=FollowUpMetrics(),
    )


# ── Auth guard ────────────────────────────────────────────────────────────────

async def test_analytics_overview_unauthenticated():
    """No token → 401."""
    app = _build_app(admin=None)  # no override → real JWT check

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/admin/api/analytics/overview")

    assert resp.status_code == 401


# ── Overview ──────────────────────────────────────────────────────────────────

async def test_analytics_overview_authenticated():
    """Authenticated → 200 with aggregated metrics."""
    admin = _make_admin()
    app = _build_app(admin)

    with patch(
        "apps.admin.routes.analytics.get_owner_analytics",
        new=AsyncMock(return_value=_make_analytics()),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/admin/api/analytics/overview")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total_leads"] == 100
    assert data["leads_today"] == 5
    assert data["leads_7d"] == 30
    assert data["hot_leads"] == 10
    assert data["warm_leads"] == 40
    assert data["conversion_rate"] == pytest.approx(0.23, abs=1e-4)
    assert data["ai_messages_today"] == 38
    assert data["attention_queue"] == 8


# ── Leads by source ───────────────────────────────────────────────────────────

async def test_leads_by_source():
    """Returns dict of source → count."""
    admin = _make_admin()
    app = _build_app(admin)

    # Mock the SQLAlchemy query result
    row1 = MagicMock()
    row1.source = "web"
    row1.cnt = 42

    row2 = MagicMock()
    row2.source = "telegram"
    row2.cnt = 80

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute.return_value = MagicMock(all=MagicMock(return_value=[row1, row2]))
    app.dependency_overrides[get_db] = lambda: mock_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/admin/api/analytics/leads-by-source")

    assert resp.status_code == 200
    data = resp.json()
    assert data["web"] == 42
    assert data["telegram"] == 80
