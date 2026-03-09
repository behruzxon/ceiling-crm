"""Unit tests for POST /api/pricing/calculate (pure math — no mocking needed)."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from apps.api.routes.pricing import router


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/pricing")
    return app


async def test_calculate_5x4_no_discount():
    """5 × 4 = 20 m² — exactly at threshold, no discount (threshold is strict >)."""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/pricing/calculate",
            json={"length": 5.0, "width": 4.0, "price_per_sqm": 120000, "design_name": "Standard"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["length"] == pytest.approx(5.0)
    assert data["width"] == pytest.approx(4.0)
    assert data["area"] == pytest.approx(20.0)
    assert data["gross_amount"] == 20 * 120000
    assert data["discount_pct"] == 0
    assert data["final_total"] == data["gross_amount"]
    assert data["promo_eligible"] is False


async def test_calculate_large_area_discount():
    """8 × 6 = 48 m² — large-area discount (>40 m² → 10 %)."""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/pricing/calculate",
            json={"length": 8.0, "width": 6.0, "price_per_sqm": 100000, "design_name": "Premium"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["area"] == pytest.approx(48.0)
    assert data["discount_pct"] == 10
    gross = 48 * 100000
    assert data["gross_amount"] == gross
    assert data["discount_amount"] == gross // 10
    assert data["final_total"] == gross - gross // 10
    assert data["promo_eligible"] is False


async def test_calculate_led_promo_eligible():
    """8 × 7 = 56 m² + design_key='gulli' → promo_eligible True."""
    app = _build_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/pricing/calculate",
            json={
                "length": 8.0,
                "width": 7.0,
                "price_per_sqm": 100000,
                "design_name": "Gulli",
                "design_key": "gulli",
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["area"] == pytest.approx(56.0)
    assert data["promo_eligible"] is True
