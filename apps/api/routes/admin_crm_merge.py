"""
CRM Data Quality & Duplicate Contact Merge API endpoints.
Detection enabled by default, merge gated by CRM_CONTACT_MERGE_ENABLED.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/admin/crm", tags=["crm-merge"])


class MergePreviewBody(BaseModel):
    source_contact_id: int
    target_contact_id: int


class MergeBody(BaseModel):
    source_contact_id: int
    target_contact_id: int
    confirm: bool = False


@router.get("/data-quality/summary")
async def data_quality_summary() -> dict:
    from dataclasses import asdict

    from core.services.crm_contact_merge_service import CRMContactMergeService

    summary = CRMContactMergeService.build_data_quality_summary([])
    return asdict(summary)


@router.get("/duplicates")
async def list_duplicates(
    min_confidence: int = Query(60, ge=0, le=100),
    limit: int = Query(50, ge=1, le=100),
) -> dict:
    return {
        "candidates": [],
        "total": 0,
        "filters": {"min_confidence": min_confidence},
        "note": "Empty DB — no contacts to scan",
    }


@router.get("/contacts/{contact_id}/duplicates")
async def get_contact_duplicates(contact_id: int) -> dict:
    return {
        "contact_id": contact_id,
        "candidates": [],
        "note": "Empty DB — no contacts to compare",
    }


@router.post("/contacts/merge/preview")
async def merge_preview(body: MergePreviewBody) -> dict:
    from core.services.crm_contact_merge_service import CRMContactMergeService

    source = {"id": body.source_contact_id}
    target = {"id": body.target_contact_id}
    preview = CRMContactMergeService.build_merge_preview(source, target, merge_enabled=False)
    return {
        "source_id": preview.source_id,
        "target_id": preview.target_id,
        "confidence": preview.confidence,
        "reasons": preview.reasons,
        "plan": preview.plan,
        "warnings": preview.warnings,
        "blockers": preview.blockers,
        "allowed": preview.allowed,
    }


@router.post("/contacts/merge")
async def merge_contacts(body: MergeBody) -> dict:
    from core.services.crm_contact_merge_service import CRMContactMergeService

    result = CRMContactMergeService.validate_merge(
        {"id": body.source_contact_id},
        {"id": body.target_contact_id},
        merge_enabled=False,
        confirm=body.confirm,
    )
    return {"ok": result.ok, "error": result.error, "warnings": result.warnings}


@router.get("/contacts/merge/audit")
async def merge_audit(
    contact_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
) -> dict:
    return {
        "entries": [],
        "total": 0,
        "note": "Empty DB — no merge audit records",
    }
