"""Tests for Step CL — CRM Operator Handoff Service."""
from __future__ import annotations

from core.services.crm_operator_handoff_service import (
    DEFAULT_DEDUP_MINUTES,
    DEFAULT_EXPIRE_HOURS,
    DEFAULT_URGENT_SCORE_THRESHOLD,
    VALID_PRIORITIES,
    VALID_SOURCES,
    VALID_STATUSES,
    HandoffResult,
    QueueSummary,
    build_user_message,
    calculate_priority,
    mask_phone,
    sanitize_message_preview,
    sanitize_metadata,
)


class TestHandoffResult:
    def test_default_status_open(self):
        r = HandoffResult()
        assert r.status == "open"

    def test_default_priority_normal(self):
        r = HandoffResult()
        assert r.priority == "normal"

    def test_not_duplicate_by_default(self):
        r = HandoffResult()
        assert r.is_duplicate is False

    def test_custom_values(self):
        r = HandoffResult(
            handoff_id=1, status="assigned",
            priority="urgent", is_duplicate=True,
        )
        assert r.handoff_id == 1
        assert r.status == "assigned"

    def test_frozen(self):
        import pytest
        r = HandoffResult()
        with pytest.raises(AttributeError):
            r.status = "x"


class TestValidConstants:
    def test_statuses(self):
        assert "open" in VALID_STATUSES
        assert "waiting_phone" in VALID_STATUSES
        assert "assigned" in VALID_STATUSES
        assert "contacted" in VALID_STATUSES
        assert "resolved" in VALID_STATUSES
        assert "cancelled" in VALID_STATUSES
        assert "expired" in VALID_STATUSES

    def test_priorities(self):
        assert "low" in VALID_PRIORITIES
        assert "normal" in VALID_PRIORITIES
        assert "high" in VALID_PRIORITIES
        assert "urgent" in VALID_PRIORITIES

    def test_sources(self):
        assert "ai_button" in VALID_SOURCES
        assert "operator_button" in VALID_SOURCES
        assert "text_intent" in VALID_SOURCES

    def test_dedup_minutes(self):
        assert DEFAULT_DEDUP_MINUTES == 30

    def test_expire_hours(self):
        assert DEFAULT_EXPIRE_HOURS == 24

    def test_urgent_threshold(self):
        assert DEFAULT_URGENT_SCORE_THRESHOLD == 80


class TestMaskPhone:
    def test_normal_phone(self):
        result = mask_phone("+998901234567")
        assert "****" in result
        assert "+998901234567" != result

    def test_short_phone(self):
        result = mask_phone("123")
        assert result == "123"

    def test_none(self):
        assert mask_phone(None) is None

    def test_empty(self):
        assert mask_phone("") == ""

    def test_preserves_prefix_suffix(self):
        result = mask_phone("+998901234567")
        assert result.startswith("+998")
        assert result.endswith("67")


class TestSanitizePreview:
    def test_normal_text(self):
        result = sanitize_message_preview("narx qancha")
        assert result == "narx qancha"

    def test_truncates(self):
        long = "a" * 300
        result = sanitize_message_preview(long)
        assert len(result) == 200

    def test_redacts_token(self):
        result = sanitize_message_preview("key is sk-abc12345678xyz")
        assert "sk-abc" not in result
        assert "[REDACTED]" in result

    def test_redacts_bearer(self):
        result = sanitize_message_preview("auth: Bearer eyJhbGciOiJIUz")
        assert "eyJ" not in result
        assert "[REDACTED]" in result

    def test_none(self):
        assert sanitize_message_preview(None) is None

    def test_empty(self):
        assert sanitize_message_preview("") is None


class TestSanitizeMetadata:
    def test_normal_dict(self):
        result = sanitize_metadata({"key": "value"})
        assert result == {"key": "value"}

    def test_redacts_token_in_values(self):
        result = sanitize_metadata({"token": "sk-abc12345678xyz"})
        assert "sk-abc" not in result["token"]

    def test_none(self):
        assert sanitize_metadata(None) is None

    def test_empty(self):
        assert sanitize_metadata({}) is None

    def test_preserves_non_string(self):
        result = sanitize_metadata({"count": 5})
        assert result["count"] == 5


