"""Tests for Step BF — CRMDailyReportService."""
from __future__ import annotations
from datetime import date
from core.services.crm_daily_report_service import CRMDailyReportService, CRMDailyReportSnapshot

svc = CRMDailyReportService

def _analytics(**kw):
    defaults = {"total_contacts": 100, "new_contacts": 10, "hot_leads": 5,
                "unanswered_count": 8, "critical_count": 2, "won": 3, "lost": 2,
                "missed": {"missed_lead_count": 1}, "task_open": 5, "task_overdue": 1,
                "task_completed": 10, "top_intents": {"wants_price": 20},
                "top_objections": {"price": 5}, "top_locations": {"qarshi": 15},
                "recommendations": ["Fix SLA"]}
    defaults.update(kw)
    return defaults


class TestTitle:
    def test_contains_date(self):
        t = svc.build_report_title(date(2026, 5, 26))
        assert "2026-05-26" in t

    def test_contains_crm(self):
        assert "CRM" in svc.build_report_title()


class TestSummary:
    def test_from_analytics(self):
        r = svc.build_summary_from_analytics(_analytics())
        assert r.total_contacts == 100
        assert r.hot_leads == 5
        assert r.unanswered_count == 8
        assert r.missed_leads == 1

    def test_empty_analytics(self):
        r = svc.build_summary_from_analytics({})
        assert r.total_contacts == 0

    def test_report_date(self):
        r = svc.build_summary_from_analytics(_analytics(), date(2026, 5, 26))
        assert r.report_date == "2026-05-26"

    def test_generated_at(self):
        r = svc.build_summary_from_analytics(_analytics())
        assert r.generated_at != ""

    def test_intents(self):
        r = svc.build_summary_from_analytics(_analytics())
        assert r.top_intents.get("wants_price") == 20

    def test_objections(self):
        r = svc.build_summary_from_analytics(_analytics())
        assert r.top_objections.get("price") == 5

    def test_locations(self):
        r = svc.build_summary_from_analytics(_analytics())
        assert r.top_locations.get("qarshi") == 15

    def test_recommendations(self):
        r = svc.build_summary_from_analytics(_analytics())
        assert "Fix SLA" in r.recommendations

    def test_tasks(self):
        r = svc.build_summary_from_analytics(_analytics())
        assert r.tasks_open == 5 and r.tasks_overdue == 1

    def test_won_lost(self):
        r = svc.build_summary_from_analytics(_analytics())
        assert r.won_count == 3 and r.lost_count == 2


class TestStatus:
    def test_ok(self):
        r = svc.build_summary_from_analytics(_analytics(critical_count=1))
        assert svc.evaluate_report_status(r) == "ok"

    def test_needs_attention_critical(self):
        r = svc.build_summary_from_analytics(_analytics(critical_count=6))
        assert svc.evaluate_report_status(r) == "needs_attention"

    def test_needs_attention_missed(self):
        r = svc.build_summary_from_analytics(_analytics(missed={"missed_lead_count": 4}))
        assert svc.evaluate_report_status(r) == "needs_attention"


class TestSanitize:
    def test_token_removed(self):
        data = svc.sanitize_report_payload({"text": "sk-secret123"})
        assert "sk-secret" not in str(data)

    def test_clean(self):
        data = svc.sanitize_report_payload({"text": "hello"})
        assert data["text"] == "hello"

    def test_error_redacted(self):
        assert "sk-" not in svc.redact_error("sk-secret123 error")

    def test_error_truncated(self):
        assert len(svc.redact_error("x" * 1000)) <= 500


class TestModel:
    def test_importable(self):
        from infrastructure.database.models.crm_daily_report import CRMDailyReportModel
        assert CRMDailyReportModel.__tablename__ == "crm_daily_reports"

class TestMigration:
    def test_importable(self):
        import importlib
        mod = importlib.import_module(
            "infrastructure.database.migrations.versions."
            "20260526_1500_b3c4d5e6f7g8_add_crm_daily_reports"
        )
        assert callable(mod.upgrade)

class TestSchedulerJob:
    def test_importable(self):
        from apps.scheduler.jobs.crm_daily_report_jobs import register_crm_daily_report_jobs
        assert callable(register_crm_daily_report_jobs)

    def test_job_registers(self):
        from unittest.mock import MagicMock
        from apps.scheduler.jobs.crm_daily_report_jobs import register_crm_daily_report_jobs
        scheduler = MagicMock()
        register_crm_daily_report_jobs(scheduler)
        scheduler.add_job.assert_called_once()

class TestSettings:
    def test_default_false(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_daily_report_enabled"].default is False

    def test_delivery_disabled(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_daily_report_delivery_mode"].default == "disabled"

class TestImmutability:
    def test_frozen(self):
        import pytest
        r = CRMDailyReportSnapshot()
        with pytest.raises(AttributeError):
            r.title = "x"  # type: ignore[misc]

class TestSchedulerSmoke:
    def test_scheduler_imports(self):
        import apps.scheduler.main
        assert apps.scheduler.main is not None
