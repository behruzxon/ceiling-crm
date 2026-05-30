"""
core.services.lead_risk_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Deterministic Lead Risk Explanation engine for the CRM contact-detail
sidebar.

Pure function over the contact record + recent messages + the F4
next-best-action result. **No** AI call, **no** DB write, **no**
Telegram link. Produces a frozen :class:`LeadRiskResult` with a
risk level, score, confidence, and 3-5 short Uzbek reason bullets
explaining why.
"""

from __future__ import annotations

import re
from typing import Any

from core.schemas.lead_risk_explanation import (
    LeadRiskReason,
    LeadRiskResult,
)
from shared.utils.phone import mask_phone_in_text

# ── Constants ──────────────────────────────────────────────────────────

_TERMINAL_STATUSES: frozenset[str] = frozenset(
    {"stopped", "lost", "won", "resolved", "closed", "deal", "completed"}
)

_GOOD_TERMINAL_STATUSES: frozenset[str] = frozenset({"won", "resolved", "deal", "completed"})

_STOP_KEYWORDS: tuple[str, ...] = (
    "kerak emas",
    "qiziqmayman",
    "stop",
    "to'xtang",
    "tuxtang",
    "rahmat, kerak emas",
)

_PRICE_KEYWORDS: tuple[str, ...] = (
    "narx",
    "narxi",
    "narxlar",
    "qancha",
    "necha pul",
    "price",
    "сколько",
    "arzon",
    "chegirma",
)

_OPERATOR_KEYWORDS: tuple[str, ...] = (
    "operator",
    "menejer",
    "manager",
    "konsultant",
    "консультант",
    "оператор",
)

_HOT_TEMPERATURES: frozenset[str] = frozenset({"hot"})
_WARM_OR_HOT: frozenset[str] = frozenset({"warm", "hot"})

_HOT_SCORE_THRESHOLD = 60
_WARM_SCORE_THRESHOLD = 30

# Secret patterns — defence-in-depth.
_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"sk-[A-Za-z0-9]{16,}"), "[redacted_openai_key]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._\-]{8,}"), "[redacted_bearer]"),
    (re.compile(r"\d{6,}:[A-Za-z0-9_\-]{20,}"), "[redacted_bot_token]"),
    (re.compile(r"postgres(?:ql)?://[^\s\"']+"), "[redacted_db_url]"),
    (re.compile(r"redis://[^\s\"']+"), "[redacted_redis_url]"),
    (re.compile(r"\bsystem\s*prompt\b", re.I), "[redacted_prompt]"),
    (re.compile(r"\binternal\s+(rules?|instructions?)\b", re.I), "[redacted_prompt]"),
)


# ── Public API ─────────────────────────────────────────────────────────