class TestCalculatePriority:
    def test_high_score_urgent(self):
        assert calculate_priority(lead_score=85) == "urgent"

    def test_complaint_urgent(self):
        assert calculate_priority(reason="complaint") == "urgent"

    def test_angry_urgent(self):
        assert calculate_priority(reason="angry_objection") == "urgent"

    def test_repeated_high_score_urgent(self):
        result = calculate_priority(
            lead_score=65, is_repeated=True,
        )
        assert result == "urgent"

    def test_phone_price_high(self):
        result = calculate_priority(
            has_phone=True, reason="price_question",
        )
        assert result == "high"

    def test_measurement_high(self):
        assert calculate_priority(reason="measurement_request") == "high"

    def test_phone_score40_high(self):
        result = calculate_priority(has_phone=True, lead_score=45)
        assert result == "high"

    def test_default_normal(self):
        assert calculate_priority() == "normal"

    def test_low_score_normal(self):
        assert calculate_priority(lead_score=10) == "normal"

    def test_custom_threshold(self):
        result = calculate_priority(
            lead_score=50, urgent_threshold=50,
        )
        assert result == "urgent"


class TestBuildUserMessage:
    def test_phone_missing(self):
        msg = build_user_message(has_phone=False)
        assert "telefon" in msg.lower()
        assert "so'rovingiz qabul qilindi" in msg

    def test_phone_exists(self):
        msg = build_user_message(has_phone=True)
        assert "ko'rib chiqadi" in msg

    def test_duplicate(self):
        msg = build_user_message(has_phone=True, is_duplicate=True)
        assert "yuborilgan" in msg

    def test_no_fake_eta_missing(self):
        msg = build_user_message(has_phone=False)
        assert "hozir" not in msg.lower()
        assert "darhol" not in msg.lower()
        assert "bugun" not in msg.lower()

    def test_no_fake_eta_exists(self):
        msg = build_user_message(has_phone=True)
        assert "hozir" not in msg.lower()
        assert "darhol" not in msg.lower()

    def test_no_fake_eta_duplicate(self):
        msg = build_user_message(has_phone=True, is_duplicate=True)
        assert "hozir" not in msg.lower()

    def test_no_same_day_promise(self):
        for has_phone in (True, False):
            msg = build_user_message(has_phone=has_phone)
            assert "bugun qilamiz" not in msg.lower()
            assert "bugun keladi" not in msg.lower()


class TestQueueSummary:
    def test_defaults(self):
        s = QueueSummary()
        assert s.total_open == 0
        assert s.total_waiting_phone == 0
        assert s.total_assigned == 0
        assert s.total_urgent == 0
        assert s.total_high == 0

    def test_custom_values(self):
        s = QueueSummary(total_open=5, total_urgent=2)
        assert s.total_open == 5
        assert s.total_urgent == 2


class TestDBModel:
    def test_model_importable(self):
        from infrastructure.database.models.crm_operator_handoff import (
            CRMOperatorHandoffModel,
        )
        assert CRMOperatorHandoffModel is not None

    def test_table_name(self):
        from infrastructure.database.models.crm_operator_handoff import (
            CRMOperatorHandoffModel,
        )
        assert CRMOperatorHandoffModel.__tablename__ == "crm_operator_handoff_requests"

    def test_has_indexes(self):
        from infrastructure.database.models.crm_operator_handoff import (
            CRMOperatorHandoffModel,
        )
        idx_names = [idx.name for idx in CRMOperatorHandoffModel.__table__.indexes]
        assert "ix_handoff_contact_status" in idx_names
        assert "ix_handoff_tg_user_status" in idx_names


class TestConfigFlags:
    def test_queue_enabled_default(self):
        from shared.config.settings import BusinessSettings
        f = BusinessSettings.model_fields
        assert f["crm_operator_handoff_queue_enabled"].default is True

    def test_admin_notify_disabled(self):
        from shared.config.settings import BusinessSettings
        f = BusinessSettings.model_fields
        assert f["crm_operator_handoff_admin_notify_enabled"].default is False

    def test_require_phone_default(self):
        from shared.config.settings import BusinessSettings
        f = BusinessSettings.model_fields
        assert f["crm_operator_handoff_require_phone"].default is True

    def test_dedup_minutes_default(self):
        from shared.config.settings import BusinessSettings
        f = BusinessSettings.model_fields
        assert f["crm_operator_handoff_dedup_minutes"].default == 30

    def test_expire_hours_default(self):
        from shared.config.settings import BusinessSettings
        f = BusinessSettings.model_fields
        assert f["crm_operator_handoff_expire_hours"].default == 24

    def test_urgent_threshold_default(self):
        from shared.config.settings import BusinessSettings
        f = BusinessSettings.model_fields
        assert f["crm_operator_handoff_urgent_score_threshold"].default == 80
