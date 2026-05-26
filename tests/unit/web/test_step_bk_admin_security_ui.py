"""Tests for Step BK — Admin Security Dashboard UI."""
from __future__ import annotations
from pathlib import Path


class TestTemplate:
    def test_security_template_exists(self):
        assert Path("apps/web/templates/security.html").exists()

    def test_template_has_sections(self):
        content = Path("apps/web/templates/security.html").read_text(encoding="utf-8")
        assert "Login urinishlari" in content
        assert "Aktiv sessiyalar" in content
        assert "Ruxsat rad etilgan" in content
        assert "Muhim actionlar" in content
        assert "Shubhali holatlar" in content
        assert "Tavsiyalar" in content

    def test_no_script_injection(self):
        content = Path("apps/web/templates/security.html").read_text(encoding="utf-8")
        assert "<script>" not in content.lower()
        assert "javascript:" not in content.lower()

    def test_no_session_hash(self):
        content = Path("apps/web/templates/security.html").read_text(encoding="utf-8")
        assert "session_id_hash" not in content
        assert "session_id" not in content

    def test_kpi_cards(self):
        content = Path("apps/web/templates/security.html").read_text(encoding="utf-8")
        assert "Failed login" in content
        assert "Blocked login" in content
        assert "Aktiv sessiyalar" in content

    def test_severity_badges(self):
        content = Path("apps/web/templates/security.html").read_text(encoding="utf-8")
        assert "severity" in content

    def test_extends_base(self):
        content = Path("apps/web/templates/security.html").read_text(encoding="utf-8")
        assert "extends" in content
        assert "base.html" in content


class TestWebRoute:
    def test_web_app_has_security_route(self):
        from apps.web.main import app
        paths = [r.path for r in app.routes]
        assert "/admin/security" in paths or any("/admin/security" in str(p) for p in paths)


class TestSchemas:
    def test_dashboard_schema(self):
        from core.schemas.admin_security_audit import AdminSecurityDashboardSchema
        d = AdminSecurityDashboardSchema()
        assert d.period_hours == 24

    def test_dashboard_schema_frozen(self):
        import pytest
        from core.schemas.admin_security_audit import AdminSecurityDashboardSchema
        d = AdminSecurityDashboardSchema()
        with pytest.raises(AttributeError):
            d.period_hours = 48  # type: ignore[misc]

    def test_recent_event(self):
        from core.schemas.admin_security_audit import RecentSecurityEvent
        e = RecentSecurityEvent(action="test", status="success")
        assert e.action == "test"

    def test_recent_event_frozen(self):
        import pytest
        from core.schemas.admin_security_audit import RecentSecurityEvent
        e = RecentSecurityEvent()
        with pytest.raises(AttributeError):
            e.action = "x"  # type: ignore[misc]
