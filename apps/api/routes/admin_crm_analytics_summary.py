"""Analytics summary (real per-day trends) — read-only.

GET /api/v1/admin/crm/analytics/summary?range=today|7d|30d — replaces the dead
all-zero "Visual Charts" with real trends from existing tables. No writes, no
fabricated numbers; intent/source/temperature stay unavailable (data_quality).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies.auth import require_api_token
from core.services.crm_analytics_summary_service import build_analytics_summary
from core.services.crm_daily_summary_service import DEFAULT_TIMEZONE, VALID_RANGES
from infrastructure.database.session import get_db

router = APIRouter(
    prefix="/api/v1/admin/crm/analytics",
    tags=["analytics-summary"],
    dependencies=[Depends(require_api_token)],
)


@router.get("/summary")
async def analytics_summary(
    range: str = Query(default="7d"),
    timezone: str = Query(default=DEFAULT_TIMEZONE),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the real per-day trend summary for the given range."""
    if range not in VALID_RANGES:
        raise HTTPException(
            status_code=400,
            detail=f"invalid range '{range}'; expected one of {list(VALID_RANGES)}",
        )
    return await build_analytics_summary(db, range_=range, timezone_name=timezone)
