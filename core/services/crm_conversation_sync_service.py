"""
core.services.crm_conversation_sync_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Full conversation timeline sync + answered/unanswered logic. Pure functions.
"""
from __future__ import annotations
import re
from datetime import datetime
from typing import Any

_TOKEN_RE = re.compile(r"(?:sk-|token[=:]|Bearer\s)\S+", re.IGNORECASE)
_PHONE_RE = re.compile(r"\+?\d{9,15}")
_NO_REPLY_STATUSES = frozenset({"stopped", "lost", "won"})
_ANSWERING_DIRECTIONS = frozenset({"outbound"})
_ANSWERING_SENDER_TYPES = frozenset({"bot", "operator"})


class CRMConversationSyncService:
    """Pure conversation sync logic."""

    @staticmethod
    def compute_answered_status(
        last_inbound_at: datetime | None,
        last_bot_reply_at: datetime | None,
        last_operator_reply_at: datetime | None,
        lead_status: str = "active",
    ) -> dict[str, Any]:
        if lead_status in _NO_REPLY_STATUSES:
            return {"is_unanswered": False, "answered_by": None, "reason": "terminal_status"}

        if not last_inbound_at:
            return {"is_unanswered": False, "answered_by": None, "reason": "no_inbound"}

        latest_reply = None
        answered_by = None
        for ts, who in [
            (last_bot_reply_at, "bot"),
            (last_operator_reply_at, "operator"),
        ]:
            if ts and (latest_reply is None or ts > latest_reply):
                latest_reply = ts
                answered_by = who

        if latest_reply and latest_reply >= last_inbound_at:
            return {"is_unanswered": False, "answered_by": answered_by, "reason": "replied"}

        return {"is_unanswered": True, "answered_by": None, "reason": "awaiting_reply"}

    @staticmethod
    def calculate_response_time_seconds(
        inbound_at: datetime,
        outbound_at: datetime,
    ) -> int:
        delta = outbound_at - inbound_at
        return max(0, int(delta.total_seconds()))

    @staticmethod
    def classify_event_type(
        direction: str,
        sender_type: str,
        message_type: str = "text",
    ) -> str:
        if direction == "agent_trace":
            return "agent_trace"
        if direction == "inbound":
            if message_type == "photo":
                return "photo"
            if message_type == "voice":
                return "voice"
            if message_type == "document":
                return "document"
            if message_type == "callback":
                return "callback"
            return "user_message"
        if direction == "outbound":
            if sender_type == "operator":
                return "operator_reply"
            if sender_type == "bot":
                return "bot_reply"
        if direction == "system":
            return "system"
        return "unknown"

    @staticmethod
    def is_answering_event(direction: str, sender_type: str) -> bool:
        return direction in _ANSWERING_DIRECTIONS and sender_type in _ANSWERING_SENDER_TYPES

    @staticmethod
    def redact_text(text: str) -> str:
        text = _PHONE_RE.sub("[***]", text)
        text = _TOKEN_RE.sub("[REDACTED]", text)
        return text

    @staticmethod
    def sanitize_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
        if not payload:
            return payload
        safe = dict(payload)
        for key in list(safe.keys()):
            val = safe[key]
            if isinstance(val, str):
                safe[key] = _TOKEN_RE.sub("[REDACTED]", val)
        return safe

    @staticmethod
    def build_conversation_summary(
        last_inbound_at: datetime | None,
        last_bot_reply_at: datetime | None,
        last_operator_reply_at: datetime | None,
        lead_status: str = "active",
        timeline_counts: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        answered = CRMConversationSyncService.compute_answered_status(
            last_inbound_at, last_bot_reply_at, last_operator_reply_at, lead_status,
        )
        unanswered_min = None
        if answered["is_unanswered"] and last_inbound_at:
            from datetime import UTC, datetime as dt
            now = dt.now(UTC)
            unanswered_min = max(0, int((now - last_inbound_at).total_seconds() / 60))

        return {
            "is_unanswered": answered["is_unanswered"],
            "answered_by": answered["answered_by"],
            "last_inbound_at": last_inbound_at.isoformat() if last_inbound_at else None,
            "last_bot_reply_at": last_bot_reply_at.isoformat() if last_bot_reply_at else None,
            "last_operator_reply_at": last_operator_reply_at.isoformat() if last_operator_reply_at else None,
            "unanswered_minutes": unanswered_min,
            "timeline_counts": timeline_counts or {},
        }
