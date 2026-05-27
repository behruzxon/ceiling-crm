"""Price estimate history API — read-only, no sends."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, Path

from apps.api.dependencies.auth import require_api_token
from core.services.crm_price_estimate_history_service import build_history

router = APIRouter(
    prefix="/api/v1/admin/crm/contacts",
    tags=["price-estimates"],
    dependencies=[Depends(require_api_token)],
)


@router.get("/{contact_id}/price-estimates")
async def price_estimate_history(
    contact_id: int = Path(..., ge=1),
) -> dict:
    contact = {"id": contact_id}
    result = build_history(contact=contact, messages=[], traces=[], replay_events=[])
    return {
        "contact_id": result.contact_id,
        "summary": asdict(result.summary),
        "items": [asdict(i) for i in result.items],
    }
