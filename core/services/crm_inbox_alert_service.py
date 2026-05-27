"""
core.services.crm_inbox_alert_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Computed inbox alerts from contact SLA/status. Pure functions — no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from core.services.crm_sla_service import CRMSLAService

_NO_ALERT_STATUSES = frozenset({"stopped", "lost", "won"})
_SEVERITY_ORDER = {"critical": 0, "danger": 1, "warning": 2, "info": 3}


@dataclass(frozen=True)
class InboxAlert:
    contact_id: int = 0
    contact_name: str = ""
    alert_type: str = "new_message"
    severity: str = "info"
    title: str = ""
    message: str = ""
    unanswered_minutes: int = 0
    sla_status: str = "ok"
    priority: int = 99


class CRMInboxAlertService:
    """Pure computed alerts from contact data."""

    @staticmethod
    def build_contact_alert(
        contact: dict[str, Any], now: datetime,
    ) -> InboxAlert | None:
        status = contact.get("lead_status", "")
        if status in _NO_ALERT_STATUSES:
            return None

        sla = CRMSLAService.compute_sla_status(contact, now)
        mins = CRMSLAService.compute_unanswered_minutes(contact, now) or 0
        if mins == 0 and sla == "ok":
            return None

        name = contact.get("first_name") or contact.get("username") or "?"
        cid = contact.get("id", 0)
        temp = contact.get("temperature")
        intent = contact.get("last_intent") or (contact.get("metadata_json") or {}).get("last_intent")

        if temp == "hot" and mins > 0:
            sev, atype, pri = "critical", "hot_unanswered", 2
        elif intent == "wants_operator" and mins > 0:
            sev, atype, pri = "critical", "operator_needed", 3
        elif contact.get("phone") and mins > 0:
            sev, atype, pri = "critical", "phone_shared_unanswered", 4
        elif sla == "critical":
            sev, atype, pri = "critical", "critical_sla", 1
        elif sla == "overdue":
            sev, atype, pri = "danger", "overdue", 5
        elif sla == "due_soon":
            sev, atype, pri = "warning", "due_soon", 6
        elif mins > 0:
            sev, atype, pri = "info", "new_message", 7
        else:
            return None

        title = CRMInboxAlertService._build_title(atype, name)
        msg = f"{mins} min javobsiz" if mins > 0 else ""

        return InboxAlert(
            contact_id=cid, contact_name=name, alert_type=atype,
            severity=sev, title=title, message=msg,
            unanswered_minutes=mins, sla_status=sla, priority=pri,
        )

    @staticmethod
    def build_alerts(
        contacts: list[dict[str, Any]], now: datetime,
        limit: int = 50, severity: str | None = None,
        alert_type: str | None = None,
    ) -> list[InboxAlert]:
        alerts: list[InboxAlert] = []
        for c in contacts:
            a = CRMInboxAlertService.build_contact_alert(c, now)
            if a is None:
                continue
            if severity and a.severity != severity:
                continue
            if alert_type and a.alert_type != alert_type:
                continue
            alerts.append(a)
        alerts.sort(key=lambda a: a.priority)
        return alerts[:limit]

    @staticmethod
    def get_alert_overview(
        contacts: list[dict[str, Any]], now: datetime,
    ) -> dict[str, int]:
        counts = {"critical": 0, "danger": 0, "warning": 0, "info": 0,
                  "total": 0, "hot_unanswered": 0, "operator_needed": 0}
        for c in contacts:
            a = CRMInboxAlertService.build_contact_alert(c, now)
            if a is None:
                continue
            counts["total"] += 1
            counts[a.severity] = counts.get(a.severity, 0) + 1
            if a.alert_type == "hot_unanswered":
                counts["hot_unanswered"] += 1
            if a.alert_type == "operator_needed":
                counts["operator_needed"] += 1
        return counts

    @staticmethod
    def _build_title(alert_type: str, name: str) -> str:
        titles = {
            "critical_sla": f"CRITICAL: {name} — tez javob kerak!",
            "hot_unanswered": f"HOT LEAD: {name} — javobsiz!",
            "operator_needed": f"OPERATOR: {name} — operator so'ramoqda",
            "phone_shared_unanswered": f"TELEFON: {name} — javobsiz!",
            "overdue": f"Overdue: {name} — javob kechikmoqda",
            "due_soon": f"Due soon: {name} — tez javob bering",
            "new_message": f"Yangi xabar: {name}",
        }
        return titles.get(alert_type, f"Alert: {name}")
