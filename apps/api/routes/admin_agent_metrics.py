"""
apps.api.routes.admin_agent_metrics
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Admin endpoints for agent system metrics and execution approval.

GET  /api/v1/admin/agent/metrics/overview
GET  /api/v1/admin/agent/metrics/health
GET  /api/v1/admin/agent/executions/pending
GET  /api/v1/admin/agent/executions/{execution_id}
POST /api/v1/admin/agent/executions/{execution_id}/approve
POST /api/v1/admin/agent/executions/{execution_id}/reject
POST /api/v1/admin/agent/executions/{execution_id}/expire
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies.auth import require_api_token
from infrastructure.database.session import get_db

router = APIRouter(
    prefix="/api/v1/admin/agent",
    tags=["agent-admin"],
    dependencies=[Depends(require_api_token)],
)


@router.get("/control/status")
async def get_control_center_status() -> dict:
    from dataclasses import asdict as _asdict

    from core.services.agent_control_center_service import (
        AgentControlCenterService,
    )
    snapshot = AgentControlCenterService.build_control_center_snapshot()
    return _asdict(snapshot)


@router.get("/metrics/overview")
async def get_agent_overview(
    hours: int = Query(default=24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from core.services.agent_metrics_service import AgentMetricsService

    svc = AgentMetricsService(db)
    since = datetime.now(UTC) - timedelta(hours=hours)
    overview = await svc.get_overview(since=since)
    return asdict(overview)


@router.get("/metrics/health")
async def get_agent_health(
    db: AsyncSession = Depends(get_db),
) -> dict:
    from core.services.agent_metrics_service import AgentMetricsService

    svc = AgentMetricsService(db)
    overview = await svc.get_overview()
    return asdict(overview.health)


@router.get("/executions/pending")
async def get_pending_executions(
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from core.services.agent_execution_queue_service import (
        AgentExecutionQueueService,
    )

    svc = AgentExecutionQueueService(db)
    records = await svc.list_pending(limit=limit)

    items = []
    for r in records:
        safe_payload = dict(r.payload_json or {})
        msg = safe_payload.get("message_text", "")
        if isinstance(msg, str) and len(msg) > 100:
            safe_payload["message_text"] = msg[:100] + "..."

        items.append({
            "execution_id": r.execution_id,
            "telegram_user_id": r.telegram_user_id,
            "action": r.action,
            "mode": r.mode,
            "status": r.status,
            "risk_level": r.risk_level,
            "channel": r.channel,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
        })

    return {"items": items, "count": len(items)}


# ── Request schemas ──────────────────────────────────────────────────────────


class ApproveRequest(BaseModel):
    note: str = Field(default="", max_length=300)


class RejectRequest(BaseModel):
    reason: str = Field(default="", max_length=300)


# ── Execution detail + mutations ─────────────────────────────────────────────


def _check_approval_enabled() -> None:
    from shared.config import get_settings
    if not get_settings().business.agent_execution_api_approval_enabled:
        raise HTTPException(status_code=403, detail="API approval disabled")


@router.get("/executions/{execution_id}")
async def get_execution_detail(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    from core.services.agent_execution_queue_service import (
        AgentExecutionQueueService,
    )
    svc = AgentExecutionQueueService(db)
    record = await svc.get_by_execution_id(execution_id)
    if record is None:
        raise HTTPException(status_code=404, detail="not_found")
    return AgentExecutionQueueService.sanitize_record_for_api(record)


@router.post("/executions/{execution_id}/approve")
async def approve_execution(
    execution_id: str,
    body: ApproveRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    _check_approval_enabled()
    from core.services.agent_execution_queue_service import (
        AgentExecutionQueueService,
    )
    svc = AgentExecutionQueueService(db)
    ok, reason = await svc.approve(execution_id, admin_id=0)
    if not ok:
        if reason == "not_found":
            raise HTTPException(status_code=404, detail=reason)
        raise HTTPException(status_code=409, detail=reason)
    await db.commit()
    return {"status": "approved", "execution_id": execution_id}


@router.post("/executions/{execution_id}/reject")
async def reject_execution(
    execution_id: str,
    body: RejectRequest | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    _check_approval_enabled()
    from core.services.agent_execution_queue_service import (
        AgentExecutionQueueService,
    )
    reason_text = (body.reason if body else "")[:300]
    svc = AgentExecutionQueueService(db)
    ok, reason = await svc.reject(execution_id, admin_id=0, reason=reason_text)
    if not ok:
        if reason == "not_found":
            raise HTTPException(status_code=404, detail=reason)
        raise HTTPException(status_code=409, detail=reason)
    await db.commit()
    return {"status": "rejected", "execution_id": execution_id}


@router.post("/executions/{execution_id}/expire")
async def expire_execution(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    _check_approval_enabled()
    from core.services.agent_execution_queue_service import (
        AgentExecutionQueueService,
    )
    svc = AgentExecutionQueueService(db)
    ok, reason = await svc.expire(execution_id)
    if not ok:
        if reason == "not_found":
            raise HTTPException(status_code=404, detail=reason)
        raise HTTPException(status_code=409, detail=reason)
    await db.commit()
    return {"status": "expired", "execution_id": execution_id}
