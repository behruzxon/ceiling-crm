"""
apps.api.main
~~~~~~~~~~~~~~
FastAPI application entry point for the CeilingCRM REST API.

Run locally::

    uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload

The app uses a lifespan context manager to connect/disconnect the database
and Redis pools at startup/shutdown — the same singletons used by the
Telegram bot and scheduler.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage shared infrastructure lifecycle (DB + Redis pools)."""
    from infrastructure.cache.client import connect_redis, disconnect_redis
    from infrastructure.database.session import connect_database, disconnect_database

    await connect_database()
    log.info("api_database_connected")

    try:
        await connect_redis()
        log.info("api_redis_connected")
    except Exception:
        log.warning("api_redis_connect_failed — health checks will report degraded")

    yield

    await disconnect_redis()
    await disconnect_database()
    log.info("api_shutdown_complete")


def create_app() -> FastAPI:
    """Application factory for the CeilingCRM REST API."""
    settings = get_settings()

    app = FastAPI(
        title="CeilingCRM API",
        description="REST API for the Vashpotolok CRM platform",
        version="0.1.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        lifespan=_lifespan,
    )

    # ── Routes ────────────────────────────────────────────────────────
    from apps.api.routers.admin_users import audit_router as admin_audit_router
    from apps.api.routers.admin_users import router as admin_users_router
    from apps.api.routes.admin_agent_metrics import router as agent_metrics_router
    from apps.api.routes.admin_agent_observation import router as agent_observation_router
    from apps.api.routes.admin_agent_settings import router as agent_settings_router
    from apps.api.routes.admin_crm import router as crm_router
    from apps.api.routes.analytics import router as analytics_router
    from apps.api.routes.health import router as health_router
    from apps.api.routes.leads import router as leads_router
    from apps.api.routes.pipeline import router as pipeline_router

    app.include_router(health_router)
    app.include_router(leads_router)
    app.include_router(pipeline_router)
    app.include_router(analytics_router)
    app.include_router(agent_metrics_router)
    app.include_router(agent_settings_router)
    app.include_router(agent_observation_router)
    app.include_router(crm_router)
    from apps.api.routes.admin_security import router as admin_security_router

    app.include_router(admin_users_router)
    app.include_router(admin_audit_router)
    from apps.api.routes.admin_security_actions import router as admin_security_actions_router

    app.include_router(admin_security_router)
    from apps.api.routes.admin_crm_merge import router as admin_crm_merge_router

    app.include_router(admin_security_actions_router)
    from apps.api.routes.admin_crm_campaigns import router as admin_crm_campaigns_router

    app.include_router(admin_crm_merge_router)
    app.include_router(admin_crm_campaigns_router)
    from apps.api.routes.admin_crm_handoffs import router as admin_crm_handoffs_router

    app.include_router(admin_crm_handoffs_router)

    return app


app = create_app()
