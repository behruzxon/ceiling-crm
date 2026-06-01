"""
core.services.unknown_question_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Capture service for the **Unknown Questions Inbox** — the first safe feedback
loop for improving the agent after deployment.

It records customer messages where the bot likely failed, was uncertain, hit a
fallback / OpenAI error, was safety-blocked, or otherwise needs admin review.

Design principles
-----------------
* **Pure-first.** Sanitization, hashing, reason classification, severity, and
  event building are pure functions with no framework dependencies — trivially
  testable and reusable from any layer.
* **Privacy by construction.** Only a sanitized preview (phones masked,
  tokens / URLs / keys redacted, truncated to 300 chars) and a SHA-256 hash of
  the normalized text are ever produced. Raw messages, phone numbers, and
  secrets are never stored.
* **Never break the bot.** ``capture_unknown_question`` wraps all DB work in a
  broad ``try / except`` and logs a warning on failure — it returns ``False``
  rather than raising, so a capture problem can never affect a customer reply.
* **Read-only inbox.** This module captures and classifies. It does NOT send
  messages, mutate knowledge, or change bot behaviour.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from shared.utils.phone import mask_phone_in_text

try:  # structured logger is optional at import time (keeps the module pure-safe)
    from shared.logging import get_logger

    _log = get_logger(__name__)
except Exception:  # pragma: no cover - logging is best-effort only
    import logging

    _log = logging.getLogger(__name__)


# ── Vocabularies ─────────────────────────────────────────────────────────────

#: Allowed capture sources.
SOURCES: frozenset[str] = frozenset({"telegram", "web", "simulation", "manual"})

#: Allowed capture reasons (why the bot likely failed / needs review).
REASONS: frozenset[str] = frozenset(
    {
        "ai_fallback",
        "low_confidence",
        "openai_error",
        "safety_block",
        "generic_reply",
        "no_catalog_match",
        "unknown_design",
        "unknown_price_question",
        "shadow_live_mismatch",
        "operator_needed",
        "manual_flag",
    }
)

#: Allowed severities (ascending).
SEVERITIES: tuple[str, ...] = ("low", "medium", "high", "critical")

#: Allowed review statuses.
STATUSES: frozenset[str] = frozenset(
    {"new", "reviewed", "ignored", "converted_to_faq", "needs_operator"}
)

#: Default severity per reason. Tuned so genuinely lost customers / safety
#: events rank above informational fallbacks.
_REASON_SEVERITY: dict[str, str] = {
    "openai_error": "high",
    "safety_block": "high",
    "shadow_live_mismatch": "high",
    "operator_needed": "high",
    "unknown_price_question": "medium",
    "no_catalog_match": "medium",
    "unknown_design": "medium",
    "low_confidence": "medium",
    "ai_fallback": "medium",
    "generic_reply": "low",
    "manual_flag": "medium",
}

#: Maximum stored preview length (chars). Matches sanitize_user_text_for_prompt.
MAX_PREVIEW_LEN = 300


# ── Redaction patterns ───────────────────────────────────────────────────────

# OpenAI-style keys.
_RE_SK_KEY = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")
# Telegram bot tokens: <digits>:<35+ token chars>.
_RE_BOT_TOKEN = re.compile(r"\b\d{6,12}:[A-Za-z0-9_\-]{20,}\b")
# Bearer tokens.
_RE_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-=]{8,}")
# key=value / key: value secrets (api key, token, secret, password, database_url).
_RE_SECRET_KV = re.compile(
    r"(?i)\b(api[_-]?key|token|secret|password|passwd|database_url|db_url)\b" r"\s*[:=]\s*\S+"
)
# Any URL (we don't want links — incl. t.me invite links — sitting in the inbox).
_RE_URL = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
# Collapse whitespace runs.
_RE_WS = re.compile(r"\s+")

_REDACTION = "[redacted]"
_LINK = "[link]"


def sanitize_unknown_question_text(text: str | None, *, max_length: int = MAX_PREVIEW_LEN) -> str:
    """Return a privacy-safe, length-bounded preview of *text*.

    Order matters: redact secrets (key/value, bot tokens, bearer, sk- keys) and
    URLs **first** — before masking phones — so the phone mask's digit-run
    pattern cannot nibble the leading digits of a bot token and leave its body
    behind. Then mask phones, collapse whitespace, and truncate. Safe with
    ``None`` / empty input.
    """
    if not text:
        return ""
    out = _RE_SECRET_KV.sub(_REDACTION, str(text))
    out = _RE_BOT_TOKEN.sub(_REDACTION, out)
    out = _RE_BEARER.sub(_REDACTION, out)
    out = _RE_SK_KEY.sub(_REDACTION, out)
    out = _RE_URL.sub(_LINK, out)
    out = mask_phone_in_text(out)
    out = _RE_WS.sub(" ", out).strip()
    return out[:max_length]


def hash_question_text(text: str | None) -> str:
    """Stable SHA-256 hex digest of normalized text, for dedupe.

    Normalization: lower-cased, whitespace-collapsed, stripped. Empty input
    hashes the empty string (still stable). The hash is computed on the
    *original* text shape (after whitespace / case normalization) so that two
    phrasings differing only in spacing/case dedupe together.
    """
    norm = _RE_WS.sub(" ", (text or "").lower()).strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def hash_chat_id(chat_id: int | str | None) -> str | None:
    """Return a SHA-256 hex digest of the chat id, or ``None``.

    We never store the raw chat id — only a stable hash, so an admin cannot
    derive the Telegram chat from the inbox while dedupe/grouping still works.
    """
    if chat_id is None or chat_id == "":
        return None
    return hashlib.sha256(str(chat_id).encode("utf-8")).hexdigest()


def classify_unknown_question_reason(
    *,
    openai_error: bool = False,
    safety_block: bool = False,
    shadow_mismatch: bool = False,
    operator_needed: bool = False,
    unknown_price_question: bool = False,
    no_catalog_match: bool = False,
    unknown_design: bool = False,
    low_confidence: bool = False,
    generic_reply: bool = False,
    ai_fallback: bool = False,
    manual: bool = False,
) -> str | None:
    """Pick the single most-informative reason from the active signals.

    Priority (high → low): openai_error, safety_block, shadow_mismatch,
    operator_needed, unknown_price_question, no_catalog_match, unknown_design,
    low_confidence, generic_reply, ai_fallback, manual. Returns ``None`` if no
    signal is active (→ nothing to capture).
    """
    if openai_error:
        return "openai_error"
    if safety_block:
        return "safety_block"
    if shadow_mismatch:
        return "shadow_live_mismatch"
    if operator_needed:
        return "operator_needed"
    if unknown_price_question:
        return "unknown_price_question"
    if no_catalog_match:
        return "no_catalog_match"
    if unknown_design:
        return "unknown_design"
    if low_confidence:
        return "low_confidence"
    if generic_reply:
        return "generic_reply"
    if ai_fallback:
        return "ai_fallback"
    if manual:
        return "manual_flag"
    return None


def severity_for_unknown_question(
    reason: str,
    *,
    order_readiness_score: int | None = None,
) -> str:
    """Return a severity for *reason*, escalated by buyer readiness.

    A hot, ready-to-buy customer (readiness ≥ 70) whose question failed is more
    costly than a cold one, so we bump one tier. Unknown reasons → ``medium``.
    """
    base = _REASON_SEVERITY.get(reason, "medium")
    if order_readiness_score is not None and order_readiness_score >= 70:
        idx = min(SEVERITIES.index(base) + 1, len(SEVERITIES) - 1)
        return SEVERITIES[idx]
    return base


# Minimum word count for a price question to be considered a substantive,
# unparseable failure rather than the normal short funnel entry ("narx qancha").
_PRICE_QUESTION_MIN_WORDS = 4


def classify_catalog_capture(
    *,
    matched: bool,
    needs_confirmation: bool,
    reason: str,
) -> str | None:
    """Decide whether a catalog resolution is a capture-worthy failure.

    Maps a ``CatalogLinkResult`` outcome to a capture reason, or ``None`` to skip.

    Capture-worthy: the resolver matched nothing specific, did not offer a
    confirmation prompt, and the text was not a plain generic catalog ask — i.e.
    ``reason == "no_alias"`` → ``"no_catalog_match"``.

    NOT a failure (returns ``None``):
    * ``matched`` — a specific design was found (success);
    * ``needs_confirmation`` — ambiguous / fuzzy near-miss handled by asking the
      user (good UX, not a miss);
    * ``reason == "generic_catalog_trigger"`` — the user just asked for "katalog"
      and got the full catalog (normal);
    * ``reason == "empty_text"``.
    """
    if matched or needs_confirmation:
        return None
    if reason == "no_alias":
        return "no_catalog_match"
    return None


def classify_price_capture(
    text: str | None, *, min_words: int = _PRICE_QUESTION_MIN_WORDS
) -> str | None:
    """Decide whether an unparseable price question is capture-worthy.

    Call this only on the terminal price branch where a price intent was detected
    but no area / design / district could be parsed. A short bare ask
    ("narx qancha") is the normal funnel entry and is **not** captured; a longer
    substantive question the bot still could not structure
    (``>= min_words`` words) is captured as ``"unknown_price_question"``.
    """
    if not text:
        return None
    if len(text.split()) >= min_words:
        return "unknown_price_question"
    return None


def build_unknown_question_event(
    *,
    reason: str,
    original_text: str | None,
    bot_reply: str | None = None,
    source: str = "telegram",
    channel_user_id: int | None = None,
    crm_contact_id: int | None = None,
    telegram_chat_id: int | str | None = None,
    intent: str | None = None,
    live_route: str | None = None,
    sdm_intent: str | None = None,
    sdm_next_action: str | None = None,
    order_readiness_score: int | None = None,
    severity: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a sanitized, ready-to-insert event dict (no ORM, no DB).

    All free text is sanitized; the chat id is hashed; severity is derived when
    not supplied. ``source`` / ``reason`` / ``severity`` are coerced to known
    vocabularies so a bad caller can never persist a junk enum value.
    """
    safe_source = source if source in SOURCES else "telegram"
    safe_reason = reason if reason in REASONS else "ai_fallback"
    sev = severity if severity in SEVERITIES else None
    if sev is None:
        sev = severity_for_unknown_question(
            safe_reason, order_readiness_score=order_readiness_score
        )
    preview = sanitize_unknown_question_text(original_text)
    return {
        "source": safe_source,
        "channel_user_id": channel_user_id,
        "crm_contact_id": crm_contact_id,
        "telegram_chat_id_hash": hash_chat_id(telegram_chat_id),
        "original_text_preview": preview,
        "original_text_hash": hash_question_text(original_text),
        "bot_reply_preview": (
            sanitize_unknown_question_text(bot_reply) if bot_reply is not None else None
        ),
        "reason": safe_reason,
        "intent": intent,
        "live_route": live_route,
        "sdm_intent": sdm_intent,
        "sdm_next_action": sdm_next_action,
        "order_readiness_score": order_readiness_score,
        "severity": sev,
        "status": "new",
        "metadata_json": metadata or None,
    }


