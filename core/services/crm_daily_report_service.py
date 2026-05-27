"""
core.services.crm_daily_report_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Daily CRM report generation. Pure summary logic + schema.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

_TOKEN_RE = re.compile(r"(?:sk-|token[=:]|Bearer\s)\S+", re.IGNORECASE)


@dataclass(frozen=True)
class CRMDailyReportSnapshot:
    report_date: str = ""
    title: str = ""
    status: str = "generated"
    delivery_mode: str = "disabled"
    new_contacts: int = 0
    total_contacts: int = 0
    hot_leads: int = 0
    unanswered_count: int = 0
    critical_count: int = 0
    missed_leads: int = 0
    tasks_open: int = 0
    tasks_overdue: int = 0
    tasks_completed: int = 0
    won_count: int = 0
    lost_count: int = 0
    top_intents: dict[str, int] = field(default_factory=dict)
    top_objections: dict[str, int] = field(default_factory=dict)
    top_locations: dict[str, int] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    generated_at: str = ""


class CRMDailyReportService:
    """Pure daily report logic."""

    @staticmethod
    def build_report_title(report_date: date | None = None) -> str:
        if report_date is None:
            report_date = date.today()
        return f"CRM Kunlik Hisobot — {report_date.isoformat()}"

    @staticmethod
    def build_summary_from_analytics(
        analytics: dict[str, Any],
        report_date: date | None = None,
    ) -> CRMDailyReportSnapshot:
        from datetime import UTC
        from datetime import datetime as dt

        if report_date is None:
            report_date = date.today()
        missed = analytics.get("missed") or {}

        return CRMDailyReportSnapshot(
            report_date=report_date.isoformat(),
            title=CRMDailyReportService.build_report_title(report_date),
            new_contacts=analytics.get("new_contacts", 0),
            total_contacts=analytics.get("total_contacts", 0),
            hot_leads=analytics.get("hot_leads", 0),
            unanswered_count=analytics.get("unanswered_count", 0),
            critical_count=analytics.get("critical_count", 0),
            missed_leads=missed.get("missed_lead_count", 0),
            tasks_open=analytics.get("task_open", 0),
            tasks_overdue=analytics.get("task_overdue", 0),
            tasks_completed=analytics.get("task_completed", 0),
            won_count=analytics.get("won", 0),
            lost_count=analytics.get("lost", 0),
            top_intents=analytics.get("top_intents", {}),
            top_objections=analytics.get("top_objections", {}),
            top_locations=analytics.get("top_locations", {}),
            recommendations=analytics.get("recommendations", []),
            generated_at=dt.now(UTC).isoformat(),
        )

    @staticmethod
    def evaluate_report_status(summary: CRMDailyReportSnapshot) -> str:
        if summary.critical_count > 5 or summary.missed_leads > 3:
            return "needs_attention"
        return "ok"

    @staticmethod
    def sanitize_report_payload(data: dict[str, Any]) -> dict[str, Any]:
        safe = dict(data)
        for key, val in safe.items():
            if isinstance(val, str):
                safe[key] = _TOKEN_RE.sub("[REDACTED]", val)
        return safe

    @staticmethod
    def redact_error(error: str) -> str:
        return _TOKEN_RE.sub("[REDACTED]", error)[:500]
