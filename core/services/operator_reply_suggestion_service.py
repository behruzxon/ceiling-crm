"""
core.services.operator_reply_suggestion_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Pure suggestion engine for the Operator AI Reply Suggestion panel.

This service produces 2–3 short Uzbek reply suggestions for an operator,
based on the last inbound customer message. It is **suggest-only**:

  * Never sends a Telegram message.
  * Never calls OpenAI directly — the default responder is a fully
    deterministic stub. A caller may inject a custom ``ai_responder``
    callable (e.g. in production once the feature is enabled) and tests
    can mock it.
  * Sanitises phones, bot tokens, OpenAI keys, ``Bearer`` headers,
    database URLs, and prompt-injection markers out of both the source
    preview and every suggestion text.
  * Refuses to emit "darhol", "hozir" or "bugun" — those are operator
    promises that only a human should make.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from typing import Any

from core.schemas.operator_reply_suggestion import (
    OperatorReplySuggestion,
    OperatorReplySuggestionResult,
)
from shared.utils.phone import mask_phone_in_text

# ── Constants ──────────────────────────────────────────────────────────

_MAX_PREVIEW_CHARS = 140
_MAX_SUGGESTION_CHARS = 280

_PRICE_KEYWORDS: tuple[str, ...] = (
    "narx",
    "narxi",
    "narxlar",
    "qancha",
    "necha pul",
    "сколько",
    "price",
    "arzon",
    "chegirma",
)

_GREETING_KEYWORDS: tuple[str, ...] = (
    "salom",
    "assalom",
    "здравствуйте",
    "привет",
    "hello",
    "hi",
)

_STOP_KEYWORDS: tuple[str, ...] = (
    "kerak emas",
    "rahmat",
    "yo'q",
    "yoq",
    "stop",
)

_FORBIDDEN_PROMISE_WORDS: tuple[str, ...] = (
    "darhol",
    "hozir",
    "hozirjavob",
    "bugun",
)

# Aggressive secret patterns: stripped from BOTH source preview and any
# suggestion text the responder returns. Defence-in-depth — the
# deterministic stub never produces these, but a future custom responder
# could leak something.
_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"sk-[A-Za-z0-9]{16,}"), "[redacted_openai_key]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._\-]{8,}"), "[redacted_bearer]"),
    (re.compile(r"\d{6,}:[A-Za-z0-9_\-]{20,}"), "[redacted_bot_token]"),
    (re.compile(r"postgres(?:ql)?://[^\s\"']+"), "[redacted_db_url]"),
    (re.compile(r"redis://[^\s\"']+"), "[redacted_redis_url]"),
    (re.compile(r"\bapi[_-]?key\s*[:=]\s*[A-Za-z0-9._\-]+", re.I), "[redacted_api_key]"),
    (re.compile(r"\bsystem\s*prompt\b", re.I), "[redacted_prompt]"),
    (re.compile(r"\binternal\s+(rules?|instructions?)\b", re.I), "[redacted_prompt]"),
)


# ── Public API ─────────────────────────────────────────────────────────


def build_operator_reply_suggestions(
    contact: dict[str, Any] | Any | None,
    messages: list[dict[str, Any]] | None,
    *,
    ai_responder: Callable[..., list[dict[str, str]]] | None = None,
    feature_enabled: bool = False,
) -> OperatorReplySuggestionResult:
    """Return a frozen result describing 2–3 reply suggestions.

    Parameters
    ----------
    contact:
        Dict-like contact record (or ``None``). Only ``id`` /
        ``telegram_user_id`` are read.
    messages:
        Iterable of message dicts. Each dict may carry ``direction``,
        ``sender_type``, ``text``, ``created_at``. Bot/operator messages
        are ignored — the panel suggests replies to the **customer**.
    ai_responder:
        Optional callable used to override the deterministic stub.
        Receives ``(intent: str, source_text: str)`` and must return a
        list of dicts with ``{tone, text, reason, risk_level}`` keys.
        Tests pass a mock here — the production wiring is intentionally
        left for a follow-up feature so this PR cannot accidentally
        introduce a live OpenAI call.
    feature_enabled:
        Master gate. Default ``False``. If ``False`` the result reports
        the feature is off and returns no suggestions — the template
        renders a friendly placeholder.
    """
    contact_id = _extract_contact_id(contact)

    if not feature_enabled:
        return OperatorReplySuggestionResult(
            feature_enabled=False,
            contact_id=contact_id,
            empty_reason=("AI reply suggestions hozir o'chiq. " "Operator javobni qo'lda yozadi."),
        )

    last_inbound = _find_last_inbound(messages or [])
    if last_inbound is None:
        return OperatorReplySuggestionResult(
            feature_enabled=True,
            contact_id=contact_id,
            empty_reason="Mijozdan kelgan xabar yo'q — taklif yaratish uchun yetarli kontekst yo'q.",
        )

    raw_text = str(last_inbound.get("text") or "").strip()
    if not raw_text:
        return OperatorReplySuggestionResult(
            feature_enabled=True,
            contact_id=contact_id,
            empty_reason="Oxirgi xabarda matn yo'q (media / sticker).",
        )

    intent = _detect_intent(raw_text)
    safe_preview = _sanitize_text(raw_text, max_chars=_MAX_PREVIEW_CHARS)

    raw_suggestions = (
        _deterministic_stub(intent, safe_preview)
        if ai_responder is None
        else _safe_call_responder(ai_responder, intent, safe_preview)
    )

    suggestions = tuple(_build_safe_suggestion(s) for s in raw_suggestions[:3] if s)

    if len(suggestions) < 2:
        # Fall back to deterministic to guarantee 2–3 suggestions.
        suggestions = tuple(
            _build_safe_suggestion(s) for s in _deterministic_stub(intent, safe_preview)
        )

    return OperatorReplySuggestionResult(
        feature_enabled=True,
        contact_id=contact_id,
        source_message_preview=safe_preview,
        suggestions=suggestions,
    )


# ── Helpers ────────────────────────────────────────────────────────────


def _extract_contact_id(contact: Any | None) -> int | str:
    if contact is None:
        return ""
    if isinstance(contact, dict):
        return contact.get("id") or contact.get("telegram_user_id") or ""
    return getattr(contact, "id", "") or getattr(contact, "telegram_user_id", "") or ""


def _find_last_inbound(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    for msg in reversed(messages):
        if not isinstance(msg, dict):
            continue
        direction = str(msg.get("direction") or "").lower()
        sender = str(msg.get("sender_type") or "").lower()
        if direction == "inbound" or sender in ("user", "customer", "client"):
            return msg
    return None


def _detect_intent(text: str) -> str:
    lower = text.lower()
    if any(kw in lower for kw in _PRICE_KEYWORDS):
        return "price"
    if any(kw in lower for kw in _STOP_KEYWORDS):
        return "stop"
    if any(kw in lower for kw in _GREETING_KEYWORDS):
        return "greeting"
    if "?" in text or "qanday" in lower or "qachon" in lower:
        return "clarification"
    return "generic"


def _sanitize_text(text: str, *, max_chars: int) -> str:
    if not text:
        return ""
    cleaned = mask_phone_in_text(text)
    for pattern, replacement in _SECRET_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    cleaned = cleaned.replace("\r", " ").replace("\n", " ").strip()
    if len(cleaned) > max_chars:
        cleaned = cleaned[: max_chars - 1].rstrip() + "…"
    return cleaned


def _strip_forbidden_promises(text: str) -> str:
    for word in _FORBIDDEN_PROMISE_WORDS:
        text = re.sub(rf"\b{re.escape(word)}\b", "tez orada", text, flags=re.I)
    return text


def _build_safe_suggestion(raw: dict[str, str]) -> OperatorReplySuggestion:
    text = _sanitize_text(str(raw.get("text") or ""), max_chars=_MAX_SUGGESTION_CHARS)
    text = _strip_forbidden_promises(text)
    return OperatorReplySuggestion(
        suggestion_id=str(raw.get("suggestion_id") or uuid.uuid4().hex[:12]),
        tone=str(raw.get("tone") or "professional"),
        text=text,
        reason=_sanitize_text(str(raw.get("reason") or ""), max_chars=140),
        risk_level=str(raw.get("risk_level") or "low"),
        copy_label="Copy",
    )


def _safe_call_responder(
    responder: Callable[..., list[dict[str, str]]],
    intent: str,
    source_text: str,
) -> list[dict[str, str]]:
    try:
        result = responder(intent=intent, source_text=source_text)
    except Exception:
        return []
    if not isinstance(result, list):
        return []
    cleaned: list[dict[str, str]] = []
    for item in result:
        if isinstance(item, dict) and item.get("text"):
            cleaned.append(item)
    return cleaned


# ── Deterministic stub ─────────────────────────────────────────────────


def _deterministic_stub(intent: str, source_text: str) -> list[dict[str, str]]:
    """Return 3 canned Uzbek replies. Pure — no I/O, no randomness."""
    if intent == "price":
        return [
            {
                "tone": "professional",
                "text": (
                    "Salom! Narxni aniqlash uchun maydon (m²), dizayn turi va "
                    "qo'shimchalarni bilishimiz kerak. Bu ma'lumotlarni "
                    "ulashsangiz, taxminiy hisob beramiz."
                ),
                "reason": "Narx so'roviga aniqlovchi savollar bilan javob.",
                "risk_level": "low",
            },
            {
                "tone": "clarification",
                "text": (
                    "Maydon va dizayn turini bilishim mumkinmi? Hisob taxminiy "
                    "bo'ladi — yakuniy narx o'lchovdan keyin tasdiqlanadi."
                ),
                "reason": "Taxminiy ekanini ta'kidlaydi, fake ETA bermaydi.",
                "risk_level": "low",
            },
            {
                "tone": "closing",
                "text": (
                    "Agar qulay bo'lsa, bepul o'lchov uchun manzilingizni "
                    "yuboring — usta tashrif buyurib aniq narxni aytadi."
                ),
                "reason": "Keyingi qadam: bepul o'lchov taklifi.",
                "risk_level": "low",
            },
        ]
    if intent == "stop":
        return [
            {
                "tone": "professional",
                "text": (
                    "Tushundim, rahmat. Agar fikringiz o'zgarsa, biz har doim "
                    "yordam berishga tayyormiz."
                ),
                "reason": "Mijoz STOP signali — hurmat bilan yopish.",
                "risk_level": "low",
            },
            {
                "tone": "friendly",
                "text": (
                    "Rahmat! Sizga halaqit bermaymiz. Keyinroq kerak bo'lsa — " "shu yerda topasiz."
                ),
                "reason": "Stop signalga muloyim javob.",
                "risk_level": "low",
            },
        ]
    if intent == "greeting":
        return [
            {
                "tone": "friendly",
                "text": "Salom! CeilingCRM jamoasiga xush kelibsiz. Sizga qanday yordam bera olamiz?",
                "reason": "Salomlashish — ochiq savol bilan davom.",
                "risk_level": "low",
            },
            {
                "tone": "professional",
                "text": (
                    "Assalomu alaykum! Bizdan stretch potolok bo'yicha narx, "
                    "katalog yoki o'lchov xizmati kerakmi?"
                ),
                "reason": "Salomga rasmiy javob va xizmatlar ro'yxati.",
                "risk_level": "low",
            },
            {
                "tone": "clarification",
                "text": "Salom! Qaysi xona uchun va qanday dizayn ko'rib chiqyapsiz?",
                "reason": "Salom + kontekst yig'ish.",
                "risk_level": "low",
            },
        ]
    if intent == "clarification":
        return [
            {
                "tone": "clarification",
                "text": (
                    "Savolingiz uchun rahmat. Aniqroq javob berish uchun bir "
                    "necha tafsilot kerak — qaysi xonadan boshlasak?"
                ),
                "reason": "Savolga aniqlovchi qarshi savol.",
                "risk_level": "low",
            },
            {
                "tone": "professional",
                "text": (
                    "Yaxshi savol. Javobni to'liq berishim uchun maydon va "
                    "dizayn turini bilishim foydali bo'ladi."
                ),
                "reason": "Aniqlovchi savol + javob konteksti.",
                "risk_level": "low",
            },
            {
                "tone": "closing",
                "text": (
                    "Agar ko'rib chiqish qulayroq bo'lsa, katalogimizdan namuna "
                    "yuborishim mumkin. Qaysi xona uchun?"
                ),
                "reason": "Katalog taklifi bilan javob.",
                "risk_level": "low",
            },
        ]
    return [
        {
            "tone": "friendly",
            "text": "Salom! Xabaringiz uchun rahmat. Sizga qanday yordam bera olamiz?",
            "reason": "Umumiy javob — kontekst yig'ish.",
            "risk_level": "low",
        },
        {
            "tone": "clarification",
            "text": "Iltimos, ozgina batafsilroq yozsangiz — qaysi xizmatga qiziqyapsiz?",
            "reason": "Aniqlovchi savol.",
            "risk_level": "low",
        },
        {
            "tone": "closing",
            "text": "Agar tayyor bo'lsangiz, bepul o'lchov uchun manzilingizni yuborishingiz mumkin.",
            "reason": "Keyingi qadam taklifi.",
            "risk_level": "low",
        },
    ]
