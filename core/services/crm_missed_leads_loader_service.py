"""Real missed-leads loader — read-only, deterministic, no fake numbers.

Definition (deterministic, reliable columns only):
  A contact is a MISSED lead in the selected range if their LATEST message in
  the range is INBOUND — i.e. the customer wrote last and no outbound reply came
  after that latest inbound message. Wait time is now − latest inbound time.

Severity is derived from wait time only (created_at is reliable); it does NOT
use intent/temperature/phone, which the bot writes as constants. Those
reason-categories therefore stay 0 in the summary (honest, not fabricated).
The output feeds the existing build_summary / build_recommendations aggregation
unchanged.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from core.schemas.crm_missed_leads import MissedLeadItem
from core.services.crm_daily_summary_service import Period
from core.services.crm_missed_leads_service import mask_phone
from infrastructure.database.models.crm_contact import CRMContactModel
from infrastructure.database.models.crm_message import CRMMessageModel

_DIR_IN = "inbound"
_DIR_OUT = "outbound"
_LIST_LIMIT = 100


def classify_wait_severity(minutes: int) -> str:
    """Deterministic severity from wait minutes (no unreliable inputs)."""
    if minutes >= 180:
        return "critical"
    if minutes >= 60:
        return "high"
    if minutes >= 15:
        return "medium"
    return "low"


def compute_missed_contacts(rows: list[tuple[int, datetime, str]], now: datetime) -> dict[int, int]:
    """Pure: from (contact_id, created_at, direction) rows, return
    {contact_id: minutes_waiting} for contacts whose LATEST message is inbound.

    Handles all cases: inbound-only (missed), inbound→outbound (answered, not
    missed), outbound→inbound (missed — an earlier outbound is not a reply to the
    later inbound), and picks the latest by created_at. Internal "agent_trace"
    rows are ignored so they never mask a genuinely unanswered inbound.
    """
    latest: dict[int, tuple[datetime, str]] = {}
    for contact_id, created_at, direction in rows:
        if direction not in (_DIR_IN, _DIR_OUT):
            continue  # ignore agent_trace / non-customer-facing rows
        prev = latest.get(contact_id)
        if prev is None or created_at > prev[0]:
            latest[contact_id] = (created_at, direction)
    missed: dict[int, int] = {}
    for contact_id, (created_at, direction) in latest.items():
        if direction == _DIR_IN:
            minutes = int((now - created_at).total_seconds() // 60)
            missed[contact_id] = max(minutes, 0)
    return missed


def _display_name(c: CRMContactModel) -> str:
    name = " ".join(p for p in (c.first_name, c.last_name) if p).strip()
    if name:
        return name
    if c.username:
        return f"@{c.username}"
    return f"Kontakt #{c.id}"


async def collect_missed_items(
    session: AsyncSession, period: Period, limit: int = _LIST_LIMIT
) -> list[MissedLeadItem]:
    """Load real missed-lead items for the period. Read-only."""
    start, end = period.start, period.end
    rows = (
        await session.execute(
            sa.select(
                CRMMessageModel.contact_id,
                CRMMessageModel.created_at,
                CRMMessageModel.direction,
            ).where(CRMMessageModel.created_at >= start, CRMMessageModel.created_at < end)
        )
    ).all()
    missed = compute_missed_contacts([(r.contact_id, r.created_at, r.direction) for r in rows], end)
    if not missed:
        return []

    contacts = (
        (
            await session.execute(
                sa.select(CRMContactModel).where(CRMContactModel.id.in_(list(missed.keys())))
            )
        )
        .scalars()
        .all()
    )
    by_id = {c.id: c for c in contacts}

    items: list[MissedLeadItem] = []
    for contact_id, minutes in missed.items():
        c = by_id.get(contact_id)
        items.append(
            MissedLeadItem(
                contact_id=contact_id,
                display_name=_display_name(c) if c else f"Kontakt #{contact_id}",
                phone_masked=(mask_phone(c.phone) if c else None),
                lead_score=(c.lead_score if c else 0),
                temperature=(c.temperature or "cold") if c else "cold",
                reason="unanswered",
                severity=classify_wait_severity(minutes),
                minutes_waiting=minutes,
                next_action="Operatorga yo'naltirish",
            )
        )
    items.sort(key=lambda i: i.minutes_waiting, reverse=True)
    return items[:limit]
