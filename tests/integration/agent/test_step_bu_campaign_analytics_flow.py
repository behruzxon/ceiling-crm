"""Integration tests for Step BU — Campaign Analytics flow."""

from __future__ import annotations


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


class TestAnalyticsBuild:
    def test_sent_counted(self):
        from core.services.crm_campaign_analytics_service import CRMCampaignAnalyticsService

        a = CRMCampaignAnalyticsService.build_campaign_analytics(1, [_attempt("sent")])
        assert a.delivery.sent == 1

    def test_blocked_grouped(self):
        from core.services.crm_campaign_analytics_service import CRMCampaignAnalyticsService

        attempts = [
            _attempt("blocked", blocked_reason="stopped"),
            _attempt("blocked", blocked_reason="stopped"),
        ]
        a = CRMCampaignAnalyticsService.build_campaign_analytics(1, attempts)
        assert a.blocked_reasons[0] == ("stopped", 2)

    def test_failed_grouped(self):
        from core.services.crm_campaign_analytics_service import CRMCampaignAnalyticsService

        attempts = [_attempt("failed", error_message="timeout")]
        a = CRMCampaignAnalyticsService.build_campaign_analytics(1, attempts)
        assert len(a.failure_reasons) == 1


class TestReplyTracking:
    def test_reply_counted(self):
        from core.services.crm_campaign_analytics_service import CRMCampaignAnalyticsService

        sent = [_attempt("sent", contact_id=1)]
        msgs = [{"contact_id": 1, "direction": "inbound"}]
        a = CRMCampaignAnalyticsService.build_campaign_analytics(1, sent, inbound_messages=msgs)
        assert a.replies.reply_count == 1

    def test_outbound_ignored(self):
        from core.services.crm_campaign_analytics_service import CRMCampaignAnalyticsService

        sent = [_attempt("sent", contact_id=1)]
        msgs = [{"contact_id": 1, "direction": "outbound"}]
        a = CRMCampaignAnalyticsService.build_campaign_analytics(1, sent, inbound_messages=msgs)
        assert a.replies.reply_count == 0


class TestCanaryTracking:
    def test_canary_skipped(self):
        from core.services.crm_campaign_analytics_service import CRMCampaignAnalyticsService

        attempts = [_attempt("blocked", blocked_reason="not_in_canary")]
        a = CRMCampaignAnalyticsService.build_campaign_analytics(1, attempts)
        assert a.canary.non_canary_skipped == 1


class TestNoTrackingPixel:
    def test_no_pixel_in_service(self):
        import inspect

        import core.services.crm_campaign_analytics_service as mod

        src = inspect.getsource(mod)
        assert "pixel" not in src.lower()
        assert "tracking" not in src.lower() or "reply" in src.lower()


class TestNoSend:
    def test_no_telegram(self):
        import inspect

        import core.services.crm_campaign_analytics_service as mod

        src = inspect.getsource(mod)
        assert "aiogram" not in src
        assert "send_message" not in src


class TestNoTokenLeak:
    def test_failure_redacted(self):
        from core.services.crm_campaign_analytics_service import CRMCampaignAnalyticsService

        attempts = [_attempt("failed", error_message="sk-secret123")]
        r = CRMCampaignAnalyticsService.get_failure_reason_metrics(attempts)
        assert "sk-" not in r[0][0]


class TestSmoke:
    def test_api(self):
        from apps.api.main import app

        assert app is not None

    def test_scheduler(self):
        import apps.scheduler.main

        assert apps.scheduler.main is not None
