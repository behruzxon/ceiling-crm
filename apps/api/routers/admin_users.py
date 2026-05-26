"""
Admin Users & Audit Log API endpoints.
Feature-gated by ADMIN_DB_RBAC_ENABLED.
"""
from __future__ import annotations
from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/admin/users", tags=["admin-users"])


class AdminUserCreateBody(BaseModel):
    admin_id: str
    display_name: str = ""
    role: str = "viewer"
    is_super_owner: bool = False
    permissions_override_json: dict | None = None


class AdminUserUpdateBody(BaseModel):
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    permissions_override_json: dict | None = None


@router.get("")
async def list_admin_users(
    role: str = Query(""),
    is_active: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    return {
        "users": [],
        "total": 0,
        "filters": {"role": role, "is_active": is_active},
        "note": "DB RBAC not enabled — no users in DB yet",
    }


@router.get("/{admin_id}")
async def get_admin_user(admin_id: str) -> dict:
    return {"user": None, "note": "DB RBAC not enabled"}


@router.post("")
async def create_admin_user(body: AdminUserCreateBody) -> dict:
    from core.services.admin_user_service import AdminUserService
    svc = AdminUserService()
    err = svc.validate_admin_id(body.admin_id)
    if err:
        return {"ok": False, "error": err}
    if body.role:
        err = svc.validate_role(body.role)
        if err:
            return {"ok": False, "error": err}
    return {
        "ok": True,
        "preview": svc.build_create_dict(
            admin_id=body.admin_id,
            display_name=body.display_name,
            role=body.role,
            is_super_owner=body.is_super_owner,
            permissions_override=body.permissions_override_json,
            created_by="api",
        ),
        "note": "DB RBAC not enabled — preview only",
    }


@router.put("/{admin_id}")
async def update_admin_user(admin_id: str, body: AdminUserUpdateBody) -> dict:
    from core.services.admin_user_service import AdminUserService
    svc = AdminUserService()
    if body.role:
        err = svc.validate_role(body.role)
        if err:
            return {"ok": False, "error": err}
    return {
        "ok": True,
        "preview": svc.build_update_dict(
            display_name=body.display_name,
            role=body.role,
            is_active=body.is_active,
            permissions_override=body.permissions_override_json,
            updated_by="api",
        ),
        "note": "DB RBAC not enabled — preview only",
    }


@router.post("/{admin_id}/disable")
async def disable_admin_user(admin_id: str) -> dict:
    return {"ok": False, "error": "DB RBAC not enabled"}


@router.post("/{admin_id}/enable")
async def enable_admin_user(admin_id: str) -> dict:
    return {"ok": False, "error": "DB RBAC not enabled"}


audit_router = APIRouter(prefix="/api/v1/admin/audit", tags=["admin-audit"])


@audit_router.get("")
async def list_audit_logs(
    actor: str = Query(""),
    action: str = Query(""),
    status: str = Query(""),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    return {
        "entries": [],
        "total": 0,
        "filters": {"actor": actor, "action": action, "status": status},
        "note": "DB RBAC not enabled — no audit logs yet",
    }


@audit_router.get("/actions")
async def list_valid_actions() -> dict:
    from core.services.admin_audit_log_service import AdminAuditLogService
    return {"actions": list(AdminAuditLogService.get_valid_actions())}


@audit_router.get("/statuses")
async def list_valid_statuses() -> dict:
    from core.services.admin_audit_log_service import AdminAuditLogService
    return {"statuses": list(AdminAuditLogService.get_valid_statuses())}