def maybe_record_unknown_question(**kwargs: Any) -> dict[str, Any] | None:
    """Pure orchestrator: return a sanitized event dict, or ``None`` to skip.

    Accepts the same keyword signature as :func:`build_unknown_question_event`.
    Returns ``None`` (capture nothing) when:

    * ``reason`` is missing / unknown, or
    * the sanitized preview is empty **and** there is no reply to keep
      (e.g. a phone-number-only message reduces to an empty preview).

    This is the single decision point shared by the bot wiring and the tests.
    """
    reason = kwargs.get("reason")
    if not reason or reason not in REASONS:
        return None
    event = build_unknown_question_event(**kwargs)
    if not event["original_text_preview"] and not event["bot_reply_preview"]:
        return None
    return event


async def capture_unknown_question(**kwargs: Any) -> bool:
    """Persist one unknown-question event. Never raises.

    Designed to be fired from a bot handler via ``asyncio.create_task(...)``.
    Builds the event with :func:`maybe_record_unknown_question`; if that returns
    ``None`` nothing is written. All DB work is wrapped so a capture failure
    only logs a warning and returns ``False`` — it can never break the bot.
    """
    try:
        event = maybe_record_unknown_question(**kwargs)
        if event is None:
            return False
        # Import lazily so the pure functions above stay import-light and
        # framework-free (and so tests can monkeypatch the session factory).
        from infrastructure.database.models.agent_unknown_question import (
            AgentUnknownQuestionModel,
        )
        from infrastructure.database.session import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            session.add(AgentUnknownQuestionModel(**event))
            await session.commit()
        return True
    except Exception:  # never propagate into the bot reply path
        _log.warning("unknown_question_capture_failed", exc_info=False)
        return False
