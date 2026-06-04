"""crm_top_questions_service — group the most-asked customer questions.

Read-only, deterministic, privacy-safe. Source: ``agent_unknown_questions`` only
— its ``original_text_preview`` is a sanitized, PII-stripped preview written by
``unknown_question_service``. ``crm_messages.text`` is intentionally NOT used in
v1: it is noisy (greetings/confirmations) and may carry raw PII (phone numbers).

Grouping is by a normalized form of the preview text (lowercase, apostrophe-
folded, punctuation/emoji stripped, whitespace-collapsed). No stemming or
stopword removal — Uzbek morphology is left intact to stay safe and
deterministic. Never fabricates: an empty source yields an empty list.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models.agent_unknown_question import AgentUnknownQuestionModel

TOP_QUESTIONS_SOURCE = "agent_unknown_questions"
_DEFAULT_LIMIT = 10
# Safety bound on rows scanned for grouping (most-recent first). Unknown
# questions are low-volume (only captured bot failures), so this is generous;
# it exists purely to cap a pathological window, not to sample.
_SCAN_CAP = 5000

# Apostrophe-like glyphs folded to one ASCII apostrophe so "oʻlcham",
# "o'lcham", "o`lcham" group together (Uzbek Latin uses oʻ / gʻ).
_APOSTROPHES = ("‘", "’", "ʻ", "ʼ", "`", "´", "′")
_DROP = re.compile(r"[^\w\s']", flags=re.UNICODE)  # keep letters/digits/space/apostrophe
_WS = re.compile(r"\s+")


def normalize_question(text: str | None) -> str:
    """Deterministic, conservative normalization for grouping.

    lowercase → fold apostrophes → drop punctuation/emoji (keep letters, digits,
    spaces, apostrophe) → collapse whitespace → trim. Does NOT stem or remove
    stopwords (Uzbek morphology preserved). Returns "" for empty/None input.
    """
    if not text:
        return ""
    s = text.lower()
    for ap in _APOSTROPHES:
        s = s.replace(ap, "'")
    s = s.replace("_", " ")
    s = _DROP.sub(" ", s)
    s = _WS.sub(" ", s).strip()
    return s


def _get(row: Any, key: str) -> Any:
    if isinstance(row, dict):
        return row.get(key)
    return getattr(row, key, None)


def group_top_questions(rows: Any, limit: int = _DEFAULT_LIMIT) -> list[dict]:
    """Pure grouping of question rows.

    ``rows`` is any iterable of objects/dicts exposing text / reason / severity /
    status / created_at. Rows whose text normalizes to "" are skipped. Returns up
    to ``limit`` groups sorted by count desc, then last_seen desc, then
    normalized asc (fully deterministic). The representative fields (sample,
    reason, severity, status) are taken from the MOST RECENT row in the group;
    ``last_seen`` is that row's created_at as ISO-8601.
    """
    groups: dict[str, dict] = {}
    for r in rows:
        text = _get(r, "text")
        norm = normalize_question(text)
        if not norm:
            continue
        created = _get(r, "created_at")
        g = groups.get(norm)
        if g is None:
            g = {
                "normalized": norm,
                "sample": (text or "").strip(),
                "count": 0,
                "last_seen": created,
                "reason": _get(r, "reason"),
                "severity": _get(r, "severity"),
                "status": _get(r, "status"),
            }
            groups[norm] = g
        g["count"] += 1
        # Representative = most recent row (also advances last_seen).
        if created is not None and (g["last_seen"] is None or created >= g["last_seen"]):
            g["last_seen"] = created
            g["sample"] = (text or "").strip()
            g["reason"] = _get(r, "reason")
            g["severity"] = _get(r, "severity")
            g["status"] = _get(r, "status")

    def _sort_key(g: dict) -> tuple:
        ls = g["last_seen"]
        ts = ls.timestamp() if isinstance(ls, datetime) else float("-inf")
        return (-g["count"], -ts, g["normalized"])

    ordered = sorted(groups.values(), key=_sort_key)
    out: list[dict] = []
    for g in ordered[:limit]:
        ls = g["last_seen"]
        out.append(
            {
                "normalized": g["normalized"],
                "sample": g["sample"],
                "count": g["count"],
                "last_seen": ls.isoformat() if isinstance(ls, datetime) else None,
                "reason": g["reason"],
                "severity": g["severity"],
                "status": g["status"],
            }
        )
    return out


async def collect_top_questions(
    session: AsyncSession,
    start: datetime,
    end: datetime,
    limit: int = _DEFAULT_LIMIT,
) -> list[dict]:
    """Load and group the most-asked unknown questions in [start, end).

    Read-only. ``start``/``end`` are plain datetimes (the caller resolves the
    daily-summary Period and timezone). Returns [] when there is no data — never
    a fabricated list.
    """
    rows = (
        await session.execute(
            sa.select(
                AgentUnknownQuestionModel.original_text_preview,
                AgentUnknownQuestionModel.reason,
                AgentUnknownQuestionModel.severity,
                AgentUnknownQuestionModel.status,
                AgentUnknownQuestionModel.created_at,
            )
            .where(
                AgentUnknownQuestionModel.created_at >= start,
                AgentUnknownQuestionModel.created_at < end,
            )
            .order_by(AgentUnknownQuestionModel.created_at.desc())
            .limit(_SCAN_CAP)
        )
    ).all()
    items = [
        {
            "text": r.original_text_preview,
            "reason": r.reason,
            "severity": r.severity,
            "status": r.status,
            "created_at": r.created_at,
        }
        for r in rows
    ]
    return group_top_questions(items, limit)
