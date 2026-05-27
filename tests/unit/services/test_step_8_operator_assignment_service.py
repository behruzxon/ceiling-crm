"""Tests for operator assignment service — Step 8."""

from __future__ import annotations

from core.services.crm_operator_handoff_service import (
    VALID_STATUSES,
    HandoffResult,
    QueueSummary,
    build_user_message,
    calculate_priority,
    mask_phone,
    sanitize_message_preview,
    sanitize_metadata,
)


class TestValidStatuses:
    def test_assigned_in_statuses(self) -> None:
        assert "assigned" in VALID_STATUSES

    def test_open_in_statuses(self) -> None:
        assert "open" in VALID_STATUSES

    def test_waiting_phone_in_statuses(self) -> None:
        assert "waiting_phone" in VALID_STATUSES

    def test_contacted_in_statuses(self) -> None:
        assert "contacted" in VALID_STATUSES

    def test_resolved_in_statuses(self) -> None:
        assert "resolved" in VALID_STATUSES

    def test_cancelled_in_statuses(self) -> None:
        assert "cancelled" in VALID_STATUSES

    def test_expired_in_statuses(self) -> None:
        assert "expired" in VALID_STATUSES


class TestPriorityCalculation:
    def test_urgent_high_score(self) -> None:
        assert calculate_priority(lead_score=90) == "urgent"

    def test_urgent_complaint(self) -> None:
        assert calculate_priority(reason="complaint") == "urgent"

    def test_urgent_repeated_high(self) -> None:
        assert calculate_priority(lead_score=65, is_repeated=True) == "urgent"

    def test_high_phone_measurement(self) -> None:
        assert calculate_priority(has_phone=True, reason="measurement_request") == "high"

    def test_high_measurement_no_phone(self) -> None:
        assert calculate_priority(reason="measurement_request") == "high"

    def test_high_phone_score(self) -> None:
        assert calculate_priority(has_phone=True, lead_score=45) == "high"

    def test_normal_default(self) -> None:
        assert calculate_priority() == "normal"

    def test_normal_low_score(self) -> None:
        assert calculate_priority(lead_score=10) == "normal"


class TestMaskPhone:
    def test_mask_full(self) -> None:
        assert mask_phone("+998901234567") == "+998****67"

    def test_mask_none(self) -> None:
        assert mask_phone(None) is None

    def test_mask_short(self) -> None:
        assert mask_phone("123") == "123"

    def test_mask_empty(self) -> None:
        result = mask_phone("")
        assert result == "" or result is None


class TestSanitize:
    def test_sanitize_token(self) -> None:
        result = sanitize_message_preview("key sk-abcdefghijk12345")
        assert "sk-abcdefghijk12345" not in (result or "")

    def test_sanitize_none(self) -> None:
        assert sanitize_message_preview(None) is None

    def test_sanitize_truncate(self) -> None:
        result = sanitize_message_preview("x" * 500)
        assert len(result or "") <= 200

    def test_sanitize_metadata_none(self) -> None:
        assert sanitize_metadata(None) is None

    def test_sanitize_metadata_token(self) -> None:
        result = sanitize_metadata({"key": "sk-abcdefghijk12345"})
        assert result is not None
        assert "sk-abcdefghijk12345" not in str(result)


class TestQueueSummary:
    def test_defaults(self) -> None:
        s = QueueSummary()
        assert s.total_open == 0
        assert s.total_assigned == 0
        assert s.total_waiting_phone == 0
        assert s.total_urgent == 0
        assert s.total_high == 0

    def test_custom_values(self) -> None:
        s = QueueSummary(total_open=5, total_assigned=3)
        assert s.total_open == 5
        assert s.total_assigned == 3


class TestHandoffResult:
    def test_default(self) -> None:
        r = HandoffResult()
        assert r.status == "open"
        assert r.priority == "normal"

    def test_assigned_status(self) -> None:
        r = HandoffResult(status="assigned")
        assert r.status == "assigned"


class TestBuildUserMessage:
    def test_has_phone(self) -> None:
        msg = build_user_message(has_phone=True)
        assert "qabul qilindi" in msg

    def test_no_phone(self) -> None:
        msg = build_user_message(has_phone=False)
        assert "telefon" in msg.lower()

    def test_duplicate(self) -> None:
        msg = build_user_message(has_phone=True, is_duplicate=True)
        assert "yuborilgan" in msg
