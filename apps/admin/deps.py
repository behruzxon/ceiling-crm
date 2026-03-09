"""Admin panel FastAPI dependencies.

Provides:
- ``get_current_admin()`` — decode JWT, load AdminUserModel from DB
- ``create_access_token()`` — mint a new JWT for a verified admin user
- ``hash_password()`` / ``verify_password()`` — bcrypt helpers (direct bcrypt, not passlib)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models.admin_user import AdminUserModel
from infrastructure.database.session import get_db
from shared.config import get_settings

# ── Crypto primitives ─────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Return bcrypt hash of a plain-text password."""
    return _bcrypt.hashpw(plain.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches the bcrypt hash."""
    return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

# Token URL used by Swagger UI; actual login is a JSON endpoint below.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/api/auth/login")

_ALGORITHM = "HS256"
_TOKEN_EXPIRE_HOURS = 8


def _secret_key() -> str:
    return get_settings().app_secret_key.get_secret_value()


# ── Token helpers ─────────────────────────────────────────────────────────────

def create_access_token(admin_id: int, tenant_id: int) -> str:
    """Create a signed JWT with admin_id and tenant_id embedded."""
    expire = datetime.now(timezone.utc) + timedelta(hours=_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": str(admin_id),
        "tenant_id": tenant_id,
        "exp": expire,
    }
    return jwt.encode(payload, _secret_key(), algorithm=_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Decode and validate JWT. Raises HTTPException(401) on failure."""
    try:
        return jwt.decode(token, _secret_key(), algorithms=[_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── FastAPI dependency ────────────────────────────────────────────────────────

async def get_current_admin(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> AdminUserModel:
    """Dependency that validates the JWT and returns the AdminUserModel.

    Inject into any admin route handler that requires authentication.
    """
    payload = decode_access_token(token)
    admin_id_str: str | None = payload.get("sub")
    tenant_id: int | None = payload.get("tenant_id")

    if not admin_id_str or tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        admin_id = int(admin_id_str)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    result = await db.execute(
        select(AdminUserModel).where(
            AdminUserModel.id == admin_id,
            AdminUserModel.tenant_id == tenant_id,
        )
    )
    admin = result.scalar_one_or_none()

    if admin is None or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin account not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return admin
