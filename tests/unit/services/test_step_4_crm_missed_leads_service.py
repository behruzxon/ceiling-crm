"""Tests for Step 4 — Missed Leads Service."""

from __future__ import annotations

from core.schemas.crm_missed_leads import (
    MissedLeadDashboardResult,
    MissedLeadItem,
    MissedLeadRecommendation,
    MissedLeadSummary,
)
from core.services.crm_missed_leads_service import (
    EXCLUDED_STATUSES,
    SEVERITY_RULES,
    build_next_action,
    build_recommendations,
    build_summary,
    classify_severity,
    mask_phone,
    sanitize_preview,
)


class TestClassifySeverity:
    def test_hot_unanswered_critical(self):
        assert classify_severity("hot_unanswered", 15) == "critical"

    def test_operator_waiting_critical(self):
        assert classify_severity("operator_waiting", 10) == "critical"

    def test_phone_shared_critical(self):
        assert classify_severity("phone_shared_no_followup", 12) == "critical"

    def test_price_interest_high(self):
        assert classify_severity("price_interest_no_action", 20) == "high"

    def test_handoff_waiting_high(self):
        assert classify_severity("handoff_waiting_phone", 35) == "high"

    def test_stale_warm_high(self):
        assert classify_severity("stale_warm_lead", 1500) == "high"

    def test_catalog_medium(self):
        assert classify_severity("catalog_no_next_step", 0) == "medium"

    def test_unknown_low(self):
        assert classify_severity("unknown_reason", 100) == "low"

    def test_below_threshold_medium(self):
        assert classify_severity("hot_unanswered", 5) == "medium"


class TestMaskPhone:
    def test_normal(self):
        r = mask_phone("+998901234567")
        assert "****" in r
        assert "+998901234567" != r

    def test_none(self):
        assert mask_phone(None) is None

    def test_short(self):
        assert mask_phone("123") == "123"


class TestSanitizePreview:
    def test_normal(self):
        assert sanitize_preview("hello") == "hello"

    def test_token_redacted(self):
        r = sanitize_preview("key sk-abc12345678xyz")
        assert "sk-abc" not in r
        assert "[REDACTED]" in r

    def test_truncated(self):
        r = sanitize_preview("a" * 200)
        assert len(r) == 120

    def test_none(self):
        assert sanitize_preview(None) is None


class TestBuildNextAction:
    def test_hot(self):
        assert "javob" in build_next_action("hot_unanswered").lower()

    def test_operator(self):
        assert "operator" in build_next_action("operator_waiting").lower()

    def test_phone(self):
        r = build_next_action("phone_shared_no_followup")
        assert "telefon" in r.lower() or "bog'lan" in r.lower()

    def test_price(self):
        assert "narx" in build_next_action("price_interest_no_action").lower()

    def test_unknown(self):
        r = build_next_action("unknown")
        assert len(r) > 0


class TestBuildSummary:
    def test_empty(self):
        s = build_summary([])
        assert s.total == 0

    def test_counts(self):
        items = [
            MissedLeadItem(severity="critical", reason="hot_unanswered", minutes_waiting=15),
            MissedLeadItem(severity="high", reason="operator_waiting", minutes_waiting=10),
            MissedLeadItem(severity="medium", reason="catalog_no_next_step"),
        ]
        s = build_summary(items)
        assert s.total == 3
        assert s.critical == 1
        assert s.high == 1
        assert s.medium == 1
        assert s.hot_unanswered == 1
        assert s.operator_waiting == 1

    def test_avg_wait(self):
        items = [
            MissedLeadItem(minutes_waiting=10),
            MissedLeadItem(minutes_waiting=20),
        ]
        s = build_summary(items)
        assert s.avg_wait_minutes == 15
        assert s.oldest_wait_minutes == 20


class TestBuildRecommendations:
    def test_critical_rec(self):
        s = MissedLeadSummary(critical=3)
        recs = build_recommendations(s)
        assert any("critical" in r.text.lower() for r in recs)

    def test_operator_rec(self):
        s = MissedLeadSummary(operator_waiting=2)
        recs = build_recommendations(s)
        assert any("operator" in r.text.lower() for r in recs)

    def test_empty_no_recs(self):
        s = MissedLeadSummary()
        recs = build_recommendations(s)
        assert len(recs) == 0


class TestExcludedStatuses:
    def test_stopped(self):
        assert "stopped" in EXCLUDED_STATUSES

    def test_lost(self):
        assert "lost" in EXCLUDED_STATUSES

    def test_won(self):
        assert "won" in EXCLUDED_STATUSES


class TestSeverityRules:
    def test_rules_exist(self):
        assert len(SEVERITY_RULES) >= 8

    def test_hot_rule(self):
        assert "hot_unanswered" in SEVERITY_RULES


class TestSchemas:
    def test_item(self):
        i = MissedLeadItem(contact_id=1, reason="hot_unanswered")
        assert i.contact_id == 1

    def test_summary(self):
        s = MissedLeadSummary(total=5)
        assert s.total == 5

    def test_recommendation(self):
        r = MissedLeadRecommendation(text="test", priority="high")
        assert r.priority == "high"

    def test_dashboard_result(self):
        d = MissedLeadDashboardResult()
        assert d.summary.total == 0
