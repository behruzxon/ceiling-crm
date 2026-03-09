"""Admin authentication routes.

POST /admin/api/auth/login  — exchange email + password + tenant_slug for JWT
GET  /admin/api/auth/me     — return current admin info
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.admin.deps import create_access_token, get_current_admin, verify_password
from infrastructure.database.models.admin_user import AdminUserModel
from infrastructure.database.models.tenant import TenantModel
from infrastructure.database.session import get_db

router = APIRouter()


# ── Request / Response schemas ────────────────────────────────────────────────

class LoginRequest(BaseModel):
    tenant_slug: str
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminMeResponse(BaseModel):
    id: int
    email: str
    name: str
    tenant_id: int
    is_active: bool


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate an admin user and return a JWT bearer token.

    Looks up the tenant by slug, then verifies email + password against the
    admin_users table. Returns 401 for any failure (slug, email, or password).
    """
    # ── Resolve tenant ────────────────────────────────────────────────────────
    result = await db.execute(
        select(TenantModel).where(TenantModel.slug == payload.tenant_slug)
    )
    tenant = result.scalar_one_or_none()
    if not tenant or not tenant.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # ── Find admin user ───────────────────────────────────────────────────────
    result = await db.execute(
        select(AdminUserModel).where(
            AdminUserModel.tenant_id == tenant.id,
            AdminUserModel.email == payload.email.lower().strip(),
        )
    )
    admin = result.scalar_one_or_none()
    if not admin or not admin.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # ── Verify password ───────────────────────────────────────────────────────
    if not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(admin_id=admin.id, tenant_id=admin.tenant_id)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=AdminMeResponse)
async def me(
    admin: AdminUserModel = Depends(get_current_admin),
) -> AdminMeResponse:
    """Return the currently authenticated admin's profile."""
    return AdminMeResponse(
        id=admin.id,
        email=admin.email,
        name=admin.name,
        tenant_id=admin.tenant_id,
        is_active=admin.is_active,
    )
