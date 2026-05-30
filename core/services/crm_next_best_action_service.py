"""
core.services.crm_next_best_action_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Deterministic "what should the operator do next?" engine for the
CRM contact-detail web panel.

This is a **sibling** of the existing ``next_best_action_service`` —
that module is the AI Sales Autopilot used by the bot layer. The
function here only feeds the CRM web sidebar card, has a different
output shape, and is intentionally kept simple and pure.

Pure function over the contact record + recent messages + (optionally)
the F2 / F3 panel results that are already on the page. **No** AI
call, **no** DB write, **no** Telegram link. The result is rendered
in the contact-detail sidebar as a small advisory card.

Rule order (top wins):

1.  Terminal contact status (``stopped`` / ``lost`` / ``won`` /
    ``resolved`` / ``closed``) → ``no_action``.
2.  Stop signal in the latest inbound message → ``polite_close``.
3.  Hot lead with no phone → ``ask_phone``.
4.  Price intent with no area on file → ``ask_area``.
5.  Price intent with area on file → ``calculate_price``.
6.  Phone present and lead is warm or hot → ``schedule_measurement``.
7.  Operator requested in the last inbound → ``operator_followup``.
8.  No recent inbound message → ``wait``.
9.  Default → ``clarify_need``.
"""

from __future__ import annotations

import re
from typing import Any

from core.schemas.next_best_action import NextBestActionResult
from shared.utils.phone import mask_phone_in_text

# ── Constants ──────────────────────────────────────────────────────────

_TERMINAL_STATUSES: frozenset[str] = frozenset(
    {"stopped", "lost", "won", "resolved", "closed", "deal", "completed"}
)

_OPERATOR_REQUEST_STATUSES: frozenset[str] = frozenset({"operator_needed"})

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
_WARM_SCORE_THRESHOLD = 50

# Secret patterns — defence-in-depth against any caller passing through
# log output instead of a real message body.
_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"sk-[A-Za-z0-9]{16,}"), "[redacted_openai_key]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._\-]{8,}"), "[redacted_bearer]"),
    (re.compile(r"\d{6,}:[A-Za-z0-9_\-]{20,}"), "[redacted_bot_token]"),
    (re.compile(r"postgres(?:ql)?://[^\s\"']+"), "[redacted_db_url]"),
    (re.compile(r"redis://[^\s\"']+"), "[redacted_redis_url]"),
    (re.compile(r"\bsystem\s*prompt\b", re.I), "[redacted_prompt]"),
    (re.compile(r"\binternal\s+(rules?|instructions?)\b", re.I), "[redacted_prompt]"),
)

# Allowed CTA anchors — internal CRM only, no external links, no
# Telegram, no API endpoints.
_ALLOWED_CTA_ANCHORS: frozenset[str] = frozenset(
    {
        "#operatorReplySection",
        "#operatorReplySuggestionsPanel",
        "#manualPriceCalculatorPanel",
        "#conversationReplay",
        "#chatTimeline",
        "#nextBestActionPanel",
        "",
    }
)


# ── Public API ─────────────────────────────────────────────────────────


