"""
Admin Security Audit Dashboard API endpoints.
Read-only — no mutations.
"""
from __future__ import annotations
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/v1/admin/security", tags=["admin-security"])


@router.get("/dashboard")
async def security_dashboard(
    hours: int = Query(24, ge=1, le=720),
) -> dict:
    from core.services.admin_security_audit_service import AdminSecurityAuditService
    svc = AdminSecurityAuditService
    dashboard = svc.build_security_dashboard(
        login_attempts=[], sessions=[], audit_entries=[],
        period_hours=hours,
    )
    return {
        "login_metrics": _metrics_to_dict(dashboard.login_metrics),
        "session_metrics": _metrics_to_dict(dashboard.session_metrics),
        "denied_metrics": _metrics_to_dict(dashboard.denied_metrics),
        "sensitive_metrics": _metrics_to_dict(dashboard.sensitive_metrics),
        "suspicious": [_indicator_to_dict(s) for s in dashboard.suspicious],
        "recommendations": [_rec_to_dict(r) for r in dashboard.recommendations],
        "generated_at": dashboard.generated_at,
        "period_hours": dashboard.period_hours,
        "note": "Empty DB — no data yet",
    }


@router.get("/login-attempts")
async def list_login_attempts(
    status: str = Query(""),
    admin_id: str = Query(""),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    return {
        "attempts": [],
        "total": 0,
        "filters": {"status": status, "admin_id": admin_id},
        "note": "Empty DB — no data yet",
    }


@router.get("/sessions")
async def list_sessions(
    status: str = Query(""),
    admin_id: str = Query(""),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    return {
        "sessions": [],
        "total": 0,
        "filters": {"status": status, "admin_id": admin_id},
        "note": "Empty DB — no data yet",
    }


@router.get("/audit-events")
async def list_audit_events(
    action: str = Query(""),
    actor_admin_id: str = Query(""),
    status: str = Query(""),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict:
    return {
        "events": [],
        "total": 0,
        "filters": {"action": action, "actor_admin_id": actor_admin_id, "status": status},
        "note": "Empty DB — no data yet",
    }


@router.get("/suspicious-activity")
async def suspicious_activity(
    hours: int = Query(24, ge=1, le=720),
) -> dict:
    from core.services.admin_security_audit_service import AdminSecurityAuditService
    svc = AdminSecurityAuditService
    from core.services.admin_security_audit_service import (
        LoginAttemptMetrics, SessionMetrics, PermissionDeniedMetrics, SensitiveActionMetrics,
    )
    indicators = svc.detect_suspicious_activity(
        LoginAttemptMetrics(), SessionMetrics(),
        PermissionDeniedMetrics(), SensitiveActionMetrics(),
    )
    return {
        "indicators": [_indicator_to_dict(i) for i in indicators],
        "hours": hours,
        "note": "Empty DB — no data yet",
    }


def _metrics_to_dict(obj: object) -> dict:
    from dataclasses import asdict
    return asdict(obj)  # type: ignore[arg-type]


def _indicator_to_dict(obj: object) -> dict:
    from dataclasses import asdict
    return asdict(obj)  # type: ignore[arg-type]


def _rec_to_dict(obj: object) -> dict:
    from dataclasses import asdict
    return asdict(obj)  # type: ignore[arg-type]
