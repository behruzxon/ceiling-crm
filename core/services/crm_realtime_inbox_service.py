"""
core.services.crm_realtime_inbox_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Live inbox summary builder. Pure functions — wraps CRMInboxAlertService.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

_TOKEN_RE = re.compile(r"(?:sk-|token[=:]|Bearer\s)\S+", re.IGNORECASE)
_PHONE_RE = re.compile(r"\+?\d{9,15}")


@dataclass(frozen=True)
class LiveInboxSummary:
    generated_at: str = ""
    unread_count: int = 0
    unanswered_count: int = 0
    critical_count: int = 0
    danger_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    hot_unanswered_count: int = 0
    operator_needed_count: int = 0
    latest_alerts: list[dict[str, Any]] = field(default_factory=list)


class CRMRealtimeInboxService:
    """Live inbox summary and diff helpers."""

    @staticmethod
    def build_live_summary(
        contacts: list[dict[str, Any]],
        now: datetime | None = None,
        max_alerts: int = 5,
    ) -> LiveInboxSummary:
        check_time = now or datetime.now(UTC)
        from core.services.crm_inbox_alert_service import CRMInboxAlertService

        overview = CRMInboxAlertService.get_alert_overview(contacts, check_time)
        alerts = CRMInboxAlertService.build_alerts(contacts, check_time, limit=max_alerts)
        unanswered = sum(
            1
            for c in contacts
            if c.get("last_message_direction") == "inbound"
            and c.get("lead_status") not in ("stopped", "lost", "won")
        )
        return LiveInboxSummary(
            generated_at=check_time.isoformat(),
            unread_count=overview.get("total", 0),
            unanswered_count=unanswered,
            critical_count=overview.get("critical", 0),
            danger_count=overview.get("danger", 0),
            warning_count=overview.get("warning", 0),
            info_count=overview.get("info", 0),
            hot_unanswered_count=overview.get("hot_unanswered", 0),
            operator_needed_count=overview.get("operator_needed", 0),
            latest_alerts=CRMRealtimeInboxService.serialize_alerts(alerts, max_alerts),
        )

    @staticmethod
    def serialize_alerts(
        alerts: list[Any],
        max_alerts: int = 5,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for alert in alerts[:max_alerts]:
            entry: dict[str, Any] = {
                "contact_id": getattr(alert, "contact_id", 0),
                "contact_name": CRMRealtimeInboxService._safe_text(
                    getattr(alert, "contact_name", ""),
                ),
                "alert_type": getattr(alert, "alert_type", ""),
                "severity": getattr(alert, "severity", "info"),
                "title": CRMRealtimeInboxService._safe_text(
                    getattr(alert, "title", ""),
                ),
                "message": CRMRealtimeInboxService._safe_text(
                    getattr(alert, "message", "")[:200],
                ),
                "unanswered_minutes": getattr(alert, "unanswered_minutes", 0),
                "priority": getattr(alert, "priority", 99),
            }
            result.append(entry)
        return result

    @staticmethod
    def diff_summary(
        previous: dict[str, Any] | None,
        current: LiveInboxSummary,
    ) -> dict[str, Any]:
        if previous is None:
            return {"changed": True, "pulse": current.critical_count > 0}
        changed = (
            previous.get("critical_count", 0) != current.critical_count
            or previous.get("danger_count", 0) != current.danger_count
            or previous.get("unanswered_count", 0) != current.unanswered_count
            or previous.get("hot_unanswered_count", 0) != current.hot_unanswered_count
            or previous.get("operator_needed_count", 0) != current.operator_needed_count
        )
        pulse = current.critical_count > previous.get("critical_count", 0)
        return {"changed": changed, "pulse": pulse}

    @staticmethod
    def should_pulse(
        previous: dict[str, Any] | None,
        current: LiveInboxSummary,
    ) -> bool:
        if previous is None:
            return current.critical_count > 0
        return current.critical_count > previous.get("critical_count", 0)

    @staticmethod
    def _safe_text(text: str) -> str:
        if not text:
            return ""
        text = _TOKEN_RE.sub("[REDACTED]", text)
        text = _PHONE_RE.sub("[PHONE]", text)
        return text[:300]
