"""Unit tests for POST /api/leads."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from apps.api.deps import get_tenant_id, lead_service_dep
from apps.api.routes.leads import router
from core.domain.lead import Lead
from shared.constants.enums import CeilingCategory, LeadSource


def _build_app(mock_service=None) -> FastAPI:
    """Build a minimal app with just the leads router and mocked deps."""
    app = FastAPI()
    app.include_router(router, prefix="/api/leads")
    app.dependency_overrides[get_tenant_id] = lambda: 1
    if mock_service is not None:
        app.dependency_overrides[lead_service_dep] = lambda: mock_service
    return app


def _make_lead(**overrides) -> Lead:
    defaults = dict(
        id=1,
        user_id=123456789,
        category=CeilingCategory.ODNOTONNY,
        source=LeadSource.WEB,
        name="Test User",
        phone="+998901234567",
        district="Chilonzor",
        lead_status="warm",
        score=50,
        created_at=datetime(2026, 3, 9, 12, 0, 0),
        updated_at=datetime(2026, 3, 9, 12, 0, 0),
    )
    defaults.update(overrides)
    return Lead(**defaults)


async def test_create_lead_success_201():
    mock_service = AsyncMock()
    mock_service.create_lead.return_value = _make_lead()
    app = _build_app(mock_service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/leads",
            json={"name": "Test User", "phone": "+998901234567"},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] == 1
    assert data["name"] == "Test User"
    assert data["phone"] == "+998901234567"
    assert data["source"] == "web"
    assert data["score"] == 50


async def test_create_lead_sets_source_web():
    """Default source in the request schema is LeadSource.WEB."""
    mock_service = AsyncMock()
    mock_service.create_lead.return_value = _make_lead()
    app = _build_app(mock_service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/leads", json={"name": "Alice", "phone": "+99890000000"})

    mock_service.create_lead.assert_called_once()
    call_kwargs = mock_service.create_lead.call_args.kwargs
    assert call_kwargs["source"] == LeadSource.WEB


async def test_create_lead_plan_limit_returns_429():
    from core.services.lead_service import LeadLimitExceeded

    mock_service = AsyncMock()
    mock_service.create_lead.side_effect = LeadLimitExceeded("quota exceeded")
    app = _build_app(mock_service)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/leads",
            json={"name": "Bob", "phone": "+99890000000"},
        )

    assert resp.status_code == 429
    assert "limit" in resp.json()["detail"].lower()
