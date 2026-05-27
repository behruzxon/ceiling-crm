"""Tests for Step BB — CRMInboxAlertService."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.services.crm_inbox_alert_service import CRMInboxAlertService, InboxAlert

svc = CRMInboxAlertService
NOW = datetime(2026, 5, 26, 12, 0, 0, tzinfo=UTC)

def _c(*, status="active", temp="warm", last_msg_min=10, last_reply_min=None,
       intent=None, phone=None, cid=1, name="Test"):
    c: dict = {"id": cid, "first_name": name, "lead_status": status,
               "temperature": temp, "last_message_at": NOW - timedelta(minutes=last_msg_min),
               "metadata_json": {}}
    if last_reply_min is not None:
        c["last_operator_reply_at"] = NOW - timedelta(minutes=last_reply_min)
    if intent:
        c["last_intent"] = intent
        c["metadata_json"]["last_intent"] = intent
    if phone: c["phone"] = phone
    return c


class TestNoAlert:
    def test_stopped(self): assert svc.build_contact_alert(_c(status="stopped"), NOW) is None
    def test_lost(self): assert svc.build_contact_alert(_c(status="lost"), NOW) is None
    def test_won(self): assert svc.build_contact_alert(_c(status="won"), NOW) is None
    def test_answered(self): assert svc.build_contact_alert(_c(last_msg_min=10, last_reply_min=5), NOW) is None
    def test_no_msg(self): assert svc.build_contact_alert({"id": 1, "lead_status": "new", "temperature": "cold"}, NOW) is None


class TestSeverity:
    def test_info_4min(self):
        a = svc.build_contact_alert(_c(last_msg_min=4), NOW)
        assert a is not None and a.severity == "info"

    def test_warning_due_soon(self):
        a = svc.build_contact_alert(_c(last_msg_min=10), NOW)
        assert a is not None and a.severity == "warning"

    def test_danger_overdue(self):
        a = svc.build_contact_alert(_c(last_msg_min=20), NOW)
        assert a is not None and a.severity == "danger"

    def test_critical_sla(self):
        a = svc.build_contact_alert(_c(last_msg_min=35), NOW)
        assert a is not None and a.severity == "critical"

    def test_hot_critical(self):
        a = svc.build_contact_alert(_c(last_msg_min=12, temp="hot"), NOW)
        assert a is not None and a.severity == "critical" and a.alert_type == "hot_unanswered"

    def test_operator_critical(self):
        a = svc.build_contact_alert(_c(last_msg_min=6, intent="wants_operator"), NOW)
        assert a is not None and a.severity == "critical" and a.alert_type == "operator_needed"

    def test_phone_critical(self):
        a = svc.build_contact_alert(_c(last_msg_min=12, phone="+998"), NOW)
        assert a is not None and a.severity == "critical"


class TestAlertType:
    def test_critical_sla_type(self):
        a = svc.build_contact_alert(_c(last_msg_min=35), NOW)
        assert a.alert_type == "critical_sla"

    def test_overdue_type(self):
        a = svc.build_contact_alert(_c(last_msg_min=20), NOW)
        assert a.alert_type == "overdue"

    def test_due_soon_type(self):
        a = svc.build_contact_alert(_c(last_msg_min=10), NOW)
        assert a.alert_type == "due_soon"

    def test_new_message_type(self):
        a = svc.build_contact_alert(_c(last_msg_min=3), NOW)
        assert a.alert_type == "new_message"


class TestBuildAlerts:
    def test_empty(self):
        assert svc.build_alerts([], NOW) == []

    def test_filters_stopped(self):
        alerts = svc.build_alerts([_c(status="stopped"), _c(last_msg_min=10)], NOW)
        assert len(alerts) == 1

    def test_sorted_by_priority(self):
        contacts = [_c(last_msg_min=10, cid=1), _c(last_msg_min=35, cid=2)]
        alerts = svc.build_alerts(contacts, NOW)
        assert alerts[0].priority < alerts[1].priority

    def test_limit(self):
        contacts = [_c(last_msg_min=10+i, cid=i) for i in range(10)]
        assert len(svc.build_alerts(contacts, NOW, limit=3)) == 3

    def test_severity_filter(self):
        contacts = [_c(last_msg_min=35, cid=1), _c(last_msg_min=10, cid=2)]
        alerts = svc.build_alerts(contacts, NOW, severity="critical")
        assert all(a.severity == "critical" for a in alerts)

    def test_type_filter(self):
        contacts = [_c(last_msg_min=35, cid=1), _c(last_msg_min=12, temp="hot", cid=2)]
        alerts = svc.build_alerts(contacts, NOW, alert_type="hot_unanswered")
        assert all(a.alert_type == "hot_unanswered" for a in alerts)


class TestOverview:
    def test_counts(self):
        contacts = [_c(last_msg_min=35, cid=1), _c(last_msg_min=10, cid=2), _c(status="stopped", cid=3)]
        o = svc.get_alert_overview(contacts, NOW)
        assert o["total"] == 2
        assert o["critical"] >= 1

    def test_empty(self):
        o = svc.get_alert_overview([], NOW)
        assert o["total"] == 0

    def test_hot_count(self):
        contacts = [_c(last_msg_min=12, temp="hot", cid=1)]
        o = svc.get_alert_overview(contacts, NOW)
        assert o["hot_unanswered"] >= 1

    def test_operator_count(self):
        contacts = [_c(last_msg_min=6, intent="wants_operator", cid=1)]
        o = svc.get_alert_overview(contacts, NOW)
        assert o["operator_needed"] >= 1


class TestAlertContent:
    def test_title_contains_name(self):
        a = svc.build_contact_alert(_c(name="Aziz", last_msg_min=10), NOW)
        assert "Aziz" in a.title

    def test_message_contains_minutes(self):
        a = svc.build_contact_alert(_c(last_msg_min=15), NOW)
        assert "15" in a.message or "min" in a.message

    def test_unanswered_minutes(self):
        a = svc.build_contact_alert(_c(last_msg_min=20), NOW)
        assert a.unanswered_minutes == 20


class TestImmutability:
    def test_frozen(self):
        import pytest
        a = InboxAlert()
        with pytest.raises(AttributeError):
            a.severity = "x"  # type: ignore[misc]
