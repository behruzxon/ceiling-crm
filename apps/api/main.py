"""FastAPI application factory for the SystemaX CRM API.

Usage
-----
Development::

    uvicorn apps.api.main:app --reload --port 8000

The ``app`` module-level instance is used by the ASGI server directly.
``create_app()`` is the factory used in tests so each test gets a fresh
application instance with its own dependency overrides.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.admin.routes.analytics import router as admin_analytics_router
from apps.admin.routes.auth import router as admin_auth_router
from apps.admin.routes.billing import router as admin_billing_router
from apps.admin.routes.chats import router as admin_chats_router
from apps.admin.routes.leads import router as admin_leads_router
from apps.admin.routes.tenants import router as admin_tenants_router
from apps.api.middlewares.tenant_middleware import TenantMiddleware
from apps.api.routes.chat import router as chat_router
from apps.api.routes.leads import router as leads_router
from apps.api.routes.pricing import router as pricing_router
from apps.api.routes.stream import router as stream_router
from shared.config import get_settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="SystemaX CRM API",
        version="2.0.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
        redoc_url="/redoc",
    )

    # TenantMiddleware added first = runs second (inner)
    app.add_middleware(TenantMiddleware)

    # CORSMiddleware added last = outermost = runs first.
    # Must be outermost so OPTIONS preflight succeeds before tenant resolution.
    # Restrict allow_origins in production via environment config.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "X-Tenant-Slug", "Authorization"],
    )

    # ── Public API routes ──────────────────────────────────────────────────────
    app.include_router(leads_router, prefix="/api/leads", tags=["Leads"])
    app.include_router(pricing_router, prefix="/api/pricing", tags=["Pricing"])
    app.include_router(chat_router, prefix="/api/chat", tags=["Chat"])
    app.include_router(stream_router, prefix="/api/chat", tags=["Chat"])

    # ── Admin API routes (JWT-protected, no X-Tenant-Slug) ────────────────────
    app.include_router(admin_auth_router, prefix="/admin/api/auth", tags=["Admin Auth"])
    app.include_router(admin_leads_router, prefix="/admin/api/leads", tags=["Admin Leads"])
    app.include_router(admin_chats_router, prefix="/admin/api/chats", tags=["Admin Chats"])
    app.include_router(admin_analytics_router, prefix="/admin/api/analytics", tags=["Admin Analytics"])
    app.include_router(admin_tenants_router, prefix="/admin/api/tenants", tags=["Admin Tenants"])
    app.include_router(admin_billing_router, prefix="/admin/api/billing", tags=["Admin Billing"])

    @app.get("/health", tags=["Health"])
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()
