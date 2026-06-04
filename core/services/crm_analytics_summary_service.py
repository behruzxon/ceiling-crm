"""CRMAnalyticsSummaryService — read-only daily trends for the analytics page.

Replaces the fake all-zero "Visual Charts" with real per-day trends computed
from existing tables (crm_messages, crm_contacts, agent_unknown_questions,
crm_operator_handoff_requests). No writes, no migrations, no fabricated numbers.

Reuses the #34 period helpers (resolve_period / validate_range) so "today/7d/30d"
behaves identically across the dashboard and analytics. Intent/source/temperature
remain unavailable (data_quality=false) — the same honesty contract as #34.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from core.services.crm_daily_summary_service import (
    DEFAULT_TIMEZONE,
    Period,
    resolve_period,
    validate_range,
)
from infrastructure.database.models.agent_unknown_question import AgentUnknownQuestionModel
from infrastructure.database.models.crm_contact import CRMContactModel
from infrastructure.database.models.crm_message import CRMMessageModel
from infrastructure.database.models.crm_operator_handoff import CRMOperatorHandoffModel

_DIR_IN = "inbound"
_DIR_OUT = "outbound"


@dataclass
class TrendRaw:
    """Per-day buckets (keyed by ISO date string) + current handoff state."""

    messages_in: dict[str, int] = field(default_factory=dict)
    messages_out: dict[str, int] = field(default_factory=dict)
    new_contacts: dict[str, int] = field(default_factory=dict)
    unknown: dict[str, int] = field(default_factory=dict)
    open_handoffs: int = 0
    assigned_handoffs: int = 0
    resolved_handoffs: int = 0


def date_skeleton(period: Period) -> list[str]:
    """Inclusive list of ISO date strings from period.start to period.end."""
    start = period.start.date()
    end = period.end.date()
    days = (end - start).days
    return [(start + timedelta(days=i)).isoformat() for i in range(days + 1)]


def shape_analytics_summary(range_: str, period: Period, raw: TrendRaw) -> dict:
    """Pure assembly of the analytics-summary response."""
    dates = date_skeleton(period)
    trend = []
    totals = {
        "messages": 0,
        "incoming": 0,
        "outgoing": 0,
        "new_contacts": 0,
        "unknown_questions": 0,
    }
    for d in dates:
        inc = int(raw.messages_in.get(d, 0))
        out = int(raw.messages_out.get(d, 0))
        nc = int(raw.new_contacts.get(d, 0))
        unk = int(raw.unknown.get(d, 0))
        trend.append(
            {
                "date": d,
                "messages": inc + out,
                "incoming": inc,
                "outgoing": out,
                "new_contacts": nc,
                "unknown_questions": unk,
            }
        )
        totals["messages"] += inc + out
        totals["incoming"] += inc
        totals["outgoing"] += out
        totals["new_contacts"] += nc
        totals["unknown_questions"] += unk
    return {
        "range": range_,
        "period": {
            "start": period.start.isoformat(),
            "end": period.end.isoformat(),
            "timezone": period.timezone,
        },
        "trend": trend,
        "totals": totals,
        "handoffs": {
            "open": raw.open_handoffs,
            "assigned": raw.assigned_handoffs,
            "resolved": raw.resolved_handoffs,
        },
        "data_quality": {
            "intent_reliable": False,
            "source_reliable": False,
            "temperature_reliable": False,
        },
    }


def _day_expr(col: sa.Column, tz_name: str) -> sa.ColumnElement:
    """date(<ts> AT TIME ZONE <tz>) — local calendar day (Postgres)."""
    return sa.func.date(sa.func.timezone(tz_name, col))


async def collect_trend(session: AsyncSession, period: Period) -> TrendRaw:
    """Run the read-only per-day aggregation queries. No writes."""
    start, end, tz = period.start, period.end, period.timezone
    raw = TrendRaw()

    msg_rows = (
        await session.execute(
            sa.select(
                _day_expr(CRMMessageModel.created_at, tz).label("d"),
                CRMMessageModel.direction,
                sa.func.count(),
            )
            .where(CRMMessageModel.created_at >= start, CRMMessageModel.created_at < end)
            .group_by("d", CRMMessageModel.direction)
        )
    ).all()
    for day, direction, count in msg_rows:
        key = day.isoformat() if hasattr(day, "isoformat") else str(day)
        if direction == _DIR_IN:
            raw.messages_in[key] = int(count)
        elif direction == _DIR_OUT:
            raw.messages_out[key] = int(count)

    contact_rows = (
        await session.execute(
            sa.select(_day_expr(CRMContactModel.created_at, tz).label("d"), sa.func.count())
            .where(CRMContactModel.created_at >= start, CRMContactModel.created_at < end)
            .group_by("d")
        )
    ).all()
    raw.new_contacts = {
        (d.isoformat() if hasattr(d, "isoformat") else str(d)): int(c) for d, c in contact_rows
    }

    unk_rows = (
        await session.execute(
            sa.select(
                _day_expr(AgentUnknownQuestionModel.created_at, tz).label("d"), sa.func.count()
            )
            .where(
                AgentUnknownQuestionModel.created_at >= start,
                AgentUnknownQuestionModel.created_at < end,
            )
            .group_by("d")
        )
    ).all()
    raw.unknown = {
        (d.isoformat() if hasattr(d, "isoformat") else str(d)): int(c) for d, c in unk_rows
    }

    hs = (
        await session.execute(
            sa.select(
                sa.func.count().filter(CRMOperatorHandoffModel.status == "open").label("open"),
                sa.func.count()
                .filter(CRMOperatorHandoffModel.status == "assigned")
                .label("assigned"),
                sa.func.count()
                .filter(
                    CRMOperatorHandoffModel.status == "resolved",
                    CRMOperatorHandoffModel.resolved_at >= start,
                    CRMOperatorHandoffModel.resolved_at < end,
                )
                .label("resolved"),
            ).select_from(CRMOperatorHandoffModel)
        )
    ).one()
    raw.open_handoffs = int(hs.open)
    raw.assigned_handoffs = int(hs.assigned)
    raw.resolved_handoffs = int(hs.resolved)
    return raw


async def build_analytics_summary(
    session: AsyncSession,
    *,
    range_: str = "7d",
    timezone_name: str = DEFAULT_TIMEZONE,
    now: datetime | None = None,
) -> dict:
    """Build the analytics-summary trend response."""
    validate_range(range_)
    if now is None:
        now = datetime.now(tz=UTC)
    period = resolve_period(range_, now, timezone_name)
    raw = await collect_trend(session, period)
    return shape_analytics_summary(range_, period, raw)
