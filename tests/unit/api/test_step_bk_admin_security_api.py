"""Tests for Step BK — Admin Security API endpoints."""
from __future__ import annotations

import pytest


class TestSecurityDashboardAPI:
    @pytest.mark.asyncio
    async def test_dashboard(self):
        from apps.api.routes.admin_security import security_dashboard
        r = await security_dashboard(hours=24)
        assert "login_metrics" in r
        assert "session_metrics" in r
        assert "denied_metrics" in r
        assert "sensitive_metrics" in r
        assert "suspicious" in r
        assert "recommendations" in r
        assert r["period_hours"] == 24

    @pytest.mark.asyncio
    async def test_dashboard_custom_hours(self):
        from apps.api.routes.admin_security import security_dashboard
        r = await security_dashboard(hours=48)
        assert r["period_hours"] == 48

    @pytest.mark.asyncio
    async def test_dashboard_empty_db(self):
        from apps.api.routes.admin_security import security_dashboard
        r = await security_dashboard()
        assert r["login_metrics"]["total"] == 0
        assert r["session_metrics"]["active"] == 0

    @pytest.mark.asyncio
    async def test_no_session_hash_in_response(self):
        from apps.api.routes.admin_security import security_dashboard
        r = await security_dashboard()
        assert "session_id_hash" not in str(r)


class TestLoginAttemptsAPI:
    @pytest.mark.asyncio
    async def test_list(self):
        from apps.api.routes.admin_security import list_login_attempts
        r = await list_login_attempts()
        assert r["attempts"] == []
        assert r["total"] == 0

    @pytest.mark.asyncio
    async def test_filters(self):
        from apps.api.routes.admin_security import list_login_attempts
        r = await list_login_attempts(status="failed", admin_id="u1")
        assert r["filters"]["status"] == "failed"
        assert r["filters"]["admin_id"] == "u1"


class TestSessionsAPI:
    @pytest.mark.asyncio
    async def test_list(self):
        from apps.api.routes.admin_security import list_sessions
        r = await list_sessions()
        assert r["sessions"] == []

    @pytest.mark.asyncio
    async def test_filters(self):
        from apps.api.routes.admin_security import list_sessions
        r = await list_sessions(status="active", admin_id="u1")
        assert r["filters"]["status"] == "active"


class TestAuditEventsAPI:
    @pytest.mark.asyncio
    async def test_list(self):
        from apps.api.routes.admin_security import list_audit_events
        r = await list_audit_events()
        assert r["events"] == []

    @pytest.mark.asyncio
    async def test_filters(self):
        from apps.api.routes.admin_security import list_audit_events
        r = await list_audit_events(action="crm.export", actor_admin_id="u1", status="success")
        assert r["filters"]["action"] == "crm.export"


class TestSuspiciousAPI:
    @pytest.mark.asyncio
    async def test_list(self):
        from apps.api.routes.admin_security import suspicious_activity
        r = await suspicious_activity(hours=24)
        assert r["indicators"] == []
        assert r["hours"] == 24

    @pytest.mark.asyncio
    async def test_custom_hours(self):
        from apps.api.routes.admin_security import suspicious_activity
        r = await suspicious_activity(hours=48)
        assert r["hours"] == 48


class TestRouterRegistration:
    def test_router_importable(self):
        from apps.api.routes.admin_security import router
        assert router.prefix == "/api/v1/admin/security"

    def test_api_app_has_security_routes(self):
        from apps.api.main import app
        paths = [r.path for r in app.routes]
        assert any("/admin/security" in str(p) for p in paths)


class TestDI:
    def test_security_audit_service_factory(self):
        from infrastructure.di import get_admin_security_audit_service
        svc = get_admin_security_audit_service()
        assert svc is not None


class TestSettings:
    def test_dashboard_enabled_default(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_security_dashboard_enabled"].default is True

    def test_default_hours(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_security_default_hours"].default == 24

    def test_max_hours(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_security_max_hours"].default == 720

    def test_mask_ip(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_security_mask_ip"].default is True

    def test_failed_threshold(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_security_failed_login_alert_threshold"].default == 5

    def test_denied_threshold(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_security_permission_denied_alert_threshold"].default == 10

    def test_export_threshold(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["admin_security_sensitive_export_threshold"].default == 3
