"""Unknown Questions Inbox API — read-mostly admin feedback loop.

Exposes the ``agent_unknown_questions`` capture table to the admin web platform:

* ``GET  /api/v1/admin/agent/unknown-questions``          — filtered list
* ``GET  /api/v1/admin/agent/unknown-questions/summary``  — KPI summary
* ``POST /api/v1/admin/agent/unknown-questions/{id}/review`` — triage (status + note)

Safety: every route requires ``require_api_token``. There is **no** send action,
**no** content / FAQ / price mutation, and **no** model or Telegram call here.
The review endpoint only updates the row's ``status`` / ``admin_note`` (triage),
nothing more.
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query

from apps.api.dependencies.auth import require_api_token
from core.services.unknown_question_service import SEVERITIES, STATUSES
from infrastructure.database.models.agent_unknown_question import AgentUnknownQuestionModel
from infrastructure.database.session import get_db

router = APIRouter(
    prefix="/api/v1/admin/agent/unknown-questions",
    tags=["unknown-questions"],
    dependencies=[Depends(require_api_token)],
)


def _row_to_dict(row: AgentUnknownQuestionModel) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "source": row.source,
        "channel_user_id": row.channel_user_id,
        "crm_contact_id": row.crm_contact_id,
        "original_text_preview": row.original_text_preview,
        "bot_reply_preview": row.bot_reply_preview,
        "reason": row.reason,
        "intent": row.intent,
        "live_route": row.live_route,
        "sdm_intent": row.sdm_intent,
        "sdm_next_action": row.sdm_next_action,
        "order_readiness_score": row.order_readiness_score,
        "severity": row.severity,
        "status": row.status,
        "admin_note": row.admin_note,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
        "reviewed_by": row.reviewed_by,
    }


@router.get("")
async def list_unknown_questions(
    status: str = Query(default="", max_length=20),
    reason: str = Query(default="", max_length=40),
    severity: str = Query(default="", max_length=10),
    q: str = Query(default="", max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db=Depends(get_db),
) -> dict:
    """Return a filtered, paginated list of captured unknown questions."""
    query = sa.select(AgentUnknownQuestionModel).order_by(
        AgentUnknownQuestionModel.created_at.desc()
    )
    if status:
        query = query.where(AgentUnknownQuestionModel.status == status)
    if reason:
        query = query.where(AgentUnknownQuestionModel.reason == reason)
    if severity:
        query = query.where(AgentUnknownQuestionModel.severity == severity)
    if q:
        query = query.where(AgentUnknownQuestionModel.original_text_preview.ilike(f"%{q}%"))
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    rows = result.scalars().all()
    return {"items": [_row_to_dict(r) for r in rows], "count": len(rows)}


@router.get("/summary")
async def unknown_questions_summary(
    db=Depends(get_db),
) -> dict:
    """KPI summary for the inbox header.

    ``bot_failure_rate`` is intentionally ``None``: an exact rate needs a
    reliable denominator (total handled conversations in the window) which this
    capture table does not hold. The placeholder + note are surfaced so the UI
    can show "not yet available" rather than a misleading number.
    """
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    counts = await db.execute(
        sa.select(
            sa.func.count().label("total"),
            sa.func.count().filter(AgentUnknownQuestionModel.status == "new").label("total_new"),
            sa.func.count()
            .filter(AgentUnknownQuestionModel.severity.in_(("high", "critical")))
            .label("high_severity"),
            sa.func.count()
            .filter(AgentUnknownQuestionModel.created_at >= today_start)
            .label("today_count"),
        ).select_from(AgentUnknownQuestionModel)
    )
    row = counts.one()

    reasons_result = await db.execute(
        sa.select(
            AgentUnknownQuestionModel.reason,
            sa.func.count().label("cnt"),
        )
        .group_by(AgentUnknownQuestionModel.reason)
        .order_by(sa.desc("cnt"))
        .limit(5)
    )
    top_reasons = [{"reason": r.reason, "count": r.cnt} for r in reasons_result]

    return {
        "total": row.total,
        "total_new": row.total_new,
        "high_severity": row.high_severity,
        "today_count": row.today_count,
        "top_reasons": top_reasons,
        "top_reason": top_reasons[0]["reason"] if top_reasons else None,
        "bot_failure_rate": None,
        "bot_failure_rate_note": "denominator (handled conversations) not yet available",
    }


@router.post("/{question_id}/review")
async def review_unknown_question(
    question_id: int,
    body: dict | None = None,
    db=Depends(get_db),
) -> dict:
    """Triage one captured question: set its ``status`` and optional ``admin_note``.

    This is the only write here — it does NOT send a message, create an FAQ, or
    change any bot content. Those are deliberately out of scope for this sprint.
    """
    body = body or {}
    new_status = str(body.get("status", "")).strip()
    if new_status and new_status not in STATUSES:
        raise HTTPException(status_code=422, detail="invalid status")

    result = await db.execute(
        sa.select(AgentUnknownQuestionModel).where(AgentUnknownQuestionModel.id == question_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown question not found")

    if new_status:
        row.status = new_status
    if "admin_note" in body:
        note = body.get("admin_note")
        row.admin_note = str(note)[:1000] if note is not None else None
    reviewer = body.get("reviewed_by")
    row.reviewed_by = str(reviewer)[:50] if reviewer else "admin"
    row.reviewed_at = datetime.now(UTC)
    row.updated_at = datetime.now(UTC)
    await db.commit()
    return {"status": row.status, "id": question_id}


# Severities re-exported for callers/tests that want the canonical tuple.
__all__ = ["router", "SEVERITIES"]
