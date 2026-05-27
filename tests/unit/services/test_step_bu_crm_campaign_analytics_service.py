"""Tests for Step BU — CRMCampaignAnalyticsService."""

from __future__ import annotations

from core.services.crm_campaign_analytics_service import CRMCampaignAnalyticsService

svc = CRMCampaignAnalyticsService


def _attempt(status="sent", **kw):
    base = {
        "campaign_id": 1,
        "contact_id": 1,
        "status": status,
        "blocked_reason": None,
        "error_message": None,
        "sent_at": "2026-05-26T10:00:00",
        "metadata_json": {},
    }
    base.update(kw)
    return base


class TestEmpty:
    def test_empty_delivery(self):
        m = svc.get_delivery_metrics([])
        assert m.total_attempts == 0
        assert m.success_rate == 0.0

    def test_empty_blocked(self):
        assert svc.get_blocked_reason_metrics([]) == []

    def test_empty_failures(self):
        assert svc.get_failure_reason_metrics([]) == []

    def test_empty_canary(self):
        m = svc.get_canary_metrics([])
        assert m.canary_sent == 0

    def test_empty_replies(self):
        m = svc.get_reply_metrics([], [])
        assert m.reply_count == 0

    def test_empty_status_changes(self):
        m = svc.get_status_change_metrics([], [])
        assert m.status_changes == 0

    def test_empty_analytics(self):
        a = svc.build_campaign_analytics(1, [])
        assert a.campaign_id == 1
        assert a.generated_at != ""

    def test_empty_dashboard(self):
        d = svc.build_dashboard_summary([], [])
        assert d.total_campaigns == 0


class TestDeliveryMetrics:
    def test_total(self):
        m = svc.get_delivery_metrics([_attempt(), _attempt("failed")])
        assert m.total_attempts == 2

    def test_sent(self):
        m = svc.get_delivery_metrics([_attempt("sent"), _attempt("sent")])
        assert m.sent == 2

    def test_failed(self):
        m = svc.get_delivery_metrics([_attempt("failed")])
        assert m.failed == 1

    def test_blocked(self):
        m = svc.get_delivery_metrics([_attempt("blocked")])
        assert m.blocked == 1

    def test_skipped(self):
        m = svc.get_delivery_metrics([_attempt("skipped")])
        assert m.skipped == 1

    def test_proposed(self):
        m = svc.get_delivery_metrics([_attempt("proposed")])
        assert m.proposed == 1

    def test_success_rate(self):
        m = svc.get_delivery_metrics([_attempt("sent"), _attempt("failed")])
        assert m.success_rate == 0.5

    def test_failure_rate(self):
        m = svc.get_delivery_metrics([_attempt("sent"), _attempt("failed")])
        assert m.failure_rate == 0.5

    def test_blocked_rate(self):
        m = svc.get_delivery_metrics([_attempt("blocked"), _attempt("sent")])
        assert m.blocked_rate == 0.5

    def test_unique_contacts(self):
        m = svc.get_delivery_metrics([_attempt(contact_id=1), _attempt(contact_id=2)])
        assert m.unique_contacts == 2

    def test_duplicate_blocked(self):
        m = svc.get_delivery_metrics([_attempt("blocked", blocked_reason="duplicate_send")])
        assert m.duplicate_blocked == 1


class TestBlockedReasons:
    def test_grouped(self):
        attempts = [
            _attempt("blocked", blocked_reason="stopped"),
            _attempt("blocked", blocked_reason="stopped"),
            _attempt("blocked", blocked_reason="no_telegram_id"),
        ]
        r = svc.get_blocked_reason_metrics(attempts)
        assert r[0] == ("stopped", 2)
        assert r[1] == ("no_telegram_id", 1)

    def test_non_blocked_excluded(self):
        assert svc.get_blocked_reason_metrics([_attempt("sent")]) == []


class TestFailureReasons:
    def test_grouped(self):
        attempts = [
            _attempt("failed", error_message="timeout"),
            _attempt("failed", error_message="timeout"),
            _attempt("failed", error_message="forbidden"),
        ]
        r = svc.get_failure_reason_metrics(attempts)
        assert r[0] == ("timeout", 2)

    def test_token_redacted(self):
        attempts = [_attempt("failed", error_message="sk-secret123 error")]
        r = svc.get_failure_reason_metrics(attempts)
        assert "sk-" not in r[0][0]


class TestCanaryMetrics:
    def test_canary_sent(self):
        m = svc.get_canary_metrics([_attempt("sent", metadata_json={"is_canary": True})])
        assert m.canary_sent == 1

    def test_canary_failed(self):
        m = svc.get_canary_metrics([_attempt("failed", metadata_json={"is_canary": True})])
        assert m.canary_failed == 1

    def test_non_canary_skipped(self):
        m = svc.get_canary_metrics([_attempt("blocked", blocked_reason="not_in_canary")])
        assert m.non_canary_skipped == 1


