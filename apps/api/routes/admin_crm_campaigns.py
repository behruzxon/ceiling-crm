"""
CRM Marketing Segments & Campaign Drafts API endpoints.
Send always disabled — draft/preview only.
"""
from __future__ import annotations
from dataclasses import asdict
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/admin/crm/campaigns", tags=["crm-campaigns"])


class PreviewRecipientsBody(BaseModel):
    segment_key: str
    filters: dict | None = None
    limit: int = Field(default=50, ge=1, le=200)


class SafetyCheckBody(BaseModel):
    segment_key: str
    message_text: str
    filters: dict | None = None


class DraftCreateBody(BaseModel):
    name: str = Field(..., max_length=200)
    segment_key: str
    message_text: str = Field(..., max_length=4000)
    filters: dict | None = None


class DraftUpdateBody(BaseModel):
    name: str | None = None
    message_text: str | None = None
    filters: dict | None = None


@router.get("/segments")
async def list_segments() -> dict:
    from core.services.crm_campaign_service import CRMCampaignService
    segments = CRMCampaignService.get_available_segments()
    return {"segments": [asdict(s) for s in segments]}


@router.post("/preview-recipients")
async def preview_recipients(body: PreviewRecipientsBody) -> dict:
    from core.services.crm_campaign_service import CRMCampaignService
    if not CRMCampaignService.is_valid_segment(body.segment_key):
        return {"ok": False, "error": f"invalid_segment:{body.segment_key}"}
    result = CRMCampaignService.preview_recipients([], body.segment_key, body.limit)
    return {"ok": True, **result, "note": "Empty DB — no contacts yet"}


@router.post("/safety-check")
async def safety_check(body: SafetyCheckBody) -> dict:
    from core.services.crm_campaign_service import CRMCampaignService
    if not CRMCampaignService.is_valid_segment(body.segment_key):
        return {"ok": False, "error": f"invalid_segment:{body.segment_key}"}
    validation = CRMCampaignService.validate_draft("check", body.segment_key, body.message_text)
    if not validation.ok:
        return {"ok": False, "error": validation.error, "warnings": validation.warnings}
    safety = CRMCampaignService.check_safety(0, body.message_text, send_enabled=False)
    return {"ok": True, "safety": asdict(safety), "warnings": validation.warnings}


@router.get("/drafts")
async def list_drafts(
    status: str = Query(""),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    return {"drafts": [], "total": 0, "filters": {"status": status}, "note": "Empty DB"}


@router.post("/drafts")
async def create_draft(body: DraftCreateBody) -> dict:
    from core.services.crm_campaign_service import CRMCampaignService
    validation = CRMCampaignService.validate_draft(
        body.name, body.segment_key, body.message_text,
    )
    if not validation.ok:
        return {"ok": False, "error": validation.error}
    draft = CRMCampaignService.build_draft_dict(
        name=body.name, segment_key=body.segment_key,
        message_text=body.message_text, created_by="api",
    )
    return {"ok": True, "preview": draft, "warnings": validation.warnings, "note": "Draft preview — DB not wired"}


@router.get("/drafts/{campaign_id}")
async def get_draft(campaign_id: int) -> dict:
    return {"draft": None, "note": "Empty DB"}


@router.patch("/drafts/{campaign_id}")
async def update_draft(campaign_id: int, body: DraftUpdateBody) -> dict:
    return {"ok": True, "note": "Draft update preview — DB not wired"}


@router.post("/drafts/{campaign_id}/approve")
async def approve_draft(campaign_id: int) -> dict:
    return {"ok": False, "error": "send_disabled", "note": "Campaign send not enabled in this step"}


@router.post("/drafts/{campaign_id}/archive")
async def archive_draft(campaign_id: int) -> dict:
    return {"ok": True, "note": "Archive preview — DB not wired"}


@router.get("/drafts/{campaign_id}/audit")
async def draft_audit(campaign_id: int) -> dict:
    return {"entries": [], "total": 0, "note": "Empty DB"}
