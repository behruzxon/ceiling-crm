"""Tests for Step AZ — CRMSLAService."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.services.crm_sla_service import CRMSLAService

svc = CRMSLAService
NOW = datetime(2026, 5, 26, 12, 0, 0, tzinfo=UTC)


def _c(
    *,
    status="active",
    temp="warm",
    last_msg_min=10,
    last_reply_min=None,
    last_bot_min=None,
    intent=None,
    phone=None,
):
    c = {
        "lead_status": status,
        "temperature": temp,
        "last_message_at": NOW - timedelta(minutes=last_msg_min),
    }
    if last_reply_min is not None:
        c["last_operator_reply_at"] = NOW - timedelta(minutes=last_reply_min)
    if last_bot_min is not None:
        c["last_bot_reply_at"] = NOW - timedelta(minutes=last_bot_min)
    if intent:
        c["last_intent"] = intent
    if phone:
        c["phone"] = phone
    return c


class TestUnansweredMinutes:
    def test_stopped(self):
        assert svc.compute_unanswered_minutes(_c(status="stopped"), NOW) is None

    def test_lost(self):
        assert svc.compute_unanswered_minutes(_c(status="lost"), NOW) is None

    def test_won(self):
        assert svc.compute_unanswered_minutes(_c(status="won"), NOW) is None

    def test_no_msg(self):
        assert svc.compute_unanswered_minutes({"lead_status": "new"}, NOW) is None

    def test_unanswered(self):
        assert svc.compute_unanswered_minutes(_c(last_msg_min=10), NOW) == 10

    def test_replied_operator(self):
        assert svc.compute_unanswered_minutes(_c(last_msg_min=10, last_reply_min=5), NOW) == 0

    def test_replied_bot(self):
        assert svc.compute_unanswered_minutes(_c(last_msg_min=10, last_bot_min=5), NOW) == 0


class TestSLAStatus:
    def test_ok_4min(self):
        assert svc.compute_sla_status(_c(last_msg_min=4), NOW) == "ok"

    def test_due_soon_10(self):
        assert svc.compute_sla_status(_c(last_msg_min=10), NOW) == "due_soon"

    def test_overdue_20(self):
        assert svc.compute_sla_status(_c(last_msg_min=20), NOW) == "overdue"

    def test_critical_35(self):
        assert svc.compute_sla_status(_c(last_msg_min=35), NOW) == "critical"

    def test_hot_critical_10(self):
        assert svc.compute_sla_status(_c(last_msg_min=10, temp="hot"), NOW) == "critical"

    def test_operator_critical_5(self):
        assert (
            svc.compute_sla_status(_c(last_msg_min=6, intent="wants_operator"), NOW) == "critical"
        )

    def test_phone_critical_10(self):
        assert svc.compute_sla_status(_c(last_msg_min=10, phone="+998"), NOW) == "critical"

    def test_stopped_ok(self):
        assert svc.compute_sla_status(_c(status="stopped"), NOW) == "ok"

    def test_replied_ok(self):
        assert svc.compute_sla_status(_c(last_msg_min=20, last_reply_min=5), NOW) == "ok"


class TestShouldNeedReply:
    def test_yes(self):
        assert svc.should_need_reply(_c(last_msg_min=10), NOW) is True

    def test_no_stopped(self):
        assert svc.should_need_reply(_c(status="stopped"), NOW) is False

    def test_no_replied(self):
        assert svc.should_need_reply(_c(last_msg_min=10, last_reply_min=5), NOW) is False


class TestOverview:
    def test_counts(self):
        contacts = [_c(last_msg_min=4), _c(last_msg_min=10), _c(last_msg_min=35)]
        o = svc.build_sla_overview(contacts, NOW)
        assert o["ok"] >= 1 and o["critical"] >= 1
