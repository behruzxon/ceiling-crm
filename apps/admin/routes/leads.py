"""Admin leads management routes.

GET   /admin/api/leads            — paginated + filtered lead list
GET   /admin/api/leads/{lead_id}  — single lead detail
PATCH /admin/api/leads/{lead_id}  — update name, phone, district, source, lead_status
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.admin.deps import get_current_admin
from infrastructure.database.models.admin_user import AdminUserModel
from infrastructure.database.models.lead import LeadModel
from infrastructure.database.session import get_db

router = APIRouter()


# ── Response / Request schemas ────────────────────────────────────────────────

class LeadAdminResponse(BaseModel):
    id: int
    name: str
    phone: str
    district: str
    source: str
    lead_status: str | None
    score: int
    created_at: datetime

    model_config = {"from_attributes": True}


class LeadAdminDetailResponse(LeadAdminResponse):
    category: str
    notes: str | None
    assigned_manager_id: int | None
    lead_temperature: str | None
    closing_confidence: float | None
    follow_up_count: int
    updated_at: datetime


class LeadUpdateRequest(BaseModel):
    name: str | None = None
    phone: str | None = None
    district: str | None = None
    source: str | None = None
    lead_status: Literal["hot", "warm", "cold"] | None = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[LeadAdminResponse])
async def list_leads(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    lead_status: str | None = Query(None, description="hot | warm | cold"),
    source: str | None = Query(None, description="telegram | web | chat | group | site | ads | deeplink | referral"),
    admin: AdminUserModel = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> list[LeadAdminResponse]:
    """Return a paginated list of leads for the current tenant."""
    stmt = (
        select(LeadModel)
        .where(LeadModel.tenant_id == admin.tenant_id)
        .order_by(LeadModel.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    if lead_status:
        stmt = stmt.where(LeadModel.lead_status == lead_status)
    if source:
        stmt = stmt.where(LeadModel.source == source)

    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [LeadAdminResponse.model_validate(r) for r in rows]


@router.get("/{lead_id}", response_model=LeadAdminDetailResponse)
async def get_lead(
    lead_id: int,
    admin: AdminUserModel = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> LeadAdminDetailResponse:
    """Return full details for a single lead (tenant-scoped)."""
    result = await db.execute(
        select(LeadModel).where(
            LeadModel.id == lead_id,
            LeadModel.tenant_id == admin.tenant_id,
        )
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return LeadAdminDetailResponse.model_validate(lead)


@router.patch("/{lead_id}", response_model=LeadAdminDetailResponse)
async def update_lead(
    lead_id: int,
    payload: LeadUpdateRequest,
    admin: AdminUserModel = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> LeadAdminDetailResponse:
    """Patch mutable fields on a lead (tenant-scoped).

    Only fields present in the request body are updated.
    """
    # Verify lead belongs to this tenant
    result = await db.execute(
        select(LeadModel).where(
            LeadModel.id == lead_id,
            LeadModel.tenant_id == admin.tenant_id,
        )
    )
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    updates = payload.model_dump(exclude_none=True)
    if updates:
        await db.execute(
            update(LeadModel)
            .where(
                LeadModel.id == lead_id,
                LeadModel.tenant_id == admin.tenant_id,
            )
            .values(**updates)
        )
        await db.commit()
        await db.refresh(lead)

    return LeadAdminDetailResponse.model_validate(lead)
