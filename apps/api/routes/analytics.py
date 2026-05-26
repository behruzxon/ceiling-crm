"""
apps.api.routes.analytics
~~~~~~~~~~~~~~~~~~~~~~~~~~
Read-only sales analytics endpoint for the CRM dashboard.

GET /api/v1/analytics — full analytics report for a given period.

Reuses the existing ``build_sales_analytics()`` pure function from
``core.services.sales_analytics_service``.  Lead signal dicts are
built from DB fields only (no Redis AI memory enrichment — that
requires Telegram-specific imports).  Fields that depend on Redis
enrichment (buyer_type_stats, objections, tactic stats, conversation
health, autopilot, auto-seller) will be empty/zero.
"""
from __future__ import annotations

from dataclasses import asdict
from enum import Enum

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies.auth import require_api_token
from apps.api.schemas.analytics import AnalyticsResponse
from core.services.sales_analytics_service import build_sales_analytics
from infrastructure.database.session import get_db
from infrastructure.di import get_lead_repo

router = APIRouter(
    prefix="/api/v1",
    tags=["analytics"],
    dependencies=[Depends(require_api_token)],
)


class Period(str, Enum):
    """Supported analytics time periods."""

    today = "today"
    week = "week"
    month = "month"
    all = "all"


_PERIOD_DAYS: dict[Period, int] = {
    Period.today: 1,
    Period.week: 7,
    Period.month: 30,
    Period.all: 365,
}


def _lead_to_signal_dict(lead) -> dict:
    """Convert a domain Lead to the signal dict expected by build_sales_analytics.

    Uses only DB-level fields — no Redis AI memory enrichment.
    """
    return {
        "lead_id": lead.id,
        "source": (
            lead.source.value if hasattr(lead.source, "value") else str(lead.source)
        ),
        "current_stage": (
            lead.current_stage.value
            if hasattr(lead.current_stage, "value")
            else str(lead.current_stage)
        ),
        "lead_status": lead.lead_status,
        "score": lead.score or 0,
        "phone": lead.phone,
        "district": lead.district,
        "room_area": float(lead.room_area) if lead.room_area else None,
        "follow_up_count": lead.follow_up_count or 0,
        "closing_confidence": lead.closing_confidence,
        "lead_temperature": lead.lead_temperature,
    }


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    period: Period = Query(Period.week, description="Time period for analytics"),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsResponse:
    """Return sales analytics for the specified period.

    Calls the existing ``build_sales_analytics()`` pure function with
    lead signal dicts built from database fields.
    """
    days = _PERIOD_DAYS[period]
    repo = get_lead_repo(db)

    leads = await repo.get_leads_for_analytics(days=days, limit=500)
    leads_data = [_lead_to_signal_dict(lead) for lead in leads]

    report = build_sales_analytics(leads_data)

    return AnalyticsResponse(
        period=period.value,
        days=days,
        **asdict(report),
    )
