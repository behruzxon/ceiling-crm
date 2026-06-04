"""Daily Control Dashboard — read-only daily summary API.

GET /api/v1/admin/crm/daily-summary — today/7d/30d KPI snapshot for the future
dashboard. Read-only; no writes, no migrations, no fake numbers. Reuses the
shared dashboard auth (require_api_token) and is reachable through the web
reverse proxy from #26.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies.auth import require_api_token
from core.services.crm_daily_summary_service import (
    DEFAULT_TIMEZONE,
    VALID_RANGES,
    build_daily_summary,
)
from infrastructure.database.session import get_db

router = APIRouter(
    prefix="/api/v1/admin/crm",
    tags=["crm-daily-summary"],
    dependencies=[Depends(require_api_token)],
)


@router.get("/daily-summary")
async def daily_summary(
    range: str = Query(default="today"),
    source: str = Query(default=""),
    timezone: str = Query(default=DEFAULT_TIMEZONE),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the daily-control KPI snapshot for the given range."""
    if range not in VALID_RANGES:
        raise HTTPException(
            status_code=400,
            detail=f"invalid range '{range}'; expected one of {list(VALID_RANGES)}",
        )
    return await build_daily_summary(
        db,
        range_=range,
        source=source or None,
        timezone_name=timezone,
    )
