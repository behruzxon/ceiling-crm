"""Operator daily digest — pure functions, no DB, no Telegram, no OpenAI.

The digest is built entirely from in-memory input lists; the API layer or
scheduler is responsible for fetching them. Output is structured + a
sanitized text preview safe for internal admin/operator surfaces.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any

from core.schemas.crm_operator_digest import (
    OperatorDigestItem,
    OperatorDigestRecommendation,
    OperatorDigestResult,
    OperatorDigestSummary,
    OperatorWorkloadEntry,
)

_TOKEN_RE = re.compile(r"(sk-[a-zA-Z0-9]{8,}|Bearer\s+\S{10,})", re.I)
_PHONE_RE = re.compile(r"\+?\d{7,}")

EXPIRABLE_STATUSES = frozenset({"open", "waiting_phone", "assigned"})
ACTIVE_STATUSES = frozenset({"open", "waiting_phone", "assigned"})

SEVERITY_GREEN = "green"
SEVERITY_YELLOW = "yellow"
SEVERITY_RED = "red"


def sanitize_preview(text: str | None, max_len: int = 200) -> str | None:
    """Redact tokens and phone numbers from a free-text preview.

    Phone strings are replaced with ``[PHONE]`` to prevent leakage in
    digest text rendered to admin surfaces.
    """
    if not text:
        return None
    cleaned = _TOKEN_RE.sub("[REDACTED]", text)
    cleaned = _PHONE_RE.sub("[PHONE]", cleaned)
    return cleaned[:max_len]


def _coerce_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _get(d: Any, key: str, default: Any = None) -> Any:
    """Read a key from dict or attribute from object — tolerant of both."""
    if isinstance(d, dict):
        return d.get(key, default)
    return getattr(d, key, default)


def _minutes_between(start: datetime | None, end: datetime) -> int:
    s = _coerce_aware(start)
    if s is None:
        return 0
    try:
        delta = end - s
    except TypeError:
        return 0
    return max(0, int(delta.total_seconds() // 60))


def build_handoff_metrics(
    handoffs: list[Any],
    *,
    now: datetime,
) -> dict[str, int]:
    """Count handoff rows by status / priority / today-flag.

    Returns plain dict so callers can compose metrics flexibly.
    ``today`` is defined as last 24h from ``now`` (timezone-aware).
    """
    today_cutoff = now - timedelta(hours=24)

    total_open = 0
    waiting_phone = 0
    assigned = 0
    contacted_today = 0
    resolved_today = 0
    expired_today = 0
    urgent_open = 0
    high_open = 0
    oldest_wait_minutes = 0

    for row in handoffs or []:
        status = _get(row, "status") or ""
        priority = _get(row, "priority") or ""
        created_at = _coerce_aware(_get(row, "created_at"))
        updated_at = _coerce_aware(_get(row, "updated_at"))
        contacted_at = _coerce_aware(_get(row, "contacted_at"))
        resolved_at = _coerce_aware(_get(row, "resolved_at"))

        if status == "open":
            total_open += 1
        if status == "waiting_phone":
            waiting_phone += 1
        if status == "assigned":
            assigned += 1

        if status in ACTIVE_STATUSES:
            wait = _minutes_between(created_at, now)
            if wait > oldest_wait_minutes:
                oldest_wait_minutes = wait
            if priority == "urgent":
                urgent_open += 1
            elif priority == "high":
                high_open += 1

        if status == "contacted":
            ts = contacted_at or updated_at
            if ts is not None and ts >= today_cutoff:
                contacted_today += 1
        if status == "resolved":
            ts = resolved_at or updated_at
            if ts is not None and ts >= today_cutoff:
                resolved_today += 1
        if status == "expired":
            ts = updated_at
            if ts is not None and ts >= today_cutoff:
                expired_today += 1

    return {
        "total_open": total_open,
        "waiting_phone": waiting_phone,
        "assigned": assigned,
        "contacted_today": contacted_today,
        "resolved_today": resolved_today,
        "expired_today": expired_today,
        "urgent_open": urgent_open,
        "high_open": high_open,
        "oldest_wait_minutes": oldest_wait_minutes,
    }


def build_missed_lead_metrics(missed_leads: list[Any]) -> dict[str, int]:
    """Count missed-lead rows by severity / reason."""
    total = len(missed_leads or [])
    critical = 0
    high = 0
    hot_unanswered = 0
    operator_waiting = 0
    phone_shared_no_followup = 0

    for row in missed_leads or []:
        severity = (_get(row, "severity") or "").lower()
        reason = (_get(row, "reason") or "").lower()
        if severity == "critical":
            critical += 1
        elif severity == "high":
            high += 1
        if reason == "hot_unanswered":
            hot_unanswered += 1
        if reason == "operator_waiting":
            operator_waiting += 1
        if reason == "phone_shared_no_followup":
            phone_shared_no_followup += 1

    return {
        "total_missed": total,
        "critical_missed": critical,
        "high_missed": high,
        "hot_unanswered": hot_unanswered,
        "operator_waiting": operator_waiting,
        "phone_shared_no_followup": phone_shared_no_followup,
    }


def build_workload_summary(
    handoffs: list[Any],
    *,
    now: datetime,
) -> list[OperatorWorkloadEntry]:
    """Per-operator open workload, urgent count, oldest assigned minutes."""
    by_op: dict[str, OperatorWorkloadEntry] = {}

    for row in handoffs or []:
        status = _get(row, "status") or ""
        if status not in ACTIVE_STATUSES:
            continue
        admin_id = _get(row, "assigned_to_admin_id") or "unassigned"
        admin_id = str(admin_id)
        priority = _get(row, "priority") or ""
        assigned_at = _coerce_aware(_get(row, "assigned_at"))

        entry = by_op.setdefault(
            admin_id,
            OperatorWorkloadEntry(operator_id=admin_id),
        )
        entry.assigned_open += 1
        if priority == "urgent":
            entry.urgent_assigned += 1
        age = _minutes_between(assigned_at, now)
        if age > entry.oldest_assigned_minutes:
            entry.oldest_assigned_minutes = age

    return sorted(by_op.values(), key=lambda e: (-e.urgent_assigned, -e.assigned_open))


def calculate_digest_severity(handoff_m: dict[str, int], missed_m: dict[str, int]) -> str:
    """Decide green / yellow / red overall severity."""
    critical_missed = missed_m.get("critical_missed", 0)
    urgent_open = handoff_m.get("urgent_open", 0)
    high_open = handoff_m.get("high_open", 0)
    high_missed = missed_m.get("high_missed", 0)
    oldest = handoff_m.get("oldest_wait_minutes", 0)

    if critical_missed > 0:
        return SEVERITY_RED
    if urgent_open > 0 and oldest >= 60:
        return SEVERITY_RED
    if urgent_open >= 3:
        return SEVERITY_RED
    if high_open > 0 or high_missed > 0 or urgent_open > 0:
        return SEVERITY_YELLOW
    if oldest >= 120:
        return SEVERITY_YELLOW
    return SEVERITY_GREEN


def build_recommendations(
    handoff_m: dict[str, int],
    missed_m: dict[str, int],
) -> list[OperatorDigestRecommendation]:
    """Build prioritized operator instructions.

    Each recommendation is a non-actionable internal hint — no real send.
    """
    recs: list[OperatorDigestRecommendation] = []

    if missed_m.get("critical_missed", 0) > 0:
        recs.append(
            OperatorDigestRecommendation(
                rank=len(recs) + 1,
                text="Critical missed leadlarga javob bering",
                severity="critical",
            )
        )
    if handoff_m.get("urgent_open", 0) > 0:
        recs.append(
            OperatorDigestRecommendation(
                rank=len(recs) + 1,
                text="Avval urgent handofflarni ko'ring",
                severity="critical",
            )
        )
    if handoff_m.get("waiting_phone", 0) > 0:
        recs.append(
            OperatorDigestRecommendation(
                rank=len(recs) + 1,
                text="Telefon qoldirgan mijozlarga aloqani tekshiring",
                severity="high",
            )
        )
    if handoff_m.get("expired_today", 0) > 0:
        recs.append(
            OperatorDigestRecommendation(
                rank=len(recs) + 1,
                text="Expired bo'lgan handofflarni review qiling",
                severity="high",
            )
        )
    if handoff_m.get("high_open", 0) > 0:
        recs.append(
            OperatorDigestRecommendation(
                rank=len(recs) + 1,
                text="High priority handofflarni navbat bo'yicha oling",
                severity="medium",
            )
        )
    if missed_m.get("hot_unanswered", 0) > 0:
        recs.append(
            OperatorDigestRecommendation(
                rank=len(recs) + 1,
                text="Hot leadlarga javob qaytaring",
                severity="medium",
            )
        )
    if not recs:
        recs.append(
            OperatorDigestRecommendation(
                rank=1,
                text="Navbat tinch. Yangi handofflar uchun kuzatuvni davom ettiring.",
                severity="info",
            )
        )
    return recs


def _build_items(
    handoff_m: dict[str, int],
    missed_m: dict[str, int],
) -> list[OperatorDigestItem]:
    return [
        OperatorDigestItem(
            metric_key="total_open",
            label="Open handofflar",
            value=handoff_m.get("total_open", 0),
            severity="warning" if handoff_m.get("total_open", 0) > 0 else "info",
        ),
        OperatorDigestItem(
            metric_key="waiting_phone",
            label="Telefon kutilmoqda",
            value=handoff_m.get("waiting_phone", 0),
            severity="warning" if handoff_m.get("waiting_phone", 0) > 0 else "info",
        ),
        OperatorDigestItem(
            metric_key="assigned",
            label="Tayinlangan",
            value=handoff_m.get("assigned", 0),
        ),
        OperatorDigestItem(
            metric_key="urgent_open",
            label="Urgent ochiq",
            value=handoff_m.get("urgent_open", 0),
            severity="danger" if handoff_m.get("urgent_open", 0) > 0 else "info",
        ),
        OperatorDigestItem(
            metric_key="high_open",
            label="High ochiq",
            value=handoff_m.get("high_open", 0),
            severity="warning" if handoff_m.get("high_open", 0) > 0 else "info",
        ),
        OperatorDigestItem(
            metric_key="contacted_today",
            label="Bugun bog'lanildi",
            value=handoff_m.get("contacted_today", 0),
            severity="success",
        ),
        OperatorDigestItem(
            metric_key="resolved_today",
            label="Bugun hal qilindi",
            value=handoff_m.get("resolved_today", 0),
            severity="success",
        ),
        OperatorDigestItem(
            metric_key="expired_today",
            label="Bugun muddati o'tdi",
            value=handoff_m.get("expired_today", 0),
            severity="warning" if handoff_m.get("expired_today", 0) > 0 else "info",
        ),
        OperatorDigestItem(
            metric_key="oldest_wait_minutes",
            label="Eng eski kutish (min)",
            value=handoff_m.get("oldest_wait_minutes", 0),
            severity="warning" if handoff_m.get("oldest_wait_minutes", 0) >= 60 else "info",
        ),
        OperatorDigestItem(
            metric_key="total_missed",
            label="Missed leadlar",
            value=missed_m.get("total_missed", 0),
            severity="warning" if missed_m.get("total_missed", 0) > 0 else "info",
        ),
        OperatorDigestItem(
            metric_key="critical_missed",
            label="Critical missed",
            value=missed_m.get("critical_missed", 0),
            severity="danger" if missed_m.get("critical_missed", 0) > 0 else "info",
        ),
        OperatorDigestItem(
            metric_key="hot_unanswered",
            label="Hot lead javobsiz",
            value=missed_m.get("hot_unanswered", 0),
            severity="warning" if missed_m.get("hot_unanswered", 0) > 0 else "info",
        ),
    ]


def build_digest(
    *,
    now: datetime | None = None,
    handoffs: list[Any] | None = None,
    missed_leads: list[Any] | None = None,
) -> OperatorDigestResult:
    """Orchestrator — assemble a complete OperatorDigestResult.

    All inputs are optional. Empty inputs produce a green "all quiet"
    digest, never raising.
    """
    ref_now = _coerce_aware(now) or datetime.now(UTC)
    handoffs = handoffs or []
    missed_leads = missed_leads or []

    handoff_m = build_handoff_metrics(handoffs, now=ref_now)
    missed_m = build_missed_lead_metrics(missed_leads)
    workload = build_workload_summary(handoffs, now=ref_now)
    severity = calculate_digest_severity(handoff_m, missed_m)
    items = _build_items(handoff_m, missed_m)
    recs = build_recommendations(handoff_m, missed_m)

    summary = OperatorDigestSummary(
        severity=severity,
        total_open=handoff_m["total_open"],
        waiting_phone=handoff_m["waiting_phone"],
        assigned=handoff_m["assigned"],
        contacted_today=handoff_m["contacted_today"],
        resolved_today=handoff_m["resolved_today"],
        expired_today=handoff_m["expired_today"],
        urgent_open=handoff_m["urgent_open"],
        high_open=handoff_m["high_open"],
        oldest_wait_minutes=handoff_m["oldest_wait_minutes"],
        total_missed=missed_m["total_missed"],
        critical_missed=missed_m["critical_missed"],
        high_missed=missed_m["high_missed"],
        hot_unanswered=missed_m["hot_unanswered"],
        operator_waiting=missed_m["operator_waiting"],
        phone_shared_no_followup=missed_m["phone_shared_no_followup"],
    )

    return OperatorDigestResult(
        summary=summary,
        metrics=items,
        recommendations=recs,
        workload=workload,
        generated_at=ref_now,
    )


def format_digest_text(result: OperatorDigestResult) -> str:
    """Render a sanitized internal-only text preview.

    Guarantees:
      * No raw phone numbers (phone-shaped substrings are masked).
      * No tokens / Bearer / sk- prefixes.
      * No fake ETA wording.
      * No user-facing greeting; internal tone only.
    """
    s = result.summary
    lines: list[str] = []
    badge = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(s.severity, "⚪")
    lines.append(f"{badge} CRM Operator Digest — {s.severity.upper()}")
    if result.generated_at is not None:
        lines.append(f"Hisobot vaqti: {result.generated_at.isoformat(timespec='minutes')}")
    lines.append("")
    lines.append("Handofflar:")
    lines.append(f"  Open:            {s.total_open}")
    lines.append(f"  Telefon kutadi:  {s.waiting_phone}")
    lines.append(f"  Tayinlangan:     {s.assigned}")
    lines.append(f"  Urgent ochiq:    {s.urgent_open}")
    lines.append(f"  High ochiq:      {s.high_open}")
    lines.append(f"  Bugun bog'land:  {s.contacted_today}")
    lines.append(f"  Bugun hal:       {s.resolved_today}")
    lines.append(f"  Bugun expired:   {s.expired_today}")
    lines.append(f"  Eng eski (min):  {s.oldest_wait_minutes}")
    lines.append("")
    lines.append("Missed leadlar:")
    lines.append(f"  Jami:            {s.total_missed}")
    lines.append(f"  Critical:        {s.critical_missed}")
    lines.append(f"  High:            {s.high_missed}")
    lines.append(f"  Hot javobsiz:    {s.hot_unanswered}")
    lines.append("")
    if result.workload:
        lines.append("Operator yuklamasi:")
        for w in result.workload[:5]:
            lines.append(
                f"  {w.operator_id}: open={w.assigned_open} "
                f"urgent={w.urgent_assigned} eski={w.oldest_assigned_minutes}m"
            )
        lines.append("")
    lines.append("Tavsiyalar:")
    for r in result.recommendations:
        lines.append(f"  {r.rank}. {r.text}")

    text = "\n".join(lines)
    # Final pass: scrub any phone/token that may have leaked in via labels.
    return sanitize_preview(text, max_len=4000) or ""