def explain_lead_risk(
    contact: dict[str, Any] | Any | None,
    messages: list[dict[str, Any]] | dict | None = None,
    *,
    next_best_action: Any | None = None,
) -> LeadRiskResult:
    """Return a frozen risk explanation for ``contact``.

    Deterministic and side-effect free. Output is safe to render
    directly in a Jinja2 template.
    """
    contact = contact or {}
    items = _normalise_messages(messages)
    last_inbound = _find_last_inbound(items)
    last_inbound_text = _sanitize_text(_extract_text(last_inbound))

    status = _coerce_str(_lookup(contact, "lead_status")).lower()

    # ── Terminal: closed / won — risk is moot ──────────────────────
    if status in _GOOD_TERMINAL_STATUSES:
        return LeadRiskResult(
            risk_level="low",
            score=10,
            confidence=80,
            summary="Bu lead yakunlangan holatda.",
            badge_tone="success",
            reasons=(
                LeadRiskReason(
                    reason_key="closed_status",
                    label="Yakunlangan",
                    detail=f"Kontakt holati: {status}.",
                    weight=-30,
                    tone="success",
                ),
            ),
        )
    if status in _TERMINAL_STATUSES:
        # Lost / stopped — high risk, but only one signal is reliable
        return LeadRiskResult(
            risk_level="high",
            score=85,
            confidence=70,
            summary="Bu lead yopilgan (stopped/lost) — yangi harakat tavsiya etilmaydi.",
            badge_tone="danger",
            reasons=(
                LeadRiskReason(
                    reason_key="closed_lost",
                    label="Yopiq (lost / stopped)",
                    detail=f"Kontakt holati: {status}.",
                    weight=60,
                    tone="danger",
                ),
            ),
        )

    # ── Signal extraction ──────────────────────────────────────────
    phone = _coerce_str(_lookup(contact, "phone"))
    score_input = _coerce_int(_lookup(contact, "lead_score"))
    temperature = _coerce_str(_lookup(contact, "temperature")).lower()
    metadata = _lookup(contact, "metadata") or {}
    area_m2 = _coerce_int(_lookup(metadata, "area_m2"))
    district = _coerce_str(_lookup(metadata, "district")) or _coerce_str(
        _lookup(contact, "district")
    )
    nba_key = _coerce_str(_lookup(next_best_action, "action_key"))
    nba_priority = _coerce_str(_lookup(next_best_action, "priority"))

    has_stop_signal = bool(last_inbound_text) and _contains_any(last_inbound_text, _STOP_KEYWORDS)
    has_price_intent = bool(last_inbound_text) and _contains_any(last_inbound_text, _PRICE_KEYWORDS)
    has_operator_request = bool(last_inbound_text) and _contains_any(
        last_inbound_text, _OPERATOR_KEYWORDS
    )
    is_hot = score_input >= _HOT_SCORE_THRESHOLD or temperature in _HOT_TEMPERATURES
    is_warm = score_input >= _WARM_SCORE_THRESHOLD or temperature in _WARM_OR_HOT

    reasons: list[LeadRiskReason] = []
    score = 30  # below the "medium" threshold so empty contacts stay low
    confidence = 10  # rises as we collect evidence

    # Stop signal — single biggest risk lift
    if has_stop_signal:
        reasons.append(
            LeadRiskReason(
                reason_key="stop_signal",
                label="STOP signali",
                detail="Mijoz qiziqmasligini bildirgan.",
                weight=40,
                tone="danger",
            )
        )
        score += 40
        confidence += 25

    # Phone absent → contactability risk
    if not phone:
        if is_hot:
            reasons.append(
                LeadRiskReason(
                    reason_key="hot_no_phone",
                    label="Telefon yo'q (qizg'in lead)",
                    detail="Bog'lanish uchun telefon yo'q, ammo lead qizg'in.",
                    weight=30,
                    tone="danger",
                )
            )
            score += 30
            confidence += 20
        elif is_warm:
            reasons.append(
                LeadRiskReason(
                    reason_key="warm_no_phone",
                    label="Telefon yo'q (iliq lead)",
                    detail="Bog'lanish uchun telefon yo'q.",
                    weight=15,
                    tone="warning",
                )
            )
            score += 15
            confidence += 10
        else:
            reasons.append(
                LeadRiskReason(
                    reason_key="no_phone",
                    label="Telefon yo'q",
                    detail="Bog'lanish uchun telefon raqami yo'q.",
                    weight=5,
                    tone="warning",
                )
            )
            score += 5
            confidence += 5
    else:
        reasons.append(
            LeadRiskReason(
                reason_key="has_phone",
                label="Telefon bor",
                detail="Bog'lanish ma'lumoti mavjud.",
                weight=-15,
                tone="success",
            )
        )
        score -= 15
        confidence += 15

    # Price intent + area on file vs missing
    if has_price_intent and not area_m2:
        reasons.append(
            LeadRiskReason(
                reason_key="price_without_area",
                label="Narx so'rovi, maydon yo'q",
                detail="Mijoz narx so'radi, lekin maydon (m²) aniqlanmagan.",
                weight=15,
                tone="warning",
            )
        )
        score += 15
        confidence += 10
    elif area_m2:
        reasons.append(
            LeadRiskReason(
                reason_key="has_area",
                label="Maydon ma'lum",
                detail=f"Maydon: {area_m2} m².",
                weight=-10,
                tone="success",
            )
        )
        score -= 10
        confidence += 10

    if district:
        reasons.append(
            LeadRiskReason(
                reason_key="has_district",
                label="Tuman ma'lum",
                detail=f"Tuman: {district}.",
                weight=-5,
                tone="info",
            )
        )
        score -= 5
        confidence += 5

    if has_operator_request:
        reasons.append(
            LeadRiskReason(
                reason_key="operator_requested",
                label="Operator so'rovi",
                detail="Mijoz operator/menejer yordamini so'radi.",
                weight=10,
                tone="warning",
            )
        )
        score += 10
        confidence += 10

    if last_inbound is None and not has_stop_signal:
        reasons.append(
            LeadRiskReason(
                reason_key="no_recent_inbound",
                label="Yangi xabar yo'q",
                detail="Loaded window ichida mijozdan yangi xabar yo'q.",
                weight=5,
                tone="warning",
            )
        )
        score += 5
        confidence += 5

    # NBA-aware adjustments — small nudges, never override raw signals
    if nba_key == "ask_phone" or nba_priority == "now":
        # Tip the scale into "high" sooner when next-best-action is urgent.
        score += 5
        confidence += 5
    elif nba_key == "schedule_measurement":
        score -= 10
        confidence += 5
        reasons.append(
            LeadRiskReason(
                reason_key="ready_for_measurement",
                label="O'lchovga tayyor",
                detail="Bog'lanish ma'lumoti bor va lead iliq — o'lchov bosqichida.",
                weight=-15,
                tone="success",
            )
        )

    # Clamp and pick level
    score = max(0, min(100, score))
    confidence = max(0, min(100, confidence))

    if confidence < 20 and len(reasons) <= 1:
        return LeadRiskResult(
            risk_level="unknown",
            score=score,
            confidence=confidence,
            summary="Yetarli signal yo'q — kontakt yangi yoki ma'lumotlar to'liq emas.",
            badge_tone="neutral",
            empty_reason="Riskni tushuntirish uchun yetarli signal yo'q.",
            reasons=tuple(reasons),
        )

    if score >= 70:
        risk_level = "high"
        badge_tone = "danger"
        summary = "Yuqori risk — bir nechta xavotirli signal bor."
    elif score >= 35:
        risk_level = "medium"
        badge_tone = "warning"
        summary = "O'rta risk — operator e'tibori kerak."
    else:
        risk_level = "low"
        badge_tone = "success"
        summary = "Past risk — lead davom etishi mumkin."

    # Sort by absolute weight so the strongest signals come first;
    # cap to 5 so the panel stays compact.
    reasons.sort(key=lambda r: abs(r.weight), reverse=True)
    reasons = reasons[:5]

    return LeadRiskResult(
        risk_level=risk_level,
        score=score,
        confidence=confidence,
        summary=summary,
        badge_tone=badge_tone,
        reasons=tuple(reasons),
    )


# ── Helpers ────────────────────────────────────────────────────────────


def _lookup(obj: Any, key: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _coerce_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _coerce_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return 0


def _normalise_messages(messages: list | dict | None) -> list[Any]:
    if messages is None:
        return []
    if isinstance(messages, dict):
        items = messages.get("items")
        if isinstance(items, list):
            return items
        return []
    if isinstance(messages, list):
        return messages
    return []


def _find_last_inbound(items: list[Any]) -> Any | None:
    for item in reversed(items):
        direction = _coerce_str(_lookup(item, "direction")).lower()
        sender = _coerce_str(_lookup(item, "sender_type")).lower()
        if direction == "inbound" or sender in {"user", "customer", "client"}:
            return item
    return None


def _extract_text(msg: Any) -> str:
    if msg is None:
        return ""
    return _coerce_str(_lookup(msg, "text"))


def _sanitize_text(text: str) -> str:
    if not text:
        return ""
    cleaned = mask_phone_in_text(text)
    for pattern, replacement in _SECRET_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned.lower()


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(needle in lower for needle in needles)
