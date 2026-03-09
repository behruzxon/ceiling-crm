"""Admin billing status route.

GET /admin/api/billing/status — subscription plan, expiry, and usage limits
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.admin.deps import get_current_admin
from infrastructure.database.models.admin_user import AdminUserModel
from infrastructure.database.models.tenant import TenantModel
from infrastructure.database.session import get_db
from infrastructure.di import get_billing_service

router = APIRouter()


class BillingStatusResponse(BaseModel):
    plan: str
    billing_status: str
    subscription_expires_at: datetime | None
    trial_ends_at: datetime | None
    monthly_price_uzs: int
    # Usage vs limits (from Redis + plan config)
    leads_used: int | None = None
    leads_limit: int | None = None
    leads_remaining: int | None = None
    ai_messages_used: int | None = None
    ai_messages_limit: int | None = None
    ai_messages_remaining: int | None = None


@router.get("/status", response_model=BillingStatusResponse)
async def billing_status(
    admin: AdminUserModel = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> BillingStatusResponse:
    """Return the current tenant's billing plan, expiry, and usage."""
    tenant = await db.get(TenantModel, admin.tenant_id)
    if not tenant:
        return BillingStatusResponse(
            plan="unknown",
            billing_status="unknown",
            subscription_expires_at=None,
            trial_ends_at=None,
            monthly_price_uzs=0,
        )

    # Reuse BillingService.check_limits() — fails open (returns {} on Redis error)
    billing_svc = get_billing_service(db)
    limits: dict = {}
    try:
        limits = await billing_svc.check_limits(admin.tenant_id)
    except Exception:
        pass  # limits are informational; billing status is always returned

    return BillingStatusResponse(
        plan=tenant.billing_plan,
        billing_status=tenant.billing_status,
        subscription_expires_at=tenant.subscription_expires_at,
        trial_ends_at=tenant.trial_ends_at,
        monthly_price_uzs=tenant.monthly_price_uzs,
        leads_used=limits.get("leads_used"),
        leads_limit=limits.get("leads_limit"),
        leads_remaining=limits.get("leads_remaining"),
        ai_messages_used=limits.get("ai_used"),
        ai_messages_limit=limits.get("ai_limit"),
        ai_messages_remaining=limits.get("ai_remaining"),
    )
