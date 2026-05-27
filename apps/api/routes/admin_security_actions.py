"""
Admin Security Actions API endpoints.
Feature-gated by ADMIN_SECURITY_ACTIONS_ENABLED.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/admin/security", tags=["admin-security-actions"])


class RevokeBody(BaseModel):
    confirm: bool = False
    reason: str = ""


class DisableBody(BaseModel):
    confirm: bool = False
    reason: str = ""


class EnableBody(BaseModel):
    confirm: bool = False
    reason: str = ""


class IPRuleCreateBody(BaseModel):
    ip_pattern: str
    rule_type: str = "watch"
    reason: str = ""


class IPRuleDisableBody(BaseModel):
    confirm: bool = False
    reason: str = ""


@router.post("/sessions/{session_id}/revoke")
async def revoke_session(session_id: int, body: RevokeBody) -> dict:
    from core.services.admin_security_action_service import AdminSecurityActionService
    svc = AdminSecurityActionService
    check = svc.check_actions_enabled(enabled=False)
    if not check.ok:
        return {"ok": False, "error": check.error, "action": "session.revoke"}
    check = svc.require_confirmation(body.confirm)
    if not check.ok:
        return {"ok": False, "error": check.error, "action": "session.revoke"}
    return {
        "ok": False,
        "error": "security_actions_disabled",
        "action": "session.revoke",
        "note": "Actions not enabled — preview only",
    }


@router.post("/admin-users/{admin_id}/disable")
async def disable_admin(admin_id: str, body: DisableBody) -> dict:
    from core.services.admin_security_action_service import AdminSecurityActionService
    svc = AdminSecurityActionService
    check = svc.check_actions_enabled(enabled=False)
    if not check.ok:
        return {"ok": False, "error": check.error, "action": "admin.disable"}
    return {"ok": False, "error": "security_actions_disabled", "action": "admin.disable"}


@router.post("/admin-users/{admin_id}/enable")
async def enable_admin(admin_id: str, body: EnableBody) -> dict:
    from core.services.admin_security_action_service import AdminSecurityActionService
    svc = AdminSecurityActionService
    check = svc.check_actions_enabled(enabled=False)
    if not check.ok:
        return {"ok": False, "error": check.error, "action": "admin.enable"}
    return {"ok": False, "error": "security_actions_disabled", "action": "admin.enable"}


@router.get("/ip-rules")
async def list_ip_rules(rule_type: str = "", is_active: bool | None = None) -> dict:
    return {
        "rules": [],
        "total": 0,
        "filters": {"rule_type": rule_type, "is_active": is_active},
        "note": "Empty DB — no rules yet",
    }


@router.post("/ip-rules")
async def create_ip_rule(body: IPRuleCreateBody) -> dict:
    from core.services.admin_security_action_service import AdminSecurityActionService
    svc = AdminSecurityActionService
    check = svc.validate_ip_pattern(body.ip_pattern)
    if not check.ok:
        return {"ok": False, "error": check.error}
    check = svc.validate_rule_type(body.rule_type)
    if not check.ok:
        return {"ok": False, "error": check.error}
    return {
        "ok": True,
        "preview": svc.build_ip_rule_dict(
            ip_pattern=body.ip_pattern,
            rule_type=body.rule_type,
            reason=body.reason,
            created_by="api",
        ),
        "note": "IP rules foundation — enforcement OFF",
    }


@router.post("/ip-rules/{rule_id}/disable")
async def disable_ip_rule(rule_id: int, body: IPRuleDisableBody) -> dict:
    from core.services.admin_security_action_service import AdminSecurityActionService
    svc = AdminSecurityActionService
    return {
        "ok": True,
        "preview": svc.build_disable_ip_rule_dict(updated_by="api"),
        "note": "IP rules foundation — enforcement OFF",
    }
