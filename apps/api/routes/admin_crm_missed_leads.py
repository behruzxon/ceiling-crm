"""Missed leads API endpoints — read-only, no sends."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from apps.api.dependencies.auth import require_api_token
from core.services.crm_missed_leads_service import (
    build_recommendations,
    build_summary,
)

router = APIRouter(
    prefix="/api/v1/admin/crm/missed-leads",
    tags=["missed-leads"],
    dependencies=[Depends(require_api_token)],
)


@router.get("/summary")
async def missed_leads_summary() -> dict:
    summary = build_summary([])
    return {
        "total": summary.total,
        "critical": summary.critical,
        "high": summary.high,
        "medium": summary.medium,
        "low": summary.low,
        "hot_unanswered": summary.hot_unanswered,
        "operator_waiting": summary.operator_waiting,
        "phone_shared_no_followup": summary.phone_shared_no_followup,
        "avg_wait_minutes": summary.avg_wait_minutes,
        "oldest_wait_minutes": summary.oldest_wait_minutes,
    }


@router.get("")
async def missed_leads_list(
    severity: str = Query(default="", max_length=20),
    reason: str = Query(default="", max_length=50),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    return {"items": [], "count": 0}


@router.get("/recommendations")
async def missed_leads_recommendations() -> dict:
    from core.schemas.crm_missed_leads import MissedLeadSummary

    summary = MissedLeadSummary()
    recs = build_recommendations(summary)
    return {
        "recommendations": [
            {"text": r.text, "priority": r.priority, "count": r.count} for r in recs
        ]
    }
