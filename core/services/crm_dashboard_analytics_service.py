"""
core.services.crm_dashboard_analytics_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Pure CRM analytics computation from contact/task data. No I/O.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from core.schemas.crm_dashboard_analytics import (
    CRMDashboardAnalytics,
    CRMFunnelStage,
    CRMMissedLeadMetrics,
)
from core.services.crm_sla_service import CRMSLAService

_FUNNEL_STAGES = [
    ("new", ("new",)),
    ("catalog", ("browsing", "active")),
    ("price", ("price_interested",)),
    ("phone", ("hot",)),
    ("operator", ("operator_needed",)),
    ("order", ("order_started",)),
    ("won", ("won",)),
    ("lost", ("lost", "stopped")),
]

_MISSED_HOT_MIN = 30
_MISSED_OPERATOR_MIN = 15
_MISSED_PHONE_MIN = 30
_MISSED_PRICE_HOURS = 24


class CRMDashboardAnalyticsService:
    """Pure analytics from lists of contacts and tasks."""

    @staticmethod
    def build_dashboard(
        contacts: list[dict[str, Any]],
        tasks: list[dict[str, Any]] | None = None,
        now: datetime | None = None,
    ) -> CRMDashboardAnalytics:
        from datetime import UTC
        from datetime import datetime as dt
        if now is None:
            now = dt.now(UTC)
        tasks = tasks or []

        temps = {"hot": 0, "warm": 0, "cold": 0}
        statuses: dict[str, int] = {}
        unanswered = 0
        critical = 0
        overdue = 0
        intents: dict[str, int] = {}
        objections: dict[str, int] = {}
        locations: dict[str, int] = {}
        missed = CRMDashboardAnalyticsService._compute_missed(contacts, now)

        for c in contacts:
            t = c.get("temperature")
            if t in temps:
                temps[t] += 1
            s = c.get("lead_status", "new")
            statuses[s] = statuses.get(s, 0) + 1

            sla = CRMSLAService.compute_sla_status(c, now)
            if sla == "critical":
                critical += 1
            elif sla == "overdue":
                overdue += 1
            if CRMSLAService.should_need_reply(c, now):
                unanswered += 1

            md = c.get("metadata_json") or {}
            intent = md.get("last_intent")
            if intent:
                intents[intent] = intents.get(intent, 0) + 1
            obj = md.get("objection_type")
            if obj:
                objections[obj] = objections.get(obj, 0) + 1
            loc = c.get("district") or md.get("district")
            if loc:
                locations[loc] = locations.get(loc, 0) + 1

        funnel = CRMDashboardAnalyticsService._build_funnel(statuses, len(contacts))
        task_metrics = CRMDashboardAnalyticsService._compute_task_metrics(tasks)
        recs = CRMDashboardAnalyticsService._build_recommendations(
            critical, overdue, unanswered, missed, task_metrics, objections,
        )

        return CRMDashboardAnalytics(
            generated_at=now.isoformat(),
            total_contacts=len(contacts),
            hot_leads=temps["hot"], warm_leads=temps["warm"], cold_leads=temps["cold"],
            stopped=statuses.get("stopped", 0),
            won=statuses.get("won", 0), lost=statuses.get("lost", 0),
            unanswered_count=unanswered, critical_count=critical, overdue_count=overdue,
            funnel=funnel, missed=missed,
            task_open=task_metrics["open"], task_overdue=task_metrics["overdue"],
            task_completed=task_metrics["completed"],
            task_completion_rate=task_metrics["rate"],
            top_intents=dict(sorted(intents.items(), key=lambda x: -x[1])[:10]),
            top_objections=dict(sorted(objections.items(), key=lambda x: -x[1])[:10]),
            top_locations=dict(sorted(locations.items(), key=lambda x: -x[1])[:10]),
            recommendations=recs,
        )

    @staticmethod
    def _build_funnel(
        statuses: dict[str, int], total: int,
    ) -> list[CRMFunnelStage]:
        stages: list[CRMFunnelStage] = []
        prev_count = total or 1
        for name, keys in _FUNNEL_STAGES:
            count = sum(statuses.get(k, 0) for k in keys)
            conv_prev = count / prev_count if prev_count > 0 else 0
            conv_total = count / total if total > 0 else 0
            stages.append(CRMFunnelStage(
                name=name, count=count,
                conversion_from_previous=round(conv_prev, 3),
                conversion_from_total=round(conv_total, 3),
            ))
            if count > 0:
                prev_count = count
        return stages

    @staticmethod
    def _compute_missed(
        contacts: list[dict[str, Any]], now: datetime,
    ) -> CRMMissedLeadMetrics:
        missed_hot = 0
        missed_op = 0
        missed_phone = 0
        missed_price = 0
        for c in contacts:
            mins = CRMSLAService.compute_unanswered_minutes(c, now) or 0
            if mins == 0:
                continue
            temp = c.get("temperature")
            md = c.get("metadata_json") or {}
            intent = md.get("last_intent")
            if temp == "hot" and mins >= _MISSED_HOT_MIN:
                missed_hot += 1
            if intent == "wants_operator" and mins >= _MISSED_OPERATOR_MIN:
                missed_op += 1
            if c.get("phone") and mins >= _MISSED_PHONE_MIN:
                missed_phone += 1
            if intent == "wants_price" and mins >= _MISSED_PRICE_HOURS * 60:
                missed_price += 1

        total = missed_hot + missed_op + missed_phone + missed_price
        return CRMMissedLeadMetrics(
            missed_lead_count=total, missed_hot_leads=missed_hot,
            missed_operator_requests=missed_op, missed_phone_shared=missed_phone,
            missed_price_interested=missed_price,
        )

    @staticmethod
    def _compute_task_metrics(tasks: list[dict[str, Any]]) -> dict[str, Any]:
        open_count = sum(1 for t in tasks if t.get("status") in ("todo", "in_progress"))
        overdue = sum(1 for t in tasks if t.get("status") in ("todo", "in_progress") and t.get("overdue"))
        completed = sum(1 for t in tasks if t.get("status") == "done")
        total = len(tasks) or 1
        return {"open": open_count, "overdue": overdue, "completed": completed,
                "rate": round(completed / total, 3) if tasks else 0.0}

    @staticmethod
    def _build_recommendations(
        critical: int, overdue: int, unanswered: int,
        missed: CRMMissedLeadMetrics, tasks: dict[str, Any],
        objections: dict[str, int],
    ) -> list[str]:
        recs: list[str] = []
        if critical > 5:
            recs.append("Critical javobsizlar ko'p — operator SLA'ni kuchaytiring")
        if missed.missed_hot_leads > 0:
            recs.append("Hot lead missed — tez javob berish vaqtini kamaytiring")
        if objections.get("price", 0) > 5:
            recs.append("Qimmat objection ko'p — arzonroq paket/offerni kuchaytiring")
        if tasks.get("overdue", 0) > 3:
            recs.append("Operator tasks overdue — reminder workflow kuchaytirilsin")
        if unanswered > 10:
            recs.append("Javobsiz mijozlar ko'p — operator staffni oshiring")
        return recs
