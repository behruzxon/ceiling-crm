"""FastAPI dependency wrappers over infrastructure/di.py factories.

All application-level dependencies live here so routes stay thin and
dependency overrides in tests are a single import away.
"""
from __future__ import annotations

import hashlib

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.session import get_db
from infrastructure.di import get_lead_service as _get_lead_service


async def get_tenant_id(request: Request) -> int:
    """Extract the tenant_id set by TenantMiddleware."""
    tid = getattr(request.state, "tenant_id", None)
    if tid is None:
        raise HTTPException(status_code=400, detail="Tenant not resolved")
    return tid


def chat_user_id(session_id: str) -> int:
    """Deterministic int user_id from a web session_id string (MD5 mod 10^9)."""
    return int(hashlib.md5(session_id.encode()).hexdigest(), 16) % (10**9)


def lead_service_dep(
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(get_tenant_id),
) -> "LeadService":  # type: ignore[name-defined]
    return _get_lead_service(db, tenant_id)
