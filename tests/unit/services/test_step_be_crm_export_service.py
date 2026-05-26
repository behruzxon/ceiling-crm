"""Tests for Step BE — CRMExportService."""
from __future__ import annotations
from core.services.crm_export_service import CRMExportService

svc = CRMExportService

def _c(**kw):
    defaults = {"contact_id": 1, "username": "test", "first_name": "Aziz",
                "last_name": "K", "lead_status": "active", "temperature": "warm",
                "lead_score": 50, "source": "telegram_bot", "created_at": "2026-05-26",
                "phone": "+998901234567"}
    defaults.update(kw)
    return defaults


class TestContactsCSV:
    def test_empty_has_headers(self):
        csv = svc.export_contacts_csv([])
        assert "contact_id" in csv and "lead_status" in csv

    def test_exports_rows(self):
        csv = svc.export_contacts_csv([_c()])
        assert "Aziz" in csv

    def test_no_phone_default(self):
        csv = svc.export_contacts_csv([_c()])
        assert "+998" not in csv

    def test_phone_included(self):
        csv = svc.export_contacts_csv([_c()], include_phone=True)
        assert "+998" in csv or "phone" in csv

    def test_max_rows(self):
        contacts = [_c(contact_id=i) for i in range(10)]
        csv = svc.export_contacts_csv(contacts, max_rows=3)
        lines = csv.strip().split("\n")
        assert len(lines) <= 4  # header + 3 rows


class TestHotLeadsCSV:
    def test_only_hot(self):
        contacts = [_c(temperature="hot"), _c(temperature="cold")]
        csv = svc.export_hot_leads_csv(contacts)
        lines = csv.strip().split("\n")
        assert len(lines) == 2  # header + 1 hot

    def test_empty(self):
        csv = svc.export_hot_leads_csv([])
        assert "contact_id" in csv


class TestFunnelCSV:
    def test_exports(self):
        stages = [{"stage": "new", "count": 10, "conversion_from_previous": 1.0, "conversion_from_total": 1.0}]
        csv = svc.export_funnel_csv(stages)
        assert "new" in csv and "10" in csv


class TestTasksCSV:
    def test_exports(self):
        tasks = [{"task_id": 1, "contact_id": 1, "title": "Call", "task_type": "call",
                  "status": "todo", "priority": "high", "due_at": "", "completed_at": "",
                  "assigned_to": "", "source": "manual"}]
        csv = svc.export_tasks_csv(tasks)
        assert "Call" in csv


class TestCSVInjection:
    def test_equals_guarded(self):
        assert svc.sanitize_csv_value("=cmd()").startswith("'")

    def test_plus_guarded(self):
        assert svc.sanitize_csv_value("+cmd()").startswith("'")

    def test_minus_guarded(self):
        assert svc.sanitize_csv_value("-cmd()").startswith("'")

    def test_at_guarded(self):
        assert svc.sanitize_csv_value("@cmd()").startswith("'")

    def test_normal_not_guarded(self):
        assert svc.sanitize_csv_value("Aziz") == "Aziz"

    def test_none_empty(self):
        assert svc.sanitize_csv_value(None) == ""

    def test_number(self):
        assert svc.sanitize_csv_value(42) == "42"


class TestRedaction:
    def test_token_redacted(self):
        assert "sk-secret" not in svc.sanitize_csv_value("sk-secret123abc")

    def test_bot_token_redacted(self):
        assert "1234567890:" not in svc.sanitize_csv_value("1234567890:AABBCCDDEEFFaabbccddeeffgghhiijj")

    def test_row_phone_redacted(self):
        row = svc.redact_row({"phone": "+998901234567"}, include_phone=False)
        assert row["phone"] == "[redacted]"

    def test_row_phone_included(self):
        row = svc.redact_row({"phone": "+998901234567"}, include_phone=True)
        assert row["phone"] == "+998901234567"

    def test_row_token_redacted(self):
        row = svc.redact_row({"text": "sk-secret123"})
        assert "sk-secret" not in row["text"]


class TestFilename:
    def test_safe(self):
        fn = svc.build_filename("contacts", "csv")
        assert fn.startswith("crm_contacts_") and fn.endswith(".csv")

    def test_unsafe_chars_removed(self):
        fn = svc.build_filename("contacts/../hack", "csv")
        assert "/" not in fn and ".." not in fn

    def test_xlsx(self):
        fn = svc.build_filename("hot_leads", "xlsx")
        assert fn.endswith(".xlsx")


class TestDailySummary:
    def test_builds(self):
        data = svc.build_daily_summary_data({
            "total_contacts": 100, "hot_leads": 10,
            "unanswered_count": 5, "critical_count": 2,
            "missed": {"missed_lead_count": 3},
            "task_open": 8, "task_overdue": 2,
            "recommendations": ["Fix SLA"],
        })
        assert data["total_contacts"] == 100
        assert data["missed_leads"] == 3

    def test_empty(self):
        data = svc.build_daily_summary_data({})
        assert data["total_contacts"] == 0

    def test_title(self):
        data = svc.build_daily_summary_data({})
        assert "CRM" in data["title"]


class TestUnicode:
    def test_uzbek(self):
        csv = svc.export_contacts_csv([_c(first_name="O'tkirbek")])
        assert "O'tkirbek" in csv

    def test_russian(self):
        csv = svc.export_contacts_csv([_c(first_name="Александр")])
        assert "Александр" in csv
