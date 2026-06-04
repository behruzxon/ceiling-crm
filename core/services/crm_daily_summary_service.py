"""CRMDailySummaryService — read-only daily statistics for the dashboard.

Pure aggregation over EXISTING CRM tables (crm_contacts, crm_messages,
crm_operator_handoff_requests, agent_unknown_questions). No writes, no
migrations, no fake numbers.

Honesty about reliability: per-message INTENT (price/catalog), channel SOURCE,
and contact TEMPERATURE are written with constant placeholders by the current
bot flow (crm_message_service message_type='text', crm_contact_service
source='telegram_bot', temperature never set), so they are reported as
unavailable (null + reliability=false) instead of invented. Everything else is
computed from trustworthy timestamped columns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models.agent_unknown_question import AgentUnknownQuestionModel
from infrastructure.database.models.crm_contact import CRMContactModel
from infrastructure.database.models.crm_message import CRMMessageModel
from infrastructure.database.models.crm_operator_handoff import CRMOperatorHandoffModel

VALID_RANGES: tuple[str, ...] = ("today", "7d", "30d")
DEFAULT_TIMEZONE: str = "Asia/Tashkent"
_FALLBACK_TZ = timezone(timedelta(hours=5))  # UTC+5, mirrors shared/utils/business_hours.py
_UNKNOWN_LIST_LIMIT = 10

# Direction values written by crm_message_service: inbound / outbound / agent_trace.
_DIR_IN = "inbound"
_DIR_OUT = "outbound"


def validate_range(range_: str) -> str:
    """Return the range if valid, else raise ValueError."""
    if range_ not in VALID_RANGES:
        raise ValueError(f"invalid range '{range_}'; expected one of {list(VALID_RANGES)}")
    return range_


def _resolve_tz(tz_name: str) -> timezone:
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(tz_name)  # type: ignore[return-value]
    except Exception:
        return _FALLBACK_TZ


@dataclass(frozen=True)
class Period:
    start: datetime
    end: datetime
    timezone: str


def resolve_period(range_: str, now: datetime, tz_name: str = DEFAULT_TIMEZONE) -> Period:
    """Compute the [start, end) window for the range. ``now`` is injected so the
    calculation is deterministic and testable."""
    validate_range(range_)
    tz = _resolve_tz(tz_name)
    local_now = now.astimezone(tz)
    end = local_now
    if range_ == "today":
        start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif range_ == "7d":
        start = local_now - timedelta(days=7)
    else:  # 30d
        start = local_now - timedelta(days=30)
    return Period(start=start, end=end, timezone=tz_name)


@dataclass
class RawCounts:
    """Trustworthy counts fetched from the DB (intent/source/temperature excluded)."""

    incoming_messages: int = 0
    outgoing_messages: int = 0
    new_contacts: int = 0
    operator_requests: int = 0
    missed_leads: int = 0
    unknown_questions: int = 0
    open_handoffs: int = 0
    assigned_handoffs: int = 0
    resolved_handoffs: int = 0
    hourly_messages: dict[int, int] = field(default_factory=dict)
    hourly_new_contacts: dict[int, int] = field(default_factory=dict)
    unknown_items: list[dict] = field(default_factory=list)


def empty_hourly() -> list[dict]:
    """24 zero buckets, hours 0..23."""
    return [{"hour": h, "messages": 0, "new_contacts": 0} for h in range(24)]


def _build_hourly(raw: RawCounts) -> list[dict]:
    buckets = empty_hourly()
    for h, n in raw.hourly_messages.items():
        if 0 <= h <= 23:
            buckets[h]["messages"] = int(n)
    for h, n in raw.hourly_new_contacts.items():
        if 0 <= h <= 23:
            buckets[h]["new_contacts"] = int(n)
    return buckets


def _build_warnings(raw: RawCounts) -> list[dict]:
    """Warning cards from REAL signals only — never from a stub/zero source."""
    warnings: list[dict] = []
    if raw.open_handoffs > 0:
        warnings.append({"type": "needs_operator", "count": raw.open_handoffs, "severity": "high"})
    if raw.missed_leads > 0:
        warnings.append({"type": "missed", "count": raw.missed_leads, "severity": "medium"})
    if raw.unknown_questions > 0:
        warnings.append({"type": "unknown", "count": raw.unknown_questions, "severity": "medium"})
    return warnings


def shape_summary(range_: str, period: Period, raw: RawCounts) -> dict:
    """Pure assembly of the API response from raw counts."""
    return {
        "range": range_,
        "period": {
            "start": period.start.isoformat(),
            "end": period.end.isoformat(),
            "timezone": period.timezone,
        },
        "kpis": {
            "total_messages": raw.incoming_messages + raw.outgoing_messages,
            "incoming_messages": raw.incoming_messages,
            "outgoing_messages": raw.outgoing_messages,
            "new_contacts": raw.new_contacts,
            # Intent is not reliably stored (message_type constant) → unavailable.
            "price_requests": None,
            "catalog_requests": None,
            "operator_requests": raw.operator_requests,
            "missed_leads": raw.missed_leads,
            "unknown_questions": raw.unknown_questions,
            # Temperature is not written by the bot flow → unavailable.
            "hot_leads": None,
            "warm_leads": None,
            "cold_leads": None,
            "open_handoffs": raw.open_handoffs,
            "assigned_handoffs": raw.assigned_handoffs,
            "resolved_handoffs": raw.resolved_handoffs,
        },
        "hourly_activity": _build_hourly(raw),
        # Deferred: top customer questions need text-normalisation grouping (later step).
        "top_questions": [],
        "unknown_questions": raw.unknown_items,
        "warnings": _build_warnings(raw),
        "data_quality": {
            "intent_reliable": False,
            "source_reliable": False,
            "temperature_reliable": False,
        },
    }


def _hour_expr(col: sa.Column, tz_name: str) -> sa.ColumnElement:
    """extract(hour from <ts> AT TIME ZONE <tz>) — local-hour bucket (Postgres)."""
    return sa.extract("hour", sa.func.timezone(tz_name, col))


async def collect_raw_counts(session: AsyncSession, period: Period) -> RawCounts:
    """Run all read-only aggregation queries for the period. No writes."""
    start, end, tz = period.start, period.end, period.timezone
    raw = RawCounts()

    # ── messages by direction ────────────────────────────────────────────────
    dir_rows = (
        await session.execute(
            sa.select(CRMMessageModel.direction, sa.func.count())
            .where(CRMMessageModel.created_at >= start, CRMMessageModel.created_at < end)
            .group_by(CRMMessageModel.direction)
        )
    ).all()
    for direction, count in dir_rows:
        if direction == _DIR_IN:
            raw.incoming_messages = int(count)
        elif direction == _DIR_OUT:
            raw.outgoing_messages = int(count)

    # ── new contacts ─────────────────────────────────────────────────────────
    raw.new_contacts = int(
        (
            await session.execute(
                sa.select(sa.func.count())
                .select_from(CRMContactModel)
                .where(CRMContactModel.created_at >= start, CRMContactModel.created_at < end)
            )
        ).scalar_one()
    )

    # ── operator requests (handoffs created in range) ────────────────────────
    raw.operator_requests = int(
        (
            await session.execute(
                sa.select(sa.func.count())
                .select_from(CRMOperatorHandoffModel)
                .where(
                    CRMOperatorHandoffModel.created_at >= start,
                    CRMOperatorHandoffModel.created_at < end,
                )
            )
        ).scalar_one()
    )

    # ── handoff queue state (open/assigned current) + resolved-in-range ──────
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

    # ── missed = contacts with inbound but NO outbound in range ──────────────
    inbound_ids = set(
        (
            await session.execute(
                sa.select(CRMMessageModel.contact_id)
                .where(
                    CRMMessageModel.direction == _DIR_IN,
                    CRMMessageModel.created_at >= start,
                    CRMMessageModel.created_at < end,
                )
                .distinct()
            )
        )
        .scalars()
        .all()
    )
    replied_ids = set(
        (
            await session.execute(
                sa.select(CRMMessageModel.contact_id)
                .where(
                    CRMMessageModel.direction == _DIR_OUT,
                    CRMMessageModel.created_at >= start,
                    CRMMessageModel.created_at < end,
                )
                .distinct()
            )
        )
        .scalars()
        .all()
    )
    raw.missed_leads = len(inbound_ids - replied_ids)

    # ── unknown questions count + recent list ────────────────────────────────
    raw.unknown_questions = int(
        (
            await session.execute(
                sa.select(sa.func.count())
                .select_from(AgentUnknownQuestionModel)
                .where(
                    AgentUnknownQuestionModel.created_at >= start,
                    AgentUnknownQuestionModel.created_at < end,
                )
            )
        ).scalar_one()
    )
    uq_rows = (
        await session.execute(
            sa.select(
                AgentUnknownQuestionModel.id,
                AgentUnknownQuestionModel.original_text_preview,
                AgentUnknownQuestionModel.reason,
                AgentUnknownQuestionModel.severity,
                AgentUnknownQuestionModel.created_at,
            )
            .where(
                AgentUnknownQuestionModel.created_at >= start,
                AgentUnknownQuestionModel.created_at < end,
            )
            .order_by(AgentUnknownQuestionModel.created_at.desc())
            .limit(_UNKNOWN_LIST_LIMIT)
        )
    ).all()
    raw.unknown_items = [
        {
            "id": r.id,
            "text": r.original_text_preview,
            "reason": r.reason,
            "severity": r.severity,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in uq_rows
    ]

    # ── hourly activity (local hour buckets) ─────────────────────────────────
    msg_hours = (
        await session.execute(
            sa.select(_hour_expr(CRMMessageModel.created_at, tz).label("h"), sa.func.count())
            .where(CRMMessageModel.created_at >= start, CRMMessageModel.created_at < end)
            .group_by("h")
        )
    ).all()
    raw.hourly_messages = {int(h): int(c) for h, c in msg_hours if h is not None}

    contact_hours = (
        await session.execute(
            sa.select(_hour_expr(CRMContactModel.created_at, tz).label("h"), sa.func.count())
            .where(CRMContactModel.created_at >= start, CRMContactModel.created_at < end)
            .group_by("h")
        )
    ).all()
    raw.hourly_new_contacts = {int(h): int(c) for h, c in contact_hours if h is not None}

    return raw


async def build_daily_summary(
    session: AsyncSession,
    *,
    range_: str = "today",
    source: str | None = None,
    timezone_name: str = DEFAULT_TIMEZONE,
    now: datetime | None = None,
) -> dict:
    """Build the daily-summary response.

    ``source`` is accepted for forward-compatibility but intentionally NOT used
    as a filter: crm_contacts.source is a constant placeholder today, so applying
    it would return misleading zeros — data_quality.source_reliable stays False.
    """
    validate_range(range_)
    if now is None:
        now = datetime.now(tz=UTC)
    period = resolve_period(range_, now, timezone_name)
    raw = await collect_raw_counts(session, period)
    return shape_summary(range_, period, raw)
