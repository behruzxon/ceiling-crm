"""Conversation replay API — read-only, no sends."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, Path

from apps.api.dependencies.auth import require_api_token
from core.services.crm_conversation_replay_service import build_replay

router = APIRouter(
    prefix="/api/v1/admin/crm/contacts",
    tags=["conversation-replay"],
    dependencies=[Depends(require_api_token)],
)


@router.get("/{contact_id}/conversation-replay")
async def conversation_replay(
    contact_id: int = Path(..., ge=1),
) -> dict:
    contact = {"id": contact_id}
    result = build_replay(contact=contact, messages=[], traces=[], handoffs=[])
    return {
        "contact_id": result.contact_id,
        "summary": asdict(result.summary),
        "events": [asdict(e) for e in result.events],
    }
