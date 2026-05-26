"""Tests for Step BD — CRMDashboardAnalyticsService."""
from __future__ import annotations
from datetime import UTC, datetime, timedelta
from core.schemas.crm_dashboard_analytics import CRMMissedLeadMetrics
from core.services.crm_dashboard_analytics_service import CRMDashboardAnalyticsService

svc = CRMDashboardAnalyticsService
NOW = datetime(2026, 5, 26, 12, 0, 0, tzinfo=UTC)

def _c(*, status="active", temp="warm", last_msg_min=10, intent=None, objection=None,
       phone=None, district=None, last_reply_min=None):
    c: dict = {"id": 1, "lead_status": status, "temperature": temp,
               "last_message_at": NOW - timedelta(minutes=last_msg_min),
               "metadata_json": {}}
    if intent: c["metadata_json"]["last_intent"] = intent
    if objection: c["metadata_json"]["objection_type"] = objection
    if phone: c["phone"] = phone
    if district: c["district"] = district
    if last_reply_min is not None:
        c["last_operator_reply_at"] = NOW - timedelta(minutes=last_reply_min)
    return c


class TestEmpty:
    def test_empty_safe(self):
        d = svc.build_dashboard([], now=NOW)
        assert d.total_contacts == 0 and d.hot_leads == 0

    def test_generated_at(self):
        assert svc.build_dashboard([], now=NOW).generated_at != ""


class TestTemperature:
    def test_hot(self):
        d = svc.build_dashboard([_c(temp="hot")], now=NOW)
        assert d.hot_leads == 1

    def test_warm(self):
        d = svc.build_dashboard([_c(temp="warm")], now=NOW)
        assert d.warm_leads == 1

    def test_cold(self):
        d = svc.build_dashboard([_c(temp="cold")], now=NOW)
        assert d.cold_leads == 1


class TestStatuses:
    def test_stopped(self):
        d = svc.build_dashboard([_c(status="stopped")], now=NOW)
        assert d.stopped == 1

    def test_won(self):
        d = svc.build_dashboard([_c(status="won")], now=NOW)
        assert d.won == 1

    def test_lost(self):
        d = svc.build_dashboard([_c(status="lost")], now=NOW)
        assert d.lost == 1


class TestSLA:
    def test_unanswered(self):
        d = svc.build_dashboard([_c(last_msg_min=10)], now=NOW)
        assert d.unanswered_count >= 1

    def test_critical(self):
        d = svc.build_dashboard([_c(last_msg_min=35)], now=NOW)
        assert d.critical_count >= 1

    def test_overdue(self):
        d = svc.build_dashboard([_c(last_msg_min=20)], now=NOW)
        assert d.overdue_count >= 1

    def test_answered_not_unanswered(self):
        d = svc.build_dashboard([_c(last_msg_min=10, last_reply_min=5)], now=NOW)
        assert d.unanswered_count == 0


class TestFunnel:
    def test_has_stages(self):
        d = svc.build_dashboard([_c(status="new")], now=NOW)
        assert len(d.funnel) >= 5

    def test_new_count(self):
        d = svc.build_dashboard([_c(status="new"), _c(status="new")], now=NOW)
        new_stage = next((s for s in d.funnel if s.name == "new"), None)
        assert new_stage and new_stage.count == 2

    def test_conversion_rate(self):
        d = svc.build_dashboard([_c(status="new")] * 10 + [_c(status="won")] * 2, now=NOW)
        won_stage = next((s for s in d.funnel if s.name == "won"), None)
        assert won_stage and won_stage.conversion_from_total > 0


class TestMissedLeads:
    def test_missed_hot(self):
        d = svc.build_dashboard([_c(temp="hot", last_msg_min=35)], now=NOW)
        assert d.missed.missed_hot_leads >= 1

    def test_missed_operator(self):
        d = svc.build_dashboard([_c(intent="wants_operator", last_msg_min=20)], now=NOW)
        assert d.missed.missed_operator_requests >= 1

    def test_missed_phone(self):
        d = svc.build_dashboard([_c(phone="+998", last_msg_min=35)], now=NOW)
        assert d.missed.missed_phone_shared >= 1

    def test_no_missed_answered(self):
        d = svc.build_dashboard([_c(temp="hot", last_msg_min=35, last_reply_min=5)], now=NOW)
        assert d.missed.missed_hot_leads == 0

    def test_total_missed(self):
        d = svc.build_dashboard([_c(temp="hot", last_msg_min=35)], now=NOW)
        assert d.missed.missed_lead_count >= 1


class TestIntentsObjections:
    def test_intents(self):
        d = svc.build_dashboard([_c(intent="wants_price"), _c(intent="wants_price")], now=NOW)
        assert d.top_intents.get("wants_price") == 2

    def test_objections(self):
        d = svc.build_dashboard([_c(objection="price")], now=NOW)
        assert d.top_objections.get("price") == 1

    def test_locations(self):
        d = svc.build_dashboard([_c(district="qarshi"), _c(district="qarshi")], now=NOW)
        assert d.top_locations.get("qarshi") == 2


class TestTaskMetrics:
    def test_open(self):
        d = svc.build_dashboard([], tasks=[{"status": "todo"}, {"status": "in_progress"}], now=NOW)
        assert d.task_open == 2

    def test_completed(self):
        d = svc.build_dashboard([], tasks=[{"status": "done"}], now=NOW)
        assert d.task_completed == 1

    def test_rate(self):
        d = svc.build_dashboard([], tasks=[{"status": "done"}, {"status": "todo"}], now=NOW)
        assert d.task_completion_rate == 0.5

    def test_empty_tasks(self):
        d = svc.build_dashboard([], tasks=[], now=NOW)
        assert d.task_completion_rate == 0.0


class TestRecommendations:
    def test_critical_high(self):
        contacts = [_c(last_msg_min=35)] * 6
        d = svc.build_dashboard(contacts, now=NOW)
        assert any("critical" in r.lower() or "sla" in r.lower() for r in d.recommendations)

    def test_missed_hot(self):
        d = svc.build_dashboard([_c(temp="hot", last_msg_min=35)], now=NOW)
        assert any("hot" in r.lower() or "missed" in r.lower() for r in d.recommendations)

    def test_price_objection(self):
        contacts = [_c(objection="price")] * 6
        d = svc.build_dashboard(contacts, now=NOW)
        assert any("qimmat" in r.lower() or "arzon" in r.lower() for r in d.recommendations)

    def test_no_recs_clean(self):
        d = svc.build_dashboard([_c(last_msg_min=3, last_reply_min=1)], now=NOW)
        assert isinstance(d.recommendations, list)


class TestImmutability:
    def test_frozen(self):
        import pytest
        d = svc.build_dashboard([], now=NOW)
        with pytest.raises(AttributeError):
            d.total_contacts = 5  # type: ignore[misc]

    def test_missed_frozen(self):
        import pytest
        m = CRMMissedLeadMetrics()
        with pytest.raises(AttributeError):
            m.missed_hot_leads = 1  # type: ignore[misc]


class TestNoSecrets:
    def test_clean(self):
        from dataclasses import asdict
        d = svc.build_dashboard([], now=NOW)
        text = str(asdict(d))
        assert "sk-" not in text and "+998" not in text
