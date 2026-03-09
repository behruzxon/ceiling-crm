"""Admin tenant info route.

GET /admin/api/tenants — current tenant information (tenant-isolated)
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.admin.deps import get_current_admin
from infrastructure.database.models.admin_user import AdminUserModel
from infrastructure.database.models.tenant import TenantModel
from infrastructure.database.session import get_db

router = APIRouter()


class TenantInfo(BaseModel):
    id: int
    name: str
    slug: str
    business_type: str
    billing_plan: str
    billing_status: str
    is_active: bool
    created_at: datetime


@router.get("", response_model=list[TenantInfo])
async def list_tenants(
    admin: AdminUserModel = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> list[TenantInfo]:
    """Return the current tenant's information.

    Returns a list for API consistency — always contains exactly one item
    (the tenant the admin belongs to). Never exposes other tenants.
    """
    tenant = await db.get(TenantModel, admin.tenant_id)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return [
        TenantInfo(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            business_type=tenant.business_type,
            billing_plan=tenant.billing_plan,
            billing_status=tenant.billing_status,
            is_active=tenant.is_active,
            created_at=tenant.created_at,
        )
    ]
