"""
core.services.crm_operator_task_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Operator task management + recommendation from alerts. Pure validation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_VALID_TYPES = frozenset({
    "reply", "call", "follow_up", "measurement",
    "price_offer", "catalog_send", "order_check", "custom",
})
_VALID_STATUSES = frozenset({"todo", "in_progress", "done", "snoozed", "cancelled"})
_VALID_PRIORITIES = frozenset({"low", "normal", "high", "urgent"})
_ACTIVE_STATUSES = frozenset({"todo", "in_progress", "snoozed"})
_NO_TASK_STATUSES = frozenset({"stopped", "lost", "won"})


@dataclass(frozen=True)
class TaskRecommendation:
    contact_id: int = 0
    contact_name: str = ""
    task_type: str = "reply"
    priority: str = "normal"
    title: str = ""
    reason: str = ""


class CRMOperatorTaskService:
    """Pure task validation + recommendation logic."""

    @staticmethod
    def is_valid_type(t: str) -> bool:
        return t in _VALID_TYPES

    @staticmethod
    def is_valid_status(s: str) -> bool:
        return s in _VALID_STATUSES

    @staticmethod
    def is_valid_priority(p: str) -> bool:
        return p in _VALID_PRIORITIES

    @staticmethod
    def validate_create(
        title: str, task_type: str, priority: str = "normal",
    ) -> tuple[bool, str | None]:
        if not title or not title.strip():
            return False, "empty_title"
        if len(title) > 200:
            return False, "title_too_long"
        if task_type not in _VALID_TYPES:
            return False, f"invalid_type:{task_type}"
        if priority not in _VALID_PRIORITIES:
            return False, f"invalid_priority:{priority}"
        return True, None

    @staticmethod
    def recommend_task_for_contact(
        contact: dict[str, Any],
        alert_type: str | None = None,
        alert_severity: str | None = None,
    ) -> TaskRecommendation | None:
        status = contact.get("lead_status", "")
        if status in _NO_TASK_STATUSES:
            return None

        name = contact.get("first_name") or contact.get("username") or "?"
        cid = contact.get("id", 0)

        if alert_type == "critical_sla" or alert_severity == "critical":
            return TaskRecommendation(
                contact_id=cid, contact_name=name,
                task_type="reply", priority="urgent",
                title=f"Tez javob: {name}",
                reason="SLA critical — tez javob kerak",
            )
        if alert_type == "hot_unanswered":
            return TaskRecommendation(
                contact_id=cid, contact_name=name,
                task_type="reply", priority="urgent",
                title=f"Hot lead javob: {name}",
                reason="Hot lead javobsiz",
            )
        if alert_type == "operator_needed":
            return TaskRecommendation(
                contact_id=cid, contact_name=name,
                task_type="call", priority="urgent",
                title=f"Operator: {name}",
                reason="Mijoz operator so'ramoqda",
            )
        if alert_type == "phone_shared_unanswered":
            return TaskRecommendation(
                contact_id=cid, contact_name=name,
                task_type="call", priority="high",
                title=f"Qo'ng'iroq: {name}",
                reason="Telefon qoldirgan, javobsiz",
            )
        if alert_type == "overdue":
            return TaskRecommendation(
                contact_id=cid, contact_name=name,
                task_type="reply", priority="high",
                title=f"Javob berish: {name}",
                reason="Javob kechikmoqda",
            )

        md = contact.get("metadata_json") or {}
        intent = md.get("last_intent")
        if intent == "wants_price":
            return TaskRecommendation(
                contact_id=cid, contact_name=name,
                task_type="price_offer", priority="high",
                title=f"Narx taklif: {name}",
                reason="Narx so'ramoqda",
            )
        if md.get("objection_type") == "price":
            return TaskRecommendation(
                contact_id=cid, contact_name=name,
                task_type="follow_up", priority="normal",
                title=f"Arzonroq taklif: {name}",
                reason="Narx e'tirozi bor",
            )

        return None

    @staticmethod
    def recommend_tasks_from_alerts(
        alerts: list[dict[str, Any]],
        contacts: dict[int, dict[str, Any]],
    ) -> list[TaskRecommendation]:
        recs: list[TaskRecommendation] = []
        for a in alerts:
            cid = a.get("contact_id", 0)
            contact = contacts.get(cid, {"id": cid})
            rec = CRMOperatorTaskService.recommend_task_for_contact(
                contact, a.get("alert_type"), a.get("severity"),
            )
            if rec:
                recs.append(rec)
        return recs

    @staticmethod
    def calculate_task_priority(
        contact: dict[str, Any],
        alert_severity: str | None = None,
    ) -> str:
        if alert_severity == "critical":
            return "urgent"
        if alert_severity == "danger":
            return "high"
        temp = contact.get("temperature")
        if temp == "hot":
            return "high"
        if temp == "warm":
            return "normal"
        return "low"
