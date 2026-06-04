"""Missed leads API endpoints — read-only, no sends.

Real data: missed leads are computed deterministically from crm_messages /
crm_contacts (a contact whose LATEST message in the range is inbound — no
outbound reply after it). Severity comes from wait time. The reason-categories
(hot_unanswered / operator_waiting / phone_shared) need intent/phone data the bot
does not reliably store, so they stay 0 and data_quality flags them — never faked.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies.auth import require_api_token
from core.services.crm_daily_summary_service import (
    DEFAULT_TIMEZONE,
    VALID_RANGES,
    Period,
    resolve_period,
)
from core.services.crm_missed_leads_loader_service import collect_missed_items
from core.services.crm_missed_leads_service import build_recommendations, build_summary
from infrastructure.database.session import get_db

router = APIRouter(
    prefix="/api/v1/admin/crm/missed-leads",
    tags=["missed-leads"],
    dependencies=[Depends(require_api_token)],
)

_DATA_QUALITY = {"reason_categories_reliable": False, "severity_basis": "wait_time"}


def _period(range_: str) -> Period:
    if range_ not in VALID_RANGES:
        raise HTTPException(
            status_code=400,
            detail=f"invalid range '{range_}'; expected one of {list(VALID_RANGES)}",
        )
    return resolve_period(range_, datetime.now(tz=UTC), DEFAULT_TIMEZONE)


def _item_dict(i) -> dict:
    return {
        "contact_id": i.contact_id,
        "display_name": i.display_name,
        "phone_masked": i.phone_masked,
        "lead_score": i.lead_score,
        "severity": i.severity,
        "reason": i.reason,
        "minutes_waiting": i.minutes_waiting,
        "next_action": i.next_action,
    }


@router.get("/summary")
async def missed_leads_summary(
    range: str = Query(default="7d"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    items = await collect_missed_items(db, _period(range))
    s = build_summary(items)
    return {
        "total": s.total,
        "critical": s.critical,
        "high": s.high,
        "medium": s.medium,
        "low": s.low,
        "hot_unanswered": s.hot_unanswered,
        "operator_waiting": s.operator_waiting,
        "phone_shared_no_followup": s.phone_shared_no_followup,
        "avg_wait_minutes": s.avg_wait_minutes,
        "oldest_wait_minutes": s.oldest_wait_minutes,
        "data_quality": _DATA_QUALITY,
    }


@router.get("")
async def missed_leads_list(
    range: str = Query(default="7d"),
    severity: str = Query(default="", max_length=20),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> dict:
    items = await collect_missed_items(db, _period(range))
    if severity:
        items = [i for i in items if i.severity == severity]
    page = items[offset : offset + limit]
    return {
        "items": [_item_dict(i) for i in page],
        "count": len(items),
        "data_quality": _DATA_QUALITY,
    }


@router.get("/recommendations")
async def missed_leads_recommendations(
    range: str = Query(default="7d"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    items = await collect_missed_items(db, _period(range))
    recs = build_recommendations(build_summary(items))
    return {
        "recommendations": [
            {"text": r.text, "priority": r.priority, "count": r.count} for r in recs
        ]
    }
