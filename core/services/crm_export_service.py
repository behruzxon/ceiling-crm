"""
core.services.crm_export_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
CRM data export: CSV, summary data. Pure functions — no I/O.
CSV injection guard, phone redaction, token removal.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from typing import Any

_TOKEN_RE = re.compile(r"(?:sk-|token[=:]|Bearer\s)\S+", re.IGNORECASE)
_BOT_TOKEN_RE = re.compile(r"\d{8,10}:[A-Za-z0-9_-]{30,50}")
_CSV_INJECTION_CHARS = frozenset({"=", "+", "-", "@"})

_CONTACT_COLUMNS = [
    "contact_id",
    "username",
    "first_name",
    "last_name",
    "lead_status",
    "temperature",
    "lead_score",
    "source",
    "created_at",
]
_CONTACT_COLUMNS_WITH_PHONE = _CONTACT_COLUMNS + ["phone"]


class CRMExportService:
    """Pure export logic: CSV generation, sanitization, guards."""

    @staticmethod
    def export_contacts_csv(
        contacts: list[dict[str, Any]],
        include_phone: bool = False,
        max_rows: int = 5000,
    ) -> str:
        cols = _CONTACT_COLUMNS_WITH_PHONE if include_phone else _CONTACT_COLUMNS
        rows = contacts[:max_rows]
        return CRMExportService._build_csv(cols, rows)

    @staticmethod
    def export_hot_leads_csv(
        contacts: list[dict[str, Any]],
        include_phone: bool = False,
        max_rows: int = 5000,
    ) -> str:
        cols = [
            "contact_id",
            "first_name",
            "lead_score",
            "temperature",
            "last_intent",
            "objection_type",
            "area_m2",
            "district",
        ]
        if include_phone:
            cols.append("phone")
        hot = [c for c in contacts if c.get("temperature") == "hot"][:max_rows]
        return CRMExportService._build_csv(cols, hot)

    @staticmethod
    def export_funnel_csv(funnel_stages: list[dict[str, Any]]) -> str:
        cols = ["stage", "count", "conversion_from_previous", "conversion_from_total"]
        return CRMExportService._build_csv(cols, funnel_stages)

    @staticmethod
    def export_tasks_csv(tasks: list[dict[str, Any]], max_rows: int = 5000) -> str:
        cols = [
            "task_id",
            "contact_id",
            "title",
            "task_type",
            "status",
            "priority",
            "due_at",
            "completed_at",
            "assigned_to",
            "source",
        ]
        return CRMExportService._build_csv(cols, tasks[:max_rows])

    @staticmethod
    def build_daily_summary_data(
        analytics: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "title": "CRM Daily Summary Report",
            "total_contacts": analytics.get("total_contacts", 0),
            "hot_leads": analytics.get("hot_leads", 0),
            "unanswered": analytics.get("unanswered_count", 0),
            "critical": analytics.get("critical_count", 0),
            "missed_leads": (analytics.get("missed") or {}).get("missed_lead_count", 0),
            "task_open": analytics.get("task_open", 0),
            "task_overdue": analytics.get("task_overdue", 0),
            "recommendations": analytics.get("recommendations", []),
        }

    @staticmethod
    def sanitize_csv_value(value: Any) -> str:
        if value is None:
            return ""
        s = str(value)
        s = _TOKEN_RE.sub("[REDACTED]", s)
        s = _BOT_TOKEN_RE.sub("[REDACTED]", s)
        if s and s[0] in _CSV_INJECTION_CHARS:
            s = "'" + s
        return s

    @staticmethod
    def redact_row(
        row: dict[str, Any],
        include_phone: bool = False,
    ) -> dict[str, Any]:
        safe = dict(row)
        if not include_phone and "phone" in safe:
            safe["phone"] = "[redacted]"
        for key, val in safe.items():
            if isinstance(val, str):
                safe[key] = _TOKEN_RE.sub("[REDACTED]", val)
                safe[key] = _BOT_TOKEN_RE.sub("[REDACTED]", safe[key])
        return safe

    @staticmethod
    def build_filename(
        report_type: str,
        ext: str = "csv",
    ) -> str:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M")
        safe_type = re.sub(r"[^a-zA-Z0-9_-]", "", report_type)
        return f"crm_{safe_type}_{ts}.{ext}"

    @staticmethod
    def _build_csv(
        columns: list[str],
        rows: list[dict[str, Any]],
    ) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([CRMExportService.sanitize_csv_value(row.get(col)) for col in columns])
        return output.getvalue()