class TestReplyMetrics:
    def test_replies(self):
        sent = [_attempt("sent", contact_id=1)]
        msgs = [{"contact_id": 1, "direction": "inbound", "lead_status": "active"}]
        m = svc.get_reply_metrics(sent, msgs)
        assert m.reply_count == 1
        assert m.contacts_replied == 1

    def test_reply_rate(self):
        sent = [_attempt("sent", contact_id=1), _attempt("sent", contact_id=2)]
        msgs = [{"contact_id": 1, "direction": "inbound"}]
        m = svc.get_reply_metrics(sent, msgs)
        assert m.reply_rate == 0.5

    def test_hot_replies(self):
        sent = [_attempt("sent", contact_id=1)]
        msgs = [{"contact_id": 1, "direction": "inbound", "lead_status": "hot"}]
        m = svc.get_reply_metrics(sent, msgs)
        assert m.hot_replies == 1

    def test_outbound_not_counted(self):
        sent = [_attempt("sent", contact_id=1)]
        msgs = [{"contact_id": 1, "direction": "outbound"}]
        m = svc.get_reply_metrics(sent, msgs)
        assert m.reply_count == 0

    def test_non_sent_contact_ignored(self):
        sent = [_attempt("sent", contact_id=1)]
        msgs = [{"contact_id": 999, "direction": "inbound"}]
        m = svc.get_reply_metrics(sent, msgs)
        assert m.reply_count == 0


class TestStatusChanges:
    def test_changes(self):
        sent = [_attempt("sent", contact_id=1)]
        changes = [{"contact_id": 1, "new_status": "hot"}]
        m = svc.get_status_change_metrics(sent, changes)
        assert m.status_changes == 1
        assert m.by_status[0] == ("hot", 1)

    def test_non_sent_excluded(self):
        sent = [_attempt("blocked", contact_id=1)]
        changes = [{"contact_id": 1, "new_status": "hot"}]
        m = svc.get_status_change_metrics(sent, changes)
        assert m.status_changes == 0

    def test_rate(self):
        sent = [_attempt("sent", contact_id=1), _attempt("sent", contact_id=2)]
        changes = [{"contact_id": 1, "new_status": "hot"}]
        m = svc.get_status_change_metrics(sent, changes)
        assert m.status_change_rate == 0.5


class TestRecommendations:
    def test_no_telegram_id(self):
        from core.services.crm_campaign_analytics_service import (
            CanaryMetrics,
            DeliveryMetrics,
            ReplyMetrics,
        )

        blocked = [("no_telegram_id", 5)]
        recs = svc.build_recommendations(
            DeliveryMetrics(), blocked, CanaryMetrics(), ReplyMetrics()
        )
        assert any("telegram" in r.description.lower() for r in recs)

    def test_canary_failure(self):
        from core.services.crm_campaign_analytics_service import (
            CanaryMetrics,
            DeliveryMetrics,
            ReplyMetrics,
        )

        canary = CanaryMetrics(canary_failed=2)
        recs = svc.build_recommendations(DeliveryMetrics(), [], canary, ReplyMetrics())
        assert any("canary" in r.description.lower() for r in recs)

    def test_low_reply_rate(self):
        from core.services.crm_campaign_analytics_service import (
            CanaryMetrics,
            DeliveryMetrics,
            ReplyMetrics,
        )

        delivery = DeliveryMetrics(sent=10)
        replies = ReplyMetrics(reply_rate=0.02)
        recs = svc.build_recommendations(delivery, [], CanaryMetrics(), replies)
        assert any("reply" in r.title.lower() for r in recs)

    def test_ok_when_clean(self):
        from core.services.crm_campaign_analytics_service import (
            CanaryMetrics,
            DeliveryMetrics,
            ReplyMetrics,
        )

        recs = svc.build_recommendations(DeliveryMetrics(), [], CanaryMetrics(), ReplyMetrics())
        assert any("yaxshi" in r.title.lower() for r in recs)


class TestSanitize:
    def test_token(self):
        d = svc.sanitize_output({"note": "sk-secret123"})
        assert "sk-" not in d["note"]


class TestFullAnalytics:
    def test_build(self):
        attempts = [_attempt("sent"), _attempt("blocked", blocked_reason="stopped")]
        a = svc.build_campaign_analytics(1, attempts)
        assert a.delivery.sent == 1
        assert a.delivery.blocked == 1
        assert len(a.blocked_reasons) == 1


class TestDashboard:
    def test_build(self):
        campaigns = [{"id": 1, "segment_key": "hot_leads"}]
        attempts = [_attempt("sent"), _attempt("failed")]
        d = svc.build_dashboard_summary(campaigns, attempts)
        assert d.total_campaigns == 1
        assert d.total_sent == 1
        assert d.total_failed == 1


class TestImmutability:
    def test_delivery_frozen(self):
        import pytest

        from core.services.crm_campaign_analytics_service import DeliveryMetrics

        m = DeliveryMetrics()
        with pytest.raises(AttributeError):
            m.sent = 5  # type: ignore[misc]

    def test_analytics_frozen(self):
        import pytest

        from core.services.crm_campaign_analytics_service import CampaignAnalytics

        a = CampaignAnalytics()
        with pytest.raises(AttributeError):
            a.campaign_id = 5  # type: ignore[misc]

    def test_recommendation_frozen(self):
        import pytest

        from core.services.crm_campaign_analytics_service import CampaignRecommendation

        r = CampaignRecommendation()
        with pytest.raises(AttributeError):
            r.title = "x"  # type: ignore[misc]
