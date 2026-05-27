"""Operator handoff queue API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query

from apps.api.dependencies.auth import require_api_token
from infrastructure.database.models.crm_operator_handoff import CRMOperatorHandoffModel
from infrastructure.database.session import get_db

router = APIRouter(
    prefix="/api/v1/admin/crm/handoffs",
    tags=["handoffs"],
    dependencies=[Depends(require_api_token)],
)


def _row_to_dict(row: CRMOperatorHandoffModel) -> dict:
    return {
        "id": row.id,
        "contact_id": row.contact_id,
        "telegram_user_id": row.telegram_user_id,
        "status": row.status,
        "priority": row.priority,
        "source": row.source,
        "reason": row.reason,
        "user_message_preview": row.user_message_preview,
        "phone_masked": row.phone_masked,
        "district": row.district,
        "area_m2": row.area_m2,
        "ceiling_type": row.ceiling_type,
        "assigned_to_admin_id": row.assigned_to_admin_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
    }


@router.get("/summary")
async def handoff_summary(
    db=Depends(get_db),
) -> dict:
    result = await db.execute(
        sa.select(
            sa.func.count().filter(CRMOperatorHandoffModel.status == "open").label("total_open"),
            sa.func.count()
            .filter(CRMOperatorHandoffModel.status == "waiting_phone")
            .label("total_waiting_phone"),
            sa.func.count()
            .filter(CRMOperatorHandoffModel.status == "assigned")
            .label("total_assigned"),
            sa.func.count()
            .filter(CRMOperatorHandoffModel.priority == "urgent")
            .label("total_urgent"),
            sa.func.count().filter(CRMOperatorHandoffModel.priority == "high").label("total_high"),
        ).select_from(CRMOperatorHandoffModel)
    )
    row = result.one()
    return {
        "total_open": row.total_open,
        "total_waiting_phone": row.total_waiting_phone,
        "total_assigned": row.total_assigned,
        "total_urgent": row.total_urgent,
        "total_high": row.total_high,
    }


@router.get("/queue")
async def handoff_queue(
    status: str = Query(default="", max_length=30),
    priority: str = Query(default="", max_length=20),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db),
) -> dict:
    q = sa.select(CRMOperatorHandoffModel).order_by(CRMOperatorHandoffModel.created_at.desc())
    if status:
        q = q.where(CRMOperatorHandoffModel.status == status)
    if priority:
        q = q.where(CRMOperatorHandoffModel.priority == priority)
    q = q.limit(limit).offset(offset)
    result = await db.execute(q)
    rows = result.scalars().all()
    return {"items": [_row_to_dict(r) for r in rows], "count": len(rows)}


async def _get_handoff(db, handoff_id: int) -> CRMOperatorHandoffModel:
    result = await db.execute(
        sa.select(CRMOperatorHandoffModel).where(CRMOperatorHandoffModel.id == handoff_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Handoff not found")
    return row


@router.post("/{handoff_id}/assign")
async def assign_handoff(
    handoff_id: int,
    body: dict | None = None,
    db=Depends(get_db),
) -> dict:
    row = await _get_handoff(db, handoff_id)
    row.status = "assigned"
    row.assigned_to_admin_id = (body or {}).get("admin_id")
    row.assigned_at = datetime.now(UTC)
    row.updated_at = datetime.now(UTC)
    await db.commit()
    return {"status": "assigned", "id": handoff_id}


@router.post("/{handoff_id}/contacted")
async def mark_contacted(
    handoff_id: int,
    db=Depends(get_db),
) -> dict:
    row = await _get_handoff(db, handoff_id)
    row.status = "contacted"
    row.contacted_at = datetime.now(UTC)
    row.updated_at = datetime.now(UTC)
    await db.commit()
    return {"status": "contacted", "id": handoff_id}


@router.post("/{handoff_id}/resolve")
async def resolve_handoff(
    handoff_id: int,
    body: dict | None = None,
    db=Depends(get_db),
) -> dict:
    row = await _get_handoff(db, handoff_id)
    row.status = "resolved"
    row.resolution_note = (body or {}).get("resolution_note")
    row.resolved_at = datetime.now(UTC)
    row.updated_at = datetime.now(UTC)
    await db.commit()
    return {"status": "resolved", "id": handoff_id}


@router.post("/{handoff_id}/cancel")
async def cancel_handoff(
    handoff_id: int,
    body: dict | None = None,
    db=Depends(get_db),
) -> dict:
    row = await _get_handoff(db, handoff_id)
    row.status = "cancelled"
    row.resolution_note = (body or {}).get("reason")
    row.updated_at = datetime.now(UTC)
    await db.commit()
    return {"status": "cancelled", "id": handoff_id}
