"""POST /api/leads — create a lead from a web source."""
from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, HTTPException

from apps.api.deps import lead_service_dep
from core.schemas.lead_schemas import LeadCreateRequest, LeadResponse
from core.services.lead_service import LeadLimitExceeded

router = APIRouter()


def _web_user_id(channel_user_id: str | None) -> int:
    """Deterministic int user_id from a web session string.

    Uses hashlib.md5 instead of hash() to avoid PYTHONHASHSEED randomisation
    across process restarts.
    """
    raw = channel_user_id or "web-anonymous"
    return int(hashlib.md5(raw.encode()).hexdigest(), 16) % (10**9)


@router.post("", response_model=LeadResponse, status_code=201)
async def create_lead(
    payload: LeadCreateRequest,
    service=Depends(lead_service_dep),
) -> LeadResponse:
    try:
        lead = await service.create_lead(
            user_id=_web_user_id(payload.channel_user_id),
            category=payload.category,
            name=payload.name,
            phone=payload.phone,
            district=payload.district,
            source=payload.source,
            notes=payload.notes,
        )
    except LeadLimitExceeded:
        raise HTTPException(status_code=429, detail="Lead limit reached for current plan")
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to create lead")

    return LeadResponse(
        id=lead.id,
        name=lead.name,
        phone=lead.phone,
        district=lead.district,
        source=lead.source.value,
        category=lead.category.value,
        lead_status=lead.lead_status,
        score=lead.score,
        created_at=lead.created_at,
    )
