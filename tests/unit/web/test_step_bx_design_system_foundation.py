"""Tests for Step BX — Design System Foundation."""

from __future__ import annotations

from pathlib import Path


def _base():
    return Path("apps/web/templates/base.html").read_text(encoding="utf-8")


def _login():
    return Path("apps/web/templates/login.html").read_text(encoding="utf-8")


def _security():
    return Path("apps/web/templates/security.html").read_text(encoding="utf-8")


def _campaigns():
    return Path("apps/web/templates/crm_campaigns.html").read_text(encoding="utf-8")


class TestDesignSystemClasses:
    def test_vp_card(self):
        assert "vp-card" in _base()

    def test_vp_btn(self):
        assert "vp-btn" in _base()

    def test_vp_btn_primary(self):
        assert "vp-btn-primary" in _base()

    def test_vp_btn_secondary(self):
        assert "vp-btn-secondary" in _base()

    def test_vp_btn_danger(self):
        assert "vp-btn-danger" in _base()

    def test_vp_btn_ghost(self):
        assert "vp-btn-ghost" in _base()

    def test_vp_badge(self):
        assert "vp-badge" in _base()

    def test_vp_badge_success(self):
        assert "vp-badge-success" in _base()

    def test_vp_badge_warning(self):
        assert "vp-badge-warning" in _base()

    def test_vp_badge_danger(self):
        assert "vp-badge-danger" in _base()

    def test_vp_badge_info(self):
        assert "vp-badge-info" in _base()

    def test_vp_badge_neutral(self):
        assert "vp-badge-neutral" in _base()

    def test_vp_table(self):
        assert "vp-table" in _base()

    def test_vp_input(self):
        assert "vp-input" in _base()

    def test_vp_select(self):
        assert "vp-select" in _base()

    def test_vp_textarea(self):
        assert "vp-textarea" in _base()

    def test_vp_alert(self):
        assert "vp-alert" in _base()

    def test_vp_alert_danger(self):
        assert "vp-alert-danger" in _base()

    def test_vp_alert_warning(self):
        assert "vp-alert-warning" in _base()

    def test_vp_alert_info(self):
        assert "vp-alert-info" in _base()

    def test_vp_empty_state(self):
        assert "vp-empty-state" in _base()

    def test_vp_kpi_grid(self):
        assert "vp-kpi-grid" in _base()

    def test_vp_kpi_card(self):
        assert "vp-kpi-card" in _base()

    def test_vp_page_title(self):
        assert "vp-page-title" in _base()

    def test_vp_responsive_grid(self):
        assert "vp-responsive-grid" in _base()


class TestSidebarLinks:
    def test_crm_link(self):
        assert "/crm" in _base()

    def test_campaigns_link(self):
        assert "/crm/campaigns" in _base() or "campaigns" in _base()

    def test_agent_link(self):
        assert "/agent" in _base()

    def test_security_link(self):
        assert "/admin/security" in _base()

    def test_dashboard_link(self):
        assert "/dashboard" in _base()

    def test_pipeline_link(self):
        assert "/pipeline" in _base()

    def test_leads_link(self):
        assert "/leads" in _base()

    def test_analytics_link(self):
        assert "/analytics" in _base()


class TestActivePage:
    def test_agent_active(self):
        assert "active_page == 'agent'" in _base()

    def test_crm_active(self):
        assert "active_page == 'crm'" in _base()

    def test_security_active(self):
        assert "active_page == 'security'" in _base()

    def test_campaigns_active(self):
        assert "active_page == 'campaigns'" in _base()


class TestTopbarTitles:
    def test_agent_title(self):
        assert "AI Agent" in _base()

    def test_crm_title(self):
        assert "CRM Inbox" in _base()

    def test_security_title(self):
        assert "Security" in _base()

    def test_campaigns_title(self):
        assert "Campaigns" in _base()


class TestSVGIcons:
    def test_svg_icons_in_sidebar(self):
        assert "<svg" in _base()

    def test_no_html_entity_icons(self):
        c = _base()
        assert "&#9632;" not in c
        assert "&#9782;" not in c
        assert "&#9776;" not in c


class TestLoginSidebarFix:
    def test_no_sidebar_in_login(self):
        c = _login()
        assert "sidebar" not in c.lower() or "sidebar" not in c

    def test_no_base_extends(self):
        c = _login()
        assert 'extends "base.html"' not in c

    def test_has_form(self):
        assert "<form" in _login()

    def test_has_branding(self):
        c = _login()
        assert "CeilingCRM" in c or "Systemax" in c

    def test_visible_labels(self):
        c = _login()
        assert "Admin ID" in c
        assert "Token" in c

    def test_no_navigation_links(self):
        c = _login()
        assert "/dashboard" not in c
        assert "/pipeline" not in c
        assert "/crm" not in c


class TestSecurityActivePage:
    def test_active_page_set(self):
        assert 'active_page = "security"' in _security()


class TestCampaignsPage:
    def test_uses_design_system(self):
        c = _campaigns()
        assert "vp-card" in c
        assert "vp-table" in c or "vp-kpi-grid" in c

    def test_active_page(self):
        assert 'active_page = "campaigns"' in _campaigns()

    def test_no_send_banner(self):
        c = _campaigns()
        assert "o'chirilgan" in c or "disabled" in c.lower()

    def test_web_route_exists(self):
        from apps.web.main import app

        paths = [r.path for r in app.routes]
        assert "/crm/campaigns" in paths or any("campaigns" in str(p) for p in paths)


class TestSmoke:
    def test_web_app(self):
        from apps.web.main import app

        assert app is not None

    def test_api_app(self):
        from apps.api.main import app

        assert app is not None

    def test_scheduler(self):
        import apps.scheduler.main

        assert apps.scheduler.main is not None
