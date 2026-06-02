"""
core.services.operator_reply_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Operator Send-from-Web — deliver a single manual operator reply to one known
client via Telegram, from the CRM inbox.

Hard safety contract (see doc 158)
----------------------------------
* **Default OFF.** Sending requires ``OPERATOR_WEB_SEND_ENABLED=true``. While off,
  :func:`send_operator_reply` returns ``{"status": "sender_disabled"}`` and never
  touches Telegram.
* **One message, one known contact.** No bulk, no group, no AI auto-send, no
  campaign. The target chat id must already be on the contact.
* **Validated + sanitized.** Empty / too-long / secret-bearing messages are
  blocked; phones are masked in stored previews; tokens are never stored or logged.
* **Audited.** Every attempt (blocked / disabled / sent / failed) writes a
  ``crm_operator_outbound_audit`` row. On success the reply is also recorded as an
  ``operator`` message so it appears in the conversation timeline.
* **Send is injectable.** ``sender`` defaults to a real Bot built from the token
  server-side; tests inject a fake — no real Telegram send in tests.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from shared.utils.phone import mask_phone_in_text

try:
    from shared.logging import get_logger

    _log = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging

    _log = logging.getLogger(__name__)

# A sender returns (ok, telegram_message_id, error_type). Never raises.
Sender = Callable[[int, str], Awaitable[tuple[bool, "int | None", "str | None"]]]

_BLOCK_STATUSES = frozenset({"stopped", "lost"})

# Secret patterns — never deliver or store these.
_RE_SK = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")
_RE_BOT_TOKEN = re.compile(r"\b\d{6,12}:[A-Za-z0-9_\-]{20,}\b")
_RE_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-=]{8,}")
_RE_SECRET_KV = re.compile(
    r"(?i)\b(bot_token|api[_-]?key|openai[_-]?api[_-]?key|secret|password|database_url)\b\s*[:=]\s*\S+"
)
_RE_WS = re.compile(r"\s+")
_RE_PHONE_ANY = re.compile(r"\+?\d[\d\s\-]{6,}\d")


@dataclass(frozen=True)
class OperatorReplyValidation:
    ok: bool
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    preview: str = ""
    message_hash: str = ""


def _contains_secret(text: str | None) -> bool:
    if not text:
        return False
    s = str(text)
    return bool(
        _RE_SK.search(s)
        or _RE_BOT_TOKEN.search(s)
        or _RE_BEARER.search(s)
        or _RE_SECRET_KV.search(s)
    )


def sanitize_operator_reply(text: str | None) -> str:
    """Mask phones and normalize whitespace for the stored preview / send body.

    Secrets are NOT silently stripped — they are blocked by
    :func:`validate_operator_reply` so an operator can never deliver a leak.
    """
    if not text:
        return ""
    out = mask_phone_in_text(str(text))
    return _RE_WS.sub(" ", out).strip()


def resolve_chat_target(contact: dict[str, Any] | None) -> int | None:
    """Return the Telegram chat id to send to (chat id, else user id)."""
    if not contact:
        return None
    return contact.get("telegram_chat_id") or contact.get("telegram_user_id") or None


def _hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def validate_operator_reply(
    text: str | None,
    *,
    contact: dict[str, Any] | None,
    max_chars: int = 1000,
    block_stopped: bool = True,
) -> OperatorReplyValidation:
    """Validate a would-be operator reply (pure). Sanitizes for the preview.

    Blockers: contact_not_found, missing_chat_id, empty_text, text_too_long,
    secret_blocked, contact_stopped. Warning: contains_phone. The send-enabled
    flag is checked separately by :func:`send_operator_reply`.
    """
    blockers: list[str] = []
    warnings: list[str] = []
    raw = text or ""

    # secret check on RAW text (before phone masking can mangle a token)
    if _contains_secret(raw):
        blockers.append("secret_blocked")
    if not raw.strip():
        blockers.append("empty_text")
    if len(raw) > max_chars:
        blockers.append("text_too_long")

    if contact is None:
        blockers.append("contact_not_found")
    else:
        if resolve_chat_target(contact) is None:
            blockers.append("missing_chat_id")
        status = (contact.get("lead_status") or "").lower()
        if block_stopped and status in _BLOCK_STATUSES:
            blockers.append("contact_stopped")

    if _RE_PHONE_ANY.search(raw):
        warnings.append("contains_phone")

    preview = sanitize_operator_reply(raw)
    return OperatorReplyValidation(
        ok=not blockers,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        preview=preview,
        message_hash=_hash(raw),
    )


def block_when_disabled(enabled: bool) -> bool:
    """Return True if sending must be blocked because the feature is off."""
    return not enabled


async def _default_sender(chat_id: int, text: str) -> tuple[bool, int | None, str | None]:
    """Build a Bot from the configured token, send one message, close. Never raises.

    Returns (ok, telegram_message_id, error_type). The token is read server-side
    and never logged.
    """
    bot = None
    try:
        from aiogram import Bot

        from shared.config import get_settings

        token = get_settings().bot.token.get_secret_value()
        bot = Bot(token)
        sent = await bot.send_message(chat_id=chat_id, text=text)
        return True, getattr(sent, "message_id", None), None
    except Exception as exc:  # TelegramForbidden / network / anything
        return False, None, type(exc).__name__
    finally:
        if bot is not None:
            try:
                await bot.session.close()
            except Exception:  # pragma: no cover
                pass


async def record_operator_reply(
    session: Any,
    *,
    contact: dict[str, Any],
    status: str,
    message_hash: str,
    preview: str,
    operator: str | None,
    telegram_message_id: int | None = None,
    blocked_reason: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    """Write one audit row (and, on ``sent``, an operator message). Returns audit dict."""
    from infrastructure.database.models.crm_operator_outbound_audit import (
        CRMOperatorOutboundAuditModel,
    )

    now = datetime.now(UTC)
    audit = CRMOperatorOutboundAuditModel(
        contact_id=contact["id"],
        telegram_user_id=contact.get("telegram_user_id"),
        telegram_chat_id=resolve_chat_target(contact),
        operator_id=(str(operator)[:50] if operator else None),
        message_hash=message_hash,
        message_preview=preview[:100],
        status=status,
        blocked_reason=(blocked_reason[:255] if blocked_reason else None),
        error_message=(error_message[:500] if error_message else None),
        telegram_message_id=telegram_message_id,
        sent_at=now if status == "sent" else None,
        failed_at=now if status == "failed" else None,
    )
    session.add(audit)

    if status == "sent":
        # Mirror into the conversation timeline as an operator-outbound message.
        from core.services.crm_message_service import CRMMessageService

        await CRMMessageService(session).record_outbound(
            contact_id=contact["id"],
            text=preview,
            sender_type="operator",
        )
    await session.commit()
    return {
        "status": status,
        "telegram_message_id": telegram_message_id,
        "blocked_reason": blocked_reason,
        "error": error_message,
    }


async def send_operator_reply(
    session: Any,
    *,
    contact: dict[str, Any] | None,
    text: str,
    enabled: bool,
    max_chars: int = 1000,
    confirm_send: bool = False,
    confirm_required: bool = True,
    block_stopped: bool = True,
    operator: str | None = None,
    sender: Sender | None = None,
) -> dict[str, Any]:
    """Orchestrate one operator reply. Never raises.

    Order: feature-flag gate → validation → confirm gate → send → audit. Returns a
    dict with ``status`` in {sender_disabled, blocked, confirm_required, sent,
    failed}. The reply is delivered ONLY when ``enabled`` is true, validation
    passes, and (when required) ``confirm_send`` is true.
    """
    # 1) Feature-flag gate — never send while off.
    if block_when_disabled(enabled):
        if contact:
            await record_operator_reply(
                session,
                contact=contact,
                status="blocked",
                message_hash=_hash(text or ""),
                preview=sanitize_operator_reply(text)[:100],
                operator=operator,
                blocked_reason="sender_disabled",
            )
        return {"status": "sender_disabled"}

    # 2) Validation.
    v = validate_operator_reply(
        text, contact=contact, max_chars=max_chars, block_stopped=block_stopped
    )
    if not v.ok:
        if contact:
            await record_operator_reply(
                session,
                contact=contact,
                status="blocked",
                message_hash=v.message_hash,
                preview=v.preview,
                operator=operator,
                blocked_reason=",".join(v.blockers)[:255],
            )
        return {"status": "blocked", "blockers": list(v.blockers), "warnings": list(v.warnings)}

    # 3) Confirmation gate (no send, no audit — nothing happened yet).
    if confirm_required and not confirm_send:
        return {"status": "confirm_required", "preview": v.preview, "warnings": list(v.warnings)}

    # 4) Send (injectable; default builds a real Bot server-side).
    chat_id = resolve_chat_target(contact)
    send = sender or _default_sender
    ok, msg_id, err = await send(int(chat_id), v.preview)  # type: ignore[arg-type]

    # 5) Audit.
    status = "sent" if ok else "failed"
    await record_operator_reply(
        session,
        contact=contact,  # type: ignore[arg-type]
        status=status,
        message_hash=v.message_hash,
        preview=v.preview,
        operator=operator,
        telegram_message_id=msg_id,
        error_message=(None if ok else (err or "send_failed")),
    )
    if ok:
        _log.info("operator_reply_sent", contact_id=contact["id"], telegram_message_id=msg_id)  # type: ignore[index]
        return {"status": "sent", "telegram_message_id": msg_id}
    _log.warning("operator_reply_failed", contact_id=contact["id"], error_type=err)  # type: ignore[index]
    return {"status": "failed", "error": err}
