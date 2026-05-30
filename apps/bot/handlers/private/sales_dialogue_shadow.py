"""
apps.bot.handlers.private.sales_dialogue_shadow
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Shadow / LOG-ONLY integration for the Sales Dialogue Manager.

When ``SALES_DIALOGUE_MANAGER_SHADOW_ENABLED`` is **on**, the AI handlers call
:func:`maybe_log_sales_dialogue_shadow` to compute the dialogue-manager decision
for the current message and **log a sanitized summary only**. It never produces
a customer-facing reply, never mutates the DB or FSM, never calls Telegram or
OpenAI, and never breaks the live flow.

When the flag is **off** (the default), the function returns immediately — zero
work, zero behaviour change.

Safety:
* Raw phone numbers, tokens, keys and DB URLs are redacted from the preview.
* The full raw message is never logged — only a redacted ≤120-char preview.
* Every exception is swallowed and logged as a warning.

See ``docs/AI_AGENT_SYSTEM/146_SALES_DIALOGUE_MANAGER_SHADOW_INTEGRATION.md``.
"""

from __future__ import annotations

import re
from typing import Any

from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)

_MAX_PREVIEW = 120

# Redaction patterns (aligned with the existing precedents in
# agent_response_orchestrator._redact and catalog_link_resolver._SECRET_PATTERNS).
_REDACTORS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"sk-[A-Za-z0-9]{8,}"), "[redacted_key]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9._\-]{4,}", re.I), "[redacted_bearer]"),
    (re.compile(r"\d{6,}:[A-Za-z0-9_\-]{20,}"), "[redacted_bot_token]"),
    (re.compile(r"postgres(?:ql)?://[^\s\"']+", re.I), "[redacted_db_url]"),
    (re.compile(r"redis://[^\s\"']+", re.I), "[redacted_redis_url]"),
    (re.compile(r"\bBOT_TOKEN\b", re.I), "[redacted_marker]"),
    (re.compile(r"\bOPENAI\b", re.I), "[redacted_marker]"),
    (re.compile(r"\bDATABASE_URL\b", re.I), "[redacted_marker]"),
    # Phone-like digit runs (>= 7 digits, optional +/spaces/dashes) — last so
    # it does not clobber the bot-token pattern above.
    (re.compile(r"\+?\d[\d\s\-]{6,}\d"), "[redacted_phone]"),
)


def _safe_preview(text: str) -> str:
    """Redact secrets / phones from ``text`` and truncate to ``_MAX_PREVIEW``."""
    snippet = (text or "").replace("\n", " ").strip()
    for pattern, replacement in _REDACTORS:
        snippet = pattern.sub(replacement, snippet)
    if len(snippet) > _MAX_PREVIEW:
        snippet = snippet[: _MAX_PREVIEW - 1].rstrip() + "…"
    return snippet


def _mask_id(value: int | str | None) -> str:
    """Mask an id to its last 4 chars (chat ids are not logged in the clear)."""
    if value is None:
        return ""
    s = str(value)
    if len(s) <= 4:
        return "*" * len(s)
    return "*" * (len(s) - 4) + s[-4:]


async def maybe_log_sales_dialogue_shadow(
    *,
    text: str,
    state_data: dict[str, Any] | None,
    user_id: int | str | None = None,
    chat_id: int | str | None = None,
    live_route: str | None = None,
) -> None:
    """Compute the Sales Dialogue Manager decision and log a sanitized summary.

    No-op when the shadow flag is off or the text is empty. Never raises, never
    produces a user reply, never touches the DB / FSM / Telegram / OpenAI.
    """
    try:
        settings = get_settings()
        if not settings.business.sales_dialogue_manager_shadow_enabled:
            return
        if not text or not text.strip():
            return

        # Pure, no-I/O planner. Imported lazily so flag-off path never pays.
        from core.services.sales_dialogue_manager_service import plan_turn

        plan = plan_turn(text, state_data, None)
        d = plan.decision

        # user_id is logged raw to match the existing handler-log convention
        # (it aids cross-log correlation); chat_id is masked.
        log.info(
            "sales_dialogue_shadow_decision",
            user_id=user_id if user_id else None,
            chat_id=_mask_id(chat_id),
            live_route=live_route or "unknown",
            sdm_intent=d.intent,
            sdm_next_action=d.next_action,
            sdm_confidence=round(float(d.confidence), 2),
            order_readiness_score=int(d.order_readiness_score),
            missing_fields=list(d.missing_fields),
            reason=(d.reason or "")[:60],
            safety_note=(d.safety_note or "")[:60],
            preview=_safe_preview(text),
        )
    except Exception:
        # Shadow must never affect the live flow.
        log.warning("sales_dialogue_shadow_failed")


async def fire_shadow_for_message(
    message: Any,
    state: Any,
    *,
    live_route: str,
) -> None:
    """Gated convenience wrapper for handler entry points (catalog, measurement).

    Extracts text + FSM state from the message/state and forwards to
    :func:`maybe_log_sales_dialogue_shadow` with the given ``live_route``. A
    safe no-op when the flag is off (it does not even read FSM state then).
    Never mutates state, never replies, never raises.
    """
    try:
        if not get_settings().business.sales_dialogue_manager_shadow_enabled:
            return
        text = getattr(message, "text", None) or ""
        from_user = getattr(message, "from_user", None)
        chat = getattr(message, "chat", None)
        user_id = from_user.id if from_user else None
        chat_id = chat.id if chat else None
        state_data: dict[str, Any] | None = None
        if state is not None:
            try:
                state_data = await state.get_data()
            except Exception:
                state_data = None
        await maybe_log_sales_dialogue_shadow(
            text=text,
            state_data=state_data,
            user_id=user_id,
            chat_id=chat_id,
            live_route=live_route,
        )
    except Exception:
        # Shadow must never affect the live flow.
        log.warning("sales_dialogue_shadow_failed")


__all__ = ["maybe_log_sales_dialogue_shadow", "fire_shadow_for_message"]
