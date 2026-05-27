"""Operator handoff queue service — safe, no-ETA, dedup-aware."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HandoffResult:
    handoff_id: int | None = None
    status: str = "open"
    priority: str = "normal"
    is_duplicate: bool = False
    user_message: str = ""


VALID_STATUSES = frozenset({
    "open", "waiting_phone", "assigned",
    "contacted", "resolved", "cancelled", "expired",
})
VALID_PRIORITIES = frozenset({"low", "normal", "high", "urgent"})
VALID_SOURCES = frozenset({
    "ai_button", "text_intent", "operator_button", "crm_manual",
})

_TOKEN_PATTERN = re.compile(r"(sk-[a-zA-Z0-9]{8,}|Bearer\s+\S{10,})", re.I)
_PHONE_PATTERN = re.compile(r"\+?\d{10,}")

DEFAULT_DEDUP_MINUTES = 30
DEFAULT_EXPIRE_HOURS = 24
DEFAULT_URGENT_SCORE_THRESHOLD = 80


def mask_phone(phone: str | None) -> str | None:
    if not phone or len(phone) < 6:
        return phone
    return phone[:4] + "****" + phone[-2:]


def sanitize_message_preview(text: str | None, max_len: int = 200) -> str | None:
    if not text:
        return None
    cleaned = _TOKEN_PATTERN.sub("[REDACTED]", text)
    return cleaned[:max_len]


def sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    if not metadata:
        return None
    result = {}
    for key, val in metadata.items():
        if isinstance(val, str):
            val = _TOKEN_PATTERN.sub("[REDACTED]", val)
        result[key] = val
    return result


def calculate_priority(
    *,
    lead_score: int = 0,
    reason: str | None = None,
    has_phone: bool = False,
    is_repeated: bool = False,
    urgent_threshold: int = DEFAULT_URGENT_SCORE_THRESHOLD,
) -> str:
    if lead_score >= urgent_threshold:
        return "urgent"
    if reason in ("complaint", "angry_objection"):
        return "urgent"
    if is_repeated and lead_score >= 60:
        return "urgent"
    if has_phone and reason in ("price_question", "measurement_request"):
        return "high"
    if reason == "measurement_request":
        return "high"
    if has_phone and lead_score >= 40:
        return "high"
    return "normal"


def build_user_message(*, has_phone: bool, is_duplicate: bool = False) -> str:
    if is_duplicate:
        return (
            "👨‍💼 So'rovingiz operatorga yuborilgan. "
            "Qo'shimcha savolingiz bo'lsa shu yerga yozing."
        )
    if has_phone:
        return (
            "👨‍💼 Operatorga ulash uchun so'rovingiz qabul qilindi. "
            "Operator xabaringizni ko'rib chiqadi."
        )
    return (
        "👨‍💼 Operatorga ulash uchun so'rovingiz qabul qilindi. "
        "Sizga bog'lanishimiz uchun telefon raqamingizni yuboring."
    )


@dataclass
class QueueSummary:
    total_open: int = 0
    total_waiting_phone: int = 0
    total_assigned: int = 0
    total_urgent: int = 0
    total_high: int = 0
