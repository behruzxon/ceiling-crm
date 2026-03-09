"""Admin analytics routes.

GET /admin/api/analytics/overview          — aggregated funnel + operator + AI metrics
GET /admin/api/analytics/leads-by-source   — lead counts grouped by source
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.admin.deps import get_current_admin
from core.services.owner_analytics_service import get_owner_analytics
from infrastructure.database.models.admin_user import AdminUserModel
from infrastructure.database.models.lead import LeadModel
from infrastructure.database.session import get_db

router = APIRouter()


# ── Response schemas ──────────────────────────────────────────────────────────

class AnalyticsOverview(BaseModel):
    total_leads: int
    leads_today: int
    leads_7d: int
    hot_leads: int
    warm_leads: int
    cold_leads: int
    conversion_rate: float
    assigned_leads: int
    unassigned_leads: int
    attention_queue: int
    ai_messages_today: int
    ai_messages_7d: int


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/overview", response_model=AnalyticsOverview)
async def analytics_overview(
    admin: AdminUserModel = Depends(get_current_admin),
) -> AnalyticsOverview:
    """Return aggregated metrics for the tenant's leads, operators, and AI usage.

    Reuses ``get_owner_analytics()`` which pulls from PostgreSQL + Redis and
    caches results for 60 seconds per tenant.
    """
    data = await get_owner_analytics(admin.tenant_id, window_days=7)
    return AnalyticsOverview(
        total_leads=data.funnel.total_leads,
        leads_today=data.funnel.leads_today,
        leads_7d=data.funnel.leads_7d,
        hot_leads=data.funnel.hot_leads,
        warm_leads=data.funnel.warm_leads,
        cold_leads=data.funnel.cold_leads,
        conversion_rate=round(data.funnel.conversion_rate, 4),
        assigned_leads=data.operators.assigned_leads,
        unassigned_leads=data.operators.unassigned_leads,
        attention_queue=data.operators.attention_queue,
        ai_messages_today=data.ai.ai_messages_today,
        ai_messages_7d=data.ai.ai_messages_7d,
    )


@router.get("/leads-by-source", response_model=dict[str, int])
async def leads_by_source(
    admin: AdminUserModel = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Return lead counts grouped by source channel for the current tenant."""
    result = await db.execute(
        select(LeadModel.source, func.count(LeadModel.id).label("cnt"))
        .where(LeadModel.tenant_id == admin.tenant_id)
        .group_by(LeadModel.source)
    )
    return {str(row.source): row.cnt for row in result.all()}
