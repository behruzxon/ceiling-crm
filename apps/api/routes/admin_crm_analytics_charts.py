"""Analytics chart API endpoints — read-only."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from apps.api.dependencies.auth import require_api_token
from core.services.crm_analytics_chart_service import (
    build_all_charts,
    chart_series_to_dict,
)

router = APIRouter(
    prefix="/api/v1/admin/crm/analytics",
    tags=["analytics-charts"],
    dependencies=[Depends(require_api_token)],
)


@router.get("/charts")
async def analytics_charts(
    days: int = Query(default=30, ge=1, le=365),
) -> dict:
    charts = build_all_charts()
    return {
        "days": days,
        "lead_temperature": chart_series_to_dict(charts.lead_temperature),
        "intent_breakdown": chart_series_to_dict(charts.intent_breakdown),
        "missed_severity": chart_series_to_dict(charts.missed_severity),
        "handoff_status": chart_series_to_dict(charts.handoff_status),
        "top_districts": chart_series_to_dict(charts.top_districts),
        "top_ceiling_types": chart_series_to_dict(charts.top_ceiling_types),
    }
