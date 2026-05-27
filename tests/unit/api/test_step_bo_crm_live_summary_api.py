"""Tests for Step BO — CRM Live Summary API."""

from __future__ import annotations


class TestLiveSummaryEndpoint:
    def test_endpoint_exists(self):
        from apps.api.routes.admin_crm import live_summary

        assert callable(live_summary)

    def test_api_has_route(self):
        from apps.api.main import app

        paths = [str(r.path) for r in app.routes]
        assert any("live-summary" in p for p in paths)


class TestServiceImport:
    def test_realtime_service_importable(self):
        from core.services.crm_realtime_inbox_service import CRMRealtimeInboxService

        assert CRMRealtimeInboxService is not None

    def test_build_live_summary(self):
        from core.services.crm_realtime_inbox_service import CRMRealtimeInboxService

        s = CRMRealtimeInboxService.build_live_summary([])
        assert s.generated_at != ""
        assert s.critical_count == 0


class TestSettings:
    def test_realtime_enabled(self):
        from shared.config.settings import BusinessSettings

        assert BusinessSettings.model_fields["crm_realtime_inbox_enabled"].default is True

    def test_mode_default_polling(self):
        from shared.config.settings import BusinessSettings

        assert BusinessSettings.model_fields["crm_realtime_inbox_mode"].default == "polling"

    def test_poll_seconds(self):
        from shared.config.settings import BusinessSettings

        assert BusinessSettings.model_fields["crm_realtime_inbox_poll_seconds"].default == 15

    def test_max_alerts(self):
        from shared.config.settings import BusinessSettings

        assert BusinessSettings.model_fields["crm_realtime_inbox_max_alerts"].default == 5

    def test_critical_pulse(self):
        from shared.config.settings import BusinessSettings

        assert BusinessSettings.model_fields["crm_realtime_inbox_critical_pulse"].default is True

    def test_sse_disabled(self):
        from shared.config.settings import BusinessSettings

        assert BusinessSettings.model_fields["crm_realtime_inbox_sse_enabled"].default is False


class TestNoTokenInSummary:
    def test_safe_text_redacts(self):
        from core.services.crm_realtime_inbox_service import CRMRealtimeInboxService

        assert "sk-" not in CRMRealtimeInboxService._safe_text("sk-secret")

    def test_phone_redacted(self):
        from core.services.crm_realtime_inbox_service import CRMRealtimeInboxService

        assert "+998" not in CRMRealtimeInboxService._safe_text("+998901234567")