def compute_next_best_action(
    contact: dict[str, Any] | Any | None,
    messages: list[dict[str, Any]] | dict | None = None,
    *,
    calculator_result: Any | None = None,  # noqa: ARG001
    suggestion_result: Any | None = None,  # noqa: ARG001
) -> NextBestActionResult:
    """Return the single best deterministic next-action for ``contact``."""
    contact = contact or {}
    items = _normalise_messages(messages)
    last_inbound = _find_last_inbound(items)
    last_inbound_text = _sanitize_text(_extract_text(last_inbound))

    status = _coerce_str(_lookup(contact, "lead_status")).lower()

    if status in _TERMINAL_STATUSES:
        return NextBestActionResult(
            action_key="no_action",
            label="Hozircha harakat kerak emas",
            reason=f"Kontakt holati: {status}.",
            priority="none",
            confidence=95,
            badge_tone="neutral",
        )

    if last_inbound_text and _contains_any(last_inbound_text, _STOP_KEYWORDS):
        return NextBestActionResult(
            action_key="polite_close",
            label="Muloyim yakunlash",
            reason="Mijoz qiziqishi kam ekanligini bildirdi — hurmat bilan yopish.",
            priority="later",
            confidence=80,
            badge_tone="neutral",
        )

    phone = _coerce_str(_lookup(contact, "phone"))
    score = _coerce_int(_lookup(contact, "lead_score"))
    temperature = _coerce_str(_lookup(contact, "temperature")).lower()
    metadata = _lookup(contact, "metadata") or {}
    area_m2 = _coerce_int(_lookup(metadata, "area_m2"))
    is_hot = score >= _HOT_SCORE_THRESHOLD or temperature in _HOT_TEMPERATURES

    if is_hot and not phone:
        return NextBestActionResult(
            action_key="ask_phone",
            label="Telefon raqamini so'rash",
            reason="Lead qizg'in (score yoki temperature yuqori), ammo telefon yo'q.",
            priority="now",
            confidence=85,
            cta_label="Reply panel",
            cta_url="#operatorReplySection",
            badge_tone="danger",
        )

    has_price_intent = bool(last_inbound_text) and _contains_any(last_inbound_text, _PRICE_KEYWORDS)

    if has_price_intent and not area_m2:
        return NextBestActionResult(
            action_key="ask_area",
            label="Maydonni aniqlash (m²)",
            reason="Mijoz narx so'radi, lekin maydon hali ma'lum emas.",
            priority="now",
            confidence=80,
            cta_label="Reply panel",
            cta_url="#operatorReplySection",
            badge_tone="warning",
        )

    if has_price_intent and area_m2:
        return NextBestActionResult(
            action_key="calculate_price",
            label="Taxminiy narx hisoblash",
            reason="Mijoz narx so'radi va maydon ham bor — kalkulyatorda taxminiy ko'rsating.",
            priority="today",
            confidence=80,
            cta_label="Calculator",
            cta_url="#manualPriceCalculatorPanel",
            badge_tone="info",
        )

    if phone and (score >= _WARM_SCORE_THRESHOLD or temperature in _WARM_OR_HOT):
        return NextBestActionResult(
            action_key="schedule_measurement",
            label="O'lchovga kelishish",
            reason="Mijoz iliq/qizg'in va telefon bor — o'lchov vaqtini muloyim taklif qiling.",
            priority="today",
            confidence=75,
            cta_label="Reply panel",
            cta_url="#operatorReplySection",
            badge_tone="success",
        )

    operator_request = status in _OPERATOR_REQUEST_STATUSES or (
        bool(last_inbound_text) and _contains_any(last_inbound_text, _OPERATOR_KEYWORDS)
    )
    if operator_request:
        return NextBestActionResult(
            action_key="operator_followup",
            label="Operator javobini tayyorlash",
            reason="Mijoz operator yordamini so'radi — aniq javob tayyorlang.",
            priority="now",
            confidence=70,
            cta_label="Suggestions",
            cta_url="#operatorReplySuggestionsPanel",
            badge_tone="warning",
        )

    if last_inbound is None:
        return NextBestActionResult(
            action_key="wait",
            label="Kuzatishda qoldirish",
            reason="Hozircha yangi inbound xabar yo'q — kuzatishda qoldiring.",
            priority="later",
            confidence=55,
            badge_tone="neutral",
            empty_reason="Yangi xabar kelganida bu panel yangilanadi.",
        )

    return NextBestActionResult(
        action_key="clarify_need",
        label="Ehtiyojni aniqlash",
        reason="Yetarli kontekst yo'q — qisqa aniqlovchi savol bilan boshlang.",
        priority="soon",
        confidence=55,
        cta_label="Suggestions",
        cta_url="#operatorReplySuggestionsPanel",
        badge_tone="info",
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


def is_safe_cta_url(url: str) -> bool:
    """Public helper for tests: True only for internal CRM anchors."""
    return url in _ALLOWED_CTA_ANCHORS
