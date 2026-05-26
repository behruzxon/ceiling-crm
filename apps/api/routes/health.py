"""
apps.api.routes.health
~~~~~~~~~~~~~~~~~~~~~~~
Health and readiness endpoints for the REST API.

GET /health          — quick liveness probe (no external calls, public)
GET /api/v1/health   — detailed readiness check (DB + Redis, requires auth)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from apps.api.dependencies.auth import require_api_token

router = APIRouter()


@router.get("/health", tags=["health"])
async def liveness() -> dict:
    """Lightweight liveness probe for load balancers and orchestrators.

    Returns 200 immediately — no external service calls.
    Public: no authentication required.
    """
    return {"status": "ok", "service": "ceilingcrm-api"}


@router.get(
    "/api/v1/health",
    tags=["health"],
    dependencies=[Depends(require_api_token)],
)
async def readiness() -> dict:
    """Readiness probe that verifies connectivity to PostgreSQL and Redis.

    Returns 200 with per-service status.  Individual service failures do
    not cause an HTTP error — callers inspect the ``checks`` object.
    """
    from infrastructure.cache.client import check_redis_health
    from infrastructure.database.session import check_database_health
    from shared.config import get_settings

    settings = get_settings()

    db_health = await check_database_health()
    redis_health = await check_redis_health()

    all_ok = db_health["status"] == "ok" and redis_health["status"] == "ok"

    return {
        "status": "ok" if all_ok else "degraded",
        "service": "ceilingcrm-api",
        "environment": settings.app_env,
        "checks": {
            "database": db_health,
            "redis": redis_health,
        },
    }
