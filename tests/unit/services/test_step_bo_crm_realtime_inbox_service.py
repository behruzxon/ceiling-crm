"""Tests for Step BO — CRMRealtimeInboxService."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.services.crm_realtime_inbox_service import CRMRealtimeInboxService, LiveInboxSummary

svc = CRMRealtimeInboxService


class TestEmptySummary:
    def test_empty_contacts(self):
        s = svc.build_live_summary([])
        assert s.critical_count == 0
        assert s.danger_count == 0
        assert s.unanswered_count == 0
        assert s.latest_alerts == []
        assert s.generated_at != ""

    def test_empty_alerts(self):
        s = svc.build_live_summary([])
        assert len(s.latest_alerts) == 0


class TestSummaryCounts:
    def _contact(self, **kw):
        base = {
            "id": 1,
            "contact_name": "Test",
            "lead_status": "active",
            "temperature": "warm",
            "last_message_direction": "inbound",
            "last_message_at": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
            "last_intent": None,
            "metadata_json": None,
        }
        base.update(kw)
        return base

    def test_unanswered_count(self):
        contacts = [self._contact(), self._contact(id=2)]
        s = svc.build_live_summary(contacts)
        assert s.unanswered_count == 2

    def test_stopped_not_counted(self):
        contacts = [self._contact(lead_status="stopped")]
        s = svc.build_live_summary(contacts)
        assert s.unanswered_count == 0

    def test_outbound_not_unanswered(self):
        contacts = [self._contact(last_message_direction="outbound")]
        s = svc.build_live_summary(contacts)
        assert s.unanswered_count == 0


class TestLatestAlerts:
    def test_max_alerts_limit(self):
        alerts_mock = [
            type(
                "A",
                (),
                {
                    "contact_id": i,
                    "contact_name": "t",
                    "alert_type": "x",
                    "severity": "info",
                    "title": "t",
                    "message": "m",
                    "unanswered_minutes": 0,
                    "priority": 7,
                },
            )()
            for i in range(10)
        ]
        result = svc.serialize_alerts(alerts_mock, max_alerts=3)
        assert len(result) == 3

    def test_alert_fields(self):
        alert = type(
            "A",
            (),
            {
                "contact_id": 1,
                "contact_name": "Ali",
                "alert_type": "hot_unanswered",
                "severity": "critical",
                "title": "Hot lead!",
                "message": "Yordam kerak",
                "unanswered_minutes": 15,
                "priority": 2,
            },
        )()
        result = svc.serialize_alerts([alert])
        assert result[0]["contact_id"] == 1
        assert result[0]["severity"] == "critical"
        assert result[0]["unanswered_minutes"] == 15

    def test_token_redacted_in_name(self):
        alert = type(
            "A",
            (),
            {
                "contact_id": 1,
                "contact_name": "sk-secret123",
                "alert_type": "x",
                "severity": "info",
                "title": "t",
                "message": "m",
                "unanswered_minutes": 0,
                "priority": 7,
            },
        )()
        result = svc.serialize_alerts([alert])
        assert "sk-" not in result[0]["contact_name"]

    def test_phone_redacted_in_message(self):
        alert = type(
            "A",
            (),
            {
                "contact_id": 1,
                "contact_name": "t",
                "alert_type": "x",
                "severity": "info",
                "title": "t",
                "message": "+998901234567 yozdi",
                "unanswered_minutes": 0,
                "priority": 7,
            },
        )()
        result = svc.serialize_alerts([alert])
        assert "+998" not in result[0]["message"]

    def test_message_truncated(self):
        alert = type(
            "A",
            (),
            {
                "contact_id": 1,
                "contact_name": "t",
                "alert_type": "x",
                "severity": "info",
                "title": "t",
                "message": "x" * 500,
                "unanswered_minutes": 0,
                "priority": 7,
            },
        )()
        result = svc.serialize_alerts([alert])
        assert len(result[0]["message"]) <= 300


class TestDiffSummary:
    def test_first_call_changed(self):
        s = LiveInboxSummary(critical_count=2)
        d = svc.diff_summary(None, s)
        assert d["changed"] is True
        assert d["pulse"] is True

    def test_no_change(self):
        prev = {
            "critical_count": 1,
            "danger_count": 0,
            "unanswered_count": 0,
            "hot_unanswered_count": 0,
            "operator_needed_count": 0,
        }
        s = LiveInboxSummary(critical_count=1)
        d = svc.diff_summary(prev, s)
        assert d["changed"] is False
        assert d["pulse"] is False

    def test_critical_increase_pulse(self):
        prev = {
            "critical_count": 1,
            "danger_count": 0,
            "unanswered_count": 0,
            "hot_unanswered_count": 0,
            "operator_needed_count": 0,
        }
        s = LiveInboxSummary(critical_count=3)
        d = svc.diff_summary(prev, s)
        assert d["pulse"] is True

    def test_critical_decrease_no_pulse(self):
        prev = {
            "critical_count": 5,
            "danger_count": 0,
            "unanswered_count": 0,
            "hot_unanswered_count": 0,
            "operator_needed_count": 0,
        }
        s = LiveInboxSummary(critical_count=2)
        d = svc.diff_summary(prev, s)
        assert d["pulse"] is False
        assert d["changed"] is True


class TestShouldPulse:
    def test_first_with_critical(self):
        s = LiveInboxSummary(critical_count=1)
        assert svc.should_pulse(None, s) is True

    def test_first_no_critical(self):
        s = LiveInboxSummary(critical_count=0)
        assert svc.should_pulse(None, s) is False

    def test_increase(self):
        assert svc.should_pulse({"critical_count": 0}, LiveInboxSummary(critical_count=2)) is True

    def test_same(self):
        assert svc.should_pulse({"critical_count": 2}, LiveInboxSummary(critical_count=2)) is False


class TestSafeText:
    def test_empty(self):
        assert svc._safe_text("") == ""

    def test_token(self):
        assert "sk-" not in svc._safe_text("sk-secret123 test")

    def test_phone(self):
        assert "+998" not in svc._safe_text("+998901234567")

    def test_truncated(self):
        assert len(svc._safe_text("x" * 500)) <= 300


class TestImmutability:
    def test_frozen(self):
        import pytest

        s = LiveInboxSummary()
        with pytest.raises(AttributeError):
            s.critical_count = 5  # type: ignore[misc]
