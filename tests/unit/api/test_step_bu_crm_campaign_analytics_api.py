"""Tests for Step BU — Campaign Analytics API."""
from __future__ import annotations

import pytest


class TestAnalyticsAPI:
    @pytest.mark.asyncio
    async def test_campaign_analytics(self):
        from apps.api.routes.admin_crm_campaigns import campaign_analytics
        r = await campaign_analytics(1)
        assert r["campaign_id"] == 1
        assert r["generated_at"] != ""
        assert r["delivery"]["total_attempts"] == 0

    @pytest.mark.asyncio
    async def test_custom_window(self):
        from apps.api.routes.admin_crm_campaigns import campaign_analytics
        r = await campaign_analytics(1, reply_window_hours=24)
        assert r["campaign_id"] == 1


class TestDashboardAPI:
    @pytest.mark.asyncio
    async def test_dashboard(self):
        from apps.api.routes.admin_crm_campaigns import campaign_dashboard
        r = await campaign_dashboard(hours=720)
        assert r["total_campaigns"] == 0
        assert r["total_sent"] == 0

    @pytest.mark.asyncio
    async def test_empty_safe(self):
        from apps.api.routes.admin_crm_campaigns import campaign_dashboard
        r = await campaign_dashboard()
        assert r["total_campaigns"] == 0


class TestRoutes:
    def test_analytics_route(self):
        from apps.api.main import app
        paths = [str(r.path) for r in app.routes]
        assert any("analytics" in p and "campaigns" in p for p in paths)


class TestNoTokenLeak:
    def test_failure_sanitized(self):
        from core.services.crm_campaign_analytics_service import CRMCampaignAnalyticsService
        attempts = [{"campaign_id": 1, "contact_id": 1, "status": "failed",
                     "error_message": "sk-secret123 err", "metadata_json": {}}]
        r = CRMCampaignAnalyticsService.get_failure_reason_metrics(attempts)
        assert "sk-" not in r[0][0]

    def test_output_sanitized(self):
        from core.services.crm_campaign_analytics_service import CRMCampaignAnalyticsService
        d = CRMCampaignAnalyticsService.sanitize_output({"note": "sk-secret"})
        assert "sk-" not in d["note"]
