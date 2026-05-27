"""
core.services.crm_report_delivery_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Daily report delivery validation + approval. Pure functions.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

_TOKEN_RE = re.compile(r"(?:sk-|token[=:]|Bearer\s)\S+", re.IGNORECASE)
_BOT_TOKEN_RE = re.compile(r"\d{8,10}:[A-Za-z0-9_-]{30,50}")
_VALID_CHANNELS = frozenset({"telegram", "email", "log_only", "draft"})


@dataclass(frozen=True)
class DeliveryPreviewResult:
    allowed: bool = False
    channel: str = ""
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    requires_approval: bool = False
    message_preview: str = ""


class CRMReportDeliveryService:
    """Pure delivery validation and approval logic."""

    @staticmethod
    def validate_delivery(
        channel: str,
        delivery_enabled: bool = False,
        telegram_enabled: bool = False,
        email_enabled: bool = False,
        log_only_enabled: bool = True,
        approval_required: bool = True,
        is_approved: bool = False,
        report_exists: bool = True,
        message_text: str = "",
    ) -> DeliveryPreviewResult:
        blockers: list[str] = []
        warnings: list[str] = []

        if channel not in _VALID_CHANNELS:
            blockers.append(f"invalid_channel:{channel}")

        if not report_exists:
            blockers.append("report_not_found")

        if not delivery_enabled and channel not in ("log_only", "draft"):
            blockers.append("delivery_disabled")

        if channel == "telegram" and not telegram_enabled:
            blockers.append("telegram_disabled")
        if channel == "email" and not email_enabled:
            blockers.append("email_disabled")
        if channel == "log_only" and not log_only_enabled:
            blockers.append("log_only_disabled")

        if channel in ("telegram", "email") and approval_required and not is_approved:
            blockers.append("approval_required")

        if message_text and _TOKEN_RE.search(message_text):
            blockers.append("token_in_message")
        if message_text and _BOT_TOKEN_RE.search(message_text):
            blockers.append("bot_token_in_message")

        needs_approval = channel in ("telegram", "email") and approval_required and not is_approved

        preview = (message_text or "")[:2000]

        return DeliveryPreviewResult(
            allowed=len(blockers) == 0,
            channel=channel,
            blockers=blockers,
            warnings=warnings,
            requires_approval=needs_approval,
            message_preview=preview,
        )

    @staticmethod
    def hash_recipient(recipient: str) -> str:
        return hashlib.sha256(recipient.encode()).hexdigest()[:16]

    @staticmethod
    def redact_recipient(recipient: str) -> str:
        if not recipient:
            return ""
        if len(recipient) <= 4:
            return "***"
        return recipient[:2] + "***" + recipient[-2:]

    @staticmethod
    def sanitize_message(text: str) -> str:
        text = _TOKEN_RE.sub("[REDACTED]", text)
        text = _BOT_TOKEN_RE.sub("[REDACTED]", text)
        return text

    @staticmethod
    def redact_error(error: str) -> str:
        error = _TOKEN_RE.sub("[REDACTED]", error)
        error = _BOT_TOKEN_RE.sub("[REDACTED]", error)
        return error[:500]

    @staticmethod
    def build_report_message(
        summary: dict[str, Any],
        max_length: int = 2000,
    ) -> str:
        parts = [
            f"CRM Kunlik Hisobot — {summary.get('report_date', 'bugun')}",
            "",
            f"Yangi mijozlar: {summary.get('new_contacts', 0)}",
            f"Hot leadlar: {summary.get('hot_leads', 0)}",
            f"Javobsiz: {summary.get('unanswered_count', 0)}",
            f"Critical: {summary.get('critical_count', 0)}",
            f"Missed leadlar: {summary.get('missed_leads', 0)}",
            f"Vazifalar: {summary.get('tasks_open', 0)} ochiq, {summary.get('tasks_overdue', 0)} kechikkan",
        ]
        recs = summary.get("recommendations", [])
        if recs:
            parts.append("")
            parts.append("Tavsiyalar:")
            for r in recs[:5]:
                parts.append(f"• {r}")

        text = "\n".join(parts)
        return CRMReportDeliveryService.sanitize_message(text[:max_length])
