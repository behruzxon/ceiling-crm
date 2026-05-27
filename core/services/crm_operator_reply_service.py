"""
core.services.crm_operator_reply_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Operator reply validation and send (mockable). Feature-flag gated.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

_TOKEN_RE = re.compile(r"(?:sk-|token[=:]|Bearer\s)\S+", re.IGNORECASE)
_BOT_TOKEN_RE = re.compile(r"\d{8,10}:[A-Za-z0-9_-]{30,50}")
_PHONE_RE = re.compile(r"\+?\d{9,15}")
_BLOCKED_STATUSES = frozenset({"stopped", "lost"})


class TelegramSender(Protocol):
    async def send_message(self, chat_id: int, text: str) -> Any: ...


@dataclass(frozen=True)
class ReplyPreviewResult:
    allowed: bool = False
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sanitized_preview: str = ""
    message_hash: str = ""


class CRMOperatorReplyService:
    """Operator reply validation. Pure validation methods + send wrapper."""

    @staticmethod
    def preview_reply(
        contact: dict[str, Any] | None,
        text: str,
        enabled: bool = False,
        max_length: int = 1000,
        block_stopped: bool = True,
    ) -> ReplyPreviewResult:
        blockers: list[str] = []
        warnings: list[str] = []

        if not enabled:
            blockers.append("operator_reply_disabled")
        if not text or not text.strip():
            blockers.append("empty_text")
        elif len(text) > max_length:
            blockers.append(f"text_too_long:{len(text)}/{max_length}")

        if contact is None:
            blockers.append("contact_not_found")
        else:
            chat_id = contact.get("telegram_chat_id") or contact.get("telegram_user_id")
            if not chat_id:
                blockers.append("missing_chat_id")
            status = contact.get("lead_status", "")
            if block_stopped and status in _BLOCKED_STATUSES:
                blockers.append(f"contact_{status}")
            md = contact.get("metadata_json") or {}
            if md.get("followup_disabled"):
                blockers.append("followup_disabled")
            if contact.get("temperature") == "cold":
                warnings.append("cold_contact")

        if text and _TOKEN_RE.search(text):
            blockers.append("token_pattern")
        if text and _BOT_TOKEN_RE.search(text):
            blockers.append("bot_token_pattern")

        if text and _PHONE_RE.search(text):
            warnings.append("contains_phone")

        preview = (text or "")[:100]
        msg_hash = hashlib.sha256((text or "").encode()).hexdigest()[:16]

        return ReplyPreviewResult(
            allowed=len(blockers) == 0,
            blockers=blockers, warnings=warnings,
            sanitized_preview=preview, message_hash=msg_hash,
        )

    @staticmethod
    def redact_error(error: str) -> str:
        error = _TOKEN_RE.sub("[REDACTED]", error)
        error = _BOT_TOKEN_RE.sub("[REDACTED]", error)
        return error[:500]

    @staticmethod
    def build_message_hash(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]
