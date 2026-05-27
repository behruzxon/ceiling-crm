"""
core.services.crm_sla_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
SLA computation for CRM contacts. Pure functions — no I/O.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

_NO_SLA_STATUSES = frozenset({"stopped", "lost", "won"})


class CRMSLAService:
    """Pure SLA computation."""

    @staticmethod
    def compute_unanswered_minutes(
        contact: dict[str, Any],
        now: datetime,
    ) -> int | None:
        if contact.get("lead_status") in _NO_SLA_STATUSES:
            return None
        last_inbound = contact.get("last_message_at")
        if not last_inbound:
            return None
        if isinstance(last_inbound, str):
            last_inbound = datetime.fromisoformat(last_inbound)
        last_reply = None
        for key in ("last_operator_reply_at", "last_bot_reply_at"):
            val = contact.get(key)
            if val:
                if isinstance(val, str):
                    val = datetime.fromisoformat(val)
                if last_reply is None or val > last_reply:
                    last_reply = val
        if last_reply and last_reply >= last_inbound:
            return 0
        delta = now - last_inbound
        return max(0, int(delta.total_seconds() / 60))

    @staticmethod
    def compute_sla_status(
        contact: dict[str, Any],
        now: datetime,
        due_soon: int = 5,
        overdue: int = 15,
        critical: int = 30,
        hot_critical: int = 10,
        operator_critical: int = 5,
    ) -> str:
        if contact.get("lead_status") in _NO_SLA_STATUSES:
            return "ok"
        mins = CRMSLAService.compute_unanswered_minutes(contact, now)
        if mins is None or mins == 0:
            return "ok"
        temp = contact.get("temperature")
        intent = contact.get("last_intent")
        if temp == "hot" and mins >= hot_critical:
            return "critical"
        if intent == "wants_operator" and mins >= operator_critical:
            return "critical"
        if contact.get("phone") and mins >= hot_critical:
            return "critical"
        if mins >= critical:
            return "critical"
        if mins >= overdue:
            return "overdue"
        if mins >= due_soon:
            return "due_soon"
        return "ok"

    @staticmethod
    def should_need_reply(contact: dict[str, Any], now: datetime) -> bool:
        if contact.get("lead_status") in _NO_SLA_STATUSES:
            return False
        mins = CRMSLAService.compute_unanswered_minutes(contact, now)
        return mins is not None and mins > 0

    @staticmethod
    def build_sla_overview(
        contacts: list[dict[str, Any]],
        now: datetime,
    ) -> dict[str, int]:
        counts = {"ok": 0, "due_soon": 0, "overdue": 0, "critical": 0, "unanswered": 0}
        for c in contacts:
            status = CRMSLAService.compute_sla_status(c, now)
            counts[status] = counts.get(status, 0) + 1
            if CRMSLAService.should_need_reply(c, now):
                counts["unanswered"] += 1
        return counts
