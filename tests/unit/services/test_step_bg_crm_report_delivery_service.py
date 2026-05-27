"""Tests for Step BG — CRMReportDeliveryService."""
from __future__ import annotations

from core.services.crm_report_delivery_service import (
    CRMReportDeliveryService,
    DeliveryPreviewResult,
)

svc = CRMReportDeliveryService


class TestValidationBlockers:
    def test_invalid_channel(self):
        r = svc.validate_delivery("fax")
        assert not r.allowed and any("invalid" in b for b in r.blockers)

    def test_report_not_found(self):
        r = svc.validate_delivery("log_only", report_exists=False)
        assert "report_not_found" in r.blockers

    def test_delivery_disabled(self):
        r = svc.validate_delivery("telegram", delivery_enabled=False)
        assert "delivery_disabled" in r.blockers

    def test_telegram_disabled(self):
        r = svc.validate_delivery("telegram", delivery_enabled=True, telegram_enabled=False)
        assert "telegram_disabled" in r.blockers

    def test_email_disabled(self):
        r = svc.validate_delivery("email", delivery_enabled=True, email_enabled=False)
        assert "email_disabled" in r.blockers

    def test_log_only_disabled(self):
        r = svc.validate_delivery("log_only", log_only_enabled=False)
        assert "log_only_disabled" in r.blockers

    def test_approval_required(self):
        r = svc.validate_delivery("telegram", delivery_enabled=True, telegram_enabled=True,
                                  approval_required=True, is_approved=False)
        assert "approval_required" in r.blockers

    def test_token_in_message(self):
        r = svc.validate_delivery("log_only", message_text="sk-secret123")
        assert "token_in_message" in r.blockers

    def test_bot_token_in_message(self):
        r = svc.validate_delivery("log_only",
                                  message_text="1234567890:AABBCCDDEEFFaabbccddeeffgghhiijj")
        assert "bot_token_in_message" in r.blockers


class TestValidationAllowed:
    def test_log_only_default(self):
        r = svc.validate_delivery("log_only")
        assert r.allowed

    def test_draft_allowed(self):
        r = svc.validate_delivery("draft")
        assert r.allowed

    def test_telegram_approved(self):
        r = svc.validate_delivery("telegram", delivery_enabled=True, telegram_enabled=True,
                                  approval_required=True, is_approved=True)
        assert r.allowed

    def test_email_approved(self):
        r = svc.validate_delivery("email", delivery_enabled=True, email_enabled=True,
                                  approval_required=True, is_approved=True)
        assert r.allowed

    def test_no_approval_needed(self):
        r = svc.validate_delivery("telegram", delivery_enabled=True, telegram_enabled=True,
                                  approval_required=False)
        assert r.allowed

    def test_preview_truncated(self):
        r = svc.validate_delivery("log_only", message_text="x" * 3000)
        assert len(r.message_preview) <= 2000


class TestRequiresApproval:
    def test_telegram_needs(self):
        r = svc.validate_delivery("telegram", delivery_enabled=True, telegram_enabled=True)
        assert r.requires_approval

    def test_log_only_no(self):
        r = svc.validate_delivery("log_only")
        assert not r.requires_approval

    def test_draft_no(self):
        r = svc.validate_delivery("draft")
        assert not r.requires_approval


class TestRecipient:
    def test_hash_stable(self):
        h1 = svc.hash_recipient("admin@test.com")
        h2 = svc.hash_recipient("admin@test.com")
        assert h1 == h2 and len(h1) == 16

    def test_redact(self):
        r = svc.redact_recipient("admin@test.com")
        assert "***" in r
        assert "admin@test.com" != r

    def test_redact_short(self):
        assert svc.redact_recipient("ab") == "***"

    def test_redact_empty(self):
        assert svc.redact_recipient("") == ""


class TestSanitize:
    def test_token(self):
        assert "sk-" not in svc.sanitize_message("sk-secret123")
    def test_bot_token(self):
        assert "1234567890:" not in svc.sanitize_message("1234567890:AABBCCDDEEFFaabbccddeeffgghhiijj")
    def test_clean(self):
        assert svc.sanitize_message("salom") == "salom"

class TestRedactError:
    def test_token(self):
        assert "sk-" not in svc.redact_error("sk-secret error")
    def test_truncate(self):
        assert len(svc.redact_error("x" * 1000)) <= 500


class TestBuildMessage:
    def test_basic(self):
        msg = svc.build_report_message({
            "report_date": "2026-05-26", "new_contacts": 10, "hot_leads": 5,
            "unanswered_count": 3, "critical_count": 1, "missed_leads": 0,
            "tasks_open": 8, "tasks_overdue": 2, "recommendations": ["Fix SLA"],
        })
        assert "Yangi mijozlar: 10" in msg
        assert "Hot leadlar: 5" in msg
        assert "Fix SLA" in msg

    def test_empty(self):
        msg = svc.build_report_message({})
        assert "CRM" in msg

    def test_no_token(self):
        msg = svc.build_report_message({"report_date": "sk-secret123"})
        assert "sk-secret" not in msg

    def test_max_length(self):
        msg = svc.build_report_message({"recommendations": ["x" * 3000]}, max_length=500)
        assert len(msg) <= 500


class TestModel:
    def test_importable(self):
        from infrastructure.database.models.crm_report_delivery_audit import (
            CRMReportDeliveryAuditModel,
        )
        assert CRMReportDeliveryAuditModel.__tablename__ == "crm_report_delivery_audit"

class TestMigration:
    def test_importable(self):
        import importlib
        mod = importlib.import_module(
            "infrastructure.database.migrations.versions."
            "20260526_1505_c4d5e6f7g8h9_add_crm_report_delivery_audit"
        )
        assert callable(mod.upgrade)

class TestSettings:
    def test_delivery_disabled(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_daily_report_delivery_enabled"].default is False
    def test_approval_required(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_daily_report_delivery_require_approval"].default is True
    def test_telegram_disabled(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_daily_report_telegram_enabled"].default is False
    def test_email_disabled(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_daily_report_email_enabled"].default is False

class TestImmutability:
    def test_frozen(self):
        import pytest
        r = DeliveryPreviewResult()
        with pytest.raises(AttributeError):
            r.allowed = True  # type: ignore[misc]
