"""Operator daily digest API — internal, read-only, no external sends."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query

from apps.api.dependencies.auth import require_api_token
from core.services.crm_operator_digest_service import build_digest, format_digest_text
from infrastructure.database.models.crm_operator_handoff import CRMOperatorHandoffModel
from infrastructure.database.session import get_db

router = APIRouter(
    prefix="/api/v1/admin/crm/operator-digest",
    tags=["operator-digest"],
    dependencies=[Depends(require_api_token)],
)


async def _load_handoffs(db, hours: int) -> list:
    """Load recent + active handoffs for digest computation.

    Includes:
      * any active row (open/waiting_phone/assigned/contacted)
      * any terminal row updated within the window (resolved/cancelled/expired)
    """
    cutoff = datetime.now(UTC) - timedelta(hours=max(1, hours))
    q = sa.select(CRMOperatorHandoffModel).where(
        sa.or_(
            CRMOperatorHandoffModel.status.in_(("open", "waiting_phone", "assigned", "contacted")),
            sa.and_(
                CRMOperatorHandoffModel.status.in_(("resolved", "cancelled", "expired")),
                CRMOperatorHandoffModel.updated_at >= cutoff,
            ),
        )
    )
    result = await db.execute(q)
    return list(result.scalars().all())


def _serialize_result(result) -> dict:
    return {
        "severity": result.summary.severity,
        "summary": asdict(result.summary),
        "metrics": [asdict(m) for m in result.metrics],
        "recommendations": [asdict(r) for r in result.recommendations],
        "workload": [asdict(w) for w in result.workload],
        "generated_at": (
            result.generated_at.isoformat() if result.generated_at is not None else None
        ),
    }


@router.get("/daily")
async def operator_digest_daily(
    hours: int = Query(default=24, ge=1, le=168),
    db=Depends(get_db),
) -> dict:
    """Return today's operator digest as structured JSON."""
    try:
        handoffs = await _load_handoffs(db, hours)
    except Exception:
        handoffs = []
    result = build_digest(
        now=datetime.now(UTC),
        handoffs=handoffs,
        missed_leads=[],
    )
    return _serialize_result(result)


@router.get("/preview")
async def operator_digest_preview(
    hours: int = Query(default=24, ge=1, le=168),
    db=Depends(get_db),
) -> dict:
    """Return a sanitized text preview of the digest. Internal-only."""
    try:
        handoffs = await _load_handoffs(db, hours)
    except Exception:
        handoffs = []
    result = build_digest(
        now=datetime.now(UTC),
        handoffs=handoffs,
        missed_leads=[],
    )
    return {
        "severity": result.summary.severity,
        "generated_at": (
            result.generated_at.isoformat() if result.generated_at is not None else None
        ),
        "text": format_digest_text(result),
    }
