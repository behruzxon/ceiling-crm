"""Missed leads detection — pure functions, no DB I/O."""

from __future__ import annotations

import re

from core.schemas.crm_missed_leads import (
    MissedLeadItem,
    MissedLeadRecommendation,
    MissedLeadSummary,
)

_TOKEN_RE = re.compile(r"(sk-[a-zA-Z0-9]{8,}|Bearer\s+\S{10,})", re.I)

EXCLUDED_STATUSES = frozenset({"stopped", "lost", "won", "merged"})

SEVERITY_RULES = {
    "hot_unanswered": {"threshold_min": 10, "severity": "critical"},
    "operator_waiting": {"threshold_min": 5, "severity": "critical"},
    "phone_shared_no_followup": {"threshold_min": 10, "severity": "critical"},
    "sla_critical": {"threshold_min": 0, "severity": "critical"},
    "price_interest_no_action": {"threshold_min": 15, "severity": "high"},
    "handoff_waiting_phone": {"threshold_min": 30, "severity": "high"},
    "stale_warm_lead": {"threshold_min": 1440, "severity": "high"},
    "sla_overdue": {"threshold_min": 0, "severity": "high"},
    "catalog_no_next_step": {"threshold_min": 0, "severity": "medium"},
}


def classify_severity(reason: str, minutes_waiting: int = 0) -> str:
    rule = SEVERITY_RULES.get(reason)
    if not rule:
        return "low"
    if minutes_waiting >= rule["threshold_min"]:
        return rule["severity"]
    return "medium"


def mask_phone(phone: str | None) -> str | None:
    if not phone or len(phone) < 6:
        return phone
    return phone[:4] + "****" + phone[-2:]


def sanitize_preview(text: str | None, max_len: int = 120) -> str | None:
    if not text:
        return None
    cleaned = _TOKEN_RE.sub("[REDACTED]", text)
    return cleaned[:max_len]


def build_next_action(reason: str) -> str:
    actions = {
        "hot_unanswered": "Darhol javob bering",
        "operator_waiting": "Operatorga belgilang",
        "phone_shared_no_followup": "Telefon bo'yicha bog'laning",
        "price_interest_no_action": "Taxminiy narx yuboring",
        "sla_critical": "Zudlik bilan ko'rib chiqing",
        "sla_overdue": "Muddati o'tganlarni tekshiring",
        "handoff_waiting_phone": "Telefon so'rang",
        "stale_warm_lead": "Qayta aloqa qiling",
        "catalog_no_next_step": "Narx yoki o'lchov taklif qiling",
    }
    return actions.get(reason, "Ko'rib chiqing")


def build_summary(items: list[MissedLeadItem]) -> MissedLeadSummary:
    total = len(items)
    critical = sum(1 for i in items if i.severity == "critical")
    high = sum(1 for i in items if i.severity == "high")
    medium = sum(1 for i in items if i.severity == "medium")
    low = sum(1 for i in items if i.severity == "low")
    hot = sum(1 for i in items if i.reason == "hot_unanswered")
    op_wait = sum(1 for i in items if i.reason == "operator_waiting")
    phone = sum(1 for i in items if i.reason == "phone_shared_no_followup")
    waits = [i.minutes_waiting for i in items if i.minutes_waiting > 0]
    avg_wait = int(sum(waits) / len(waits)) if waits else 0
    oldest = max(waits) if waits else 0
    return MissedLeadSummary(
        total=total,
        critical=critical,
        high=high,
        medium=medium,
        low=low,
        hot_unanswered=hot,
        operator_waiting=op_wait,
        phone_shared_no_followup=phone,
        avg_wait_minutes=avg_wait,
        oldest_wait_minutes=oldest,
    )


def build_recommendations(
    summary: MissedLeadSummary,
) -> list[MissedLeadRecommendation]:
    recs = []
    if summary.critical > 0:
        recs.append(
            MissedLeadRecommendation(
                text="Avval critical hot leadlarga javob bering",
                priority="critical",
                count=summary.critical,
            )
        )
    if summary.operator_waiting > 0:
        recs.append(
            MissedLeadRecommendation(
                text="Telefon qoldirganlarni operatorga belgilang",
                priority="high",
                count=summary.operator_waiting,
            )
        )
    if summary.phone_shared_no_followup > 0:
        recs.append(
            MissedLeadRecommendation(
                text="Telefon ulashganlarni kuzatib boring",
                priority="high",
                count=summary.phone_shared_no_followup,
            )
        )
    if summary.high > 0:
        recs.append(
            MissedLeadRecommendation(
                text="Narx so'raganlarga taxminiy hisob yuboring",
                priority="medium",
                count=summary.high,
            )
        )
    return recs
