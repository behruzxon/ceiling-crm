"""Integration tests for Step CB — Full Web UI Premium flow."""

from __future__ import annotations

from pathlib import Path


class TestAllPagesRender:
    def test_agent(self):
        assert Path("apps/web/templates/agent.html").exists()

    def test_campaigns(self):
        assert Path("apps/web/templates/crm_campaigns.html").exists()

    def test_security(self):
        assert Path("apps/web/templates/security.html").exists()

    def test_login(self):
        assert Path("apps/web/templates/login.html").exists()

    def test_dashboard(self):
        assert Path("apps/web/templates/dashboard.html").exists()

    def test_leads(self):
        assert Path("apps/web/templates/leads.html").exists()

    def test_pipeline(self):
        assert Path("apps/web/templates/pipeline.html").exists()

    def test_analytics(self):
        assert Path("apps/web/templates/analytics.html").exists()

    def test_crm_contacts(self):
        assert Path("apps/web/templates/crm_contacts.html").exists()

    def test_crm_detail(self):
        assert Path("apps/web/templates/crm_contact_detail.html").exists()


class TestActivePagesSet:
    def test_agent(self):
        assert "active_page" in Path("apps/web/templates/agent.html").read_text(encoding="utf-8")

    def test_crm(self):
        assert "active_page" in Path("apps/web/templates/crm_contacts.html").read_text(
            encoding="utf-8"
        )

    def test_security(self):
        assert "active_page" in Path("apps/web/templates/security.html").read_text(encoding="utf-8")

    def test_campaigns(self):
        assert "active_page" in Path("apps/web/templates/crm_campaigns.html").read_text(
            encoding="utf-8"
        )

    def test_dashboard(self):
        assert "active_page" in Path("apps/web/templates/dashboard.html").read_text(
            encoding="utf-8"
        )


class TestLoginStandalone:
    def test_no_base(self):
        c = Path("apps/web/templates/login.html").read_text(encoding="utf-8")
        assert 'extends "base.html"' not in c

    def test_no_nav(self):
        c = Path("apps/web/templates/login.html").read_text(encoding="utf-8")
        assert "/dashboard" not in c


class TestSendDisabled:
    def test_campaign_send_off(self):
        c = Path("apps/web/templates/crm_campaigns.html").read_text(encoding="utf-8")
        assert "o'chirilgan" in c or "disabled" in c.lower()


class TestNoTokenLeak:
    def test_all_templates(self):
        templates = Path("apps/web/templates").glob("*.html")
        for t in templates:
            c = t.read_text(encoding="utf-8")
            assert "sk-" not in c, f"Token leak in {t.name}"


class TestSmoke:
    def test_web(self):
        from apps.web.main import app

        assert app is not None

    def test_api(self):
        from apps.api.main import app

        assert app is not None

    def test_scheduler(self):
        import apps.scheduler.main

        assert apps.scheduler.main is not None
