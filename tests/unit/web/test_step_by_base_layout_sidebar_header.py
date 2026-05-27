"""Tests for Step BY — Base Layout + Sidebar/Header Premium Redesign."""
from __future__ import annotations

from pathlib import Path


def _base():
    return Path("apps/web/templates/base.html").read_text(encoding="utf-8")

def _login():
    return Path("apps/web/templates/login.html").read_text(encoding="utf-8")


class TestShellClasses:
    def test_vp_shell(self):
        assert "vp-shell" in _base()

    def test_vp_sidebar(self):
        assert "vp-sidebar" in _base()

    def test_vp_topbar(self):
        assert "vp-topbar" in _base()

    def test_vp_content(self):
        assert "vp-content" in _base()


class TestSidebarBrand:
    def test_brand_class(self):
        assert "vp-sidebar-brand" in _base()

    def test_brand_icon(self):
        assert "vp-sidebar-brand-icon" in _base()

    def test_brand_title(self):
        assert "vp-sidebar-brand-title" in _base()

    def test_brand_subtitle_class(self):
        assert "vp-sidebar-brand-subtitle" in _base()

    def test_ai_crm_platform(self):
        assert "AI CRM Platform" in _base()

    def test_vashpotolok(self):
        assert "Vashpotolok" in _base()


class TestNavSections:
    def test_asosiy_section(self):
        assert "Asosiy" in _base()

    def test_crm_section(self):
        c = _base()
        assert ">CRM<" in c or "CRM</div" in c

    def test_ai_section(self):
        assert ">AI<" in _base() or "AI</div" in _base()

    def test_admin_section(self):
        assert "Admin" in _base()


class TestNavLinks:
    def test_dashboard(self):
        assert "/dashboard" in _base()

    def test_pipeline(self):
        assert "/pipeline" in _base()

    def test_leads(self):
        assert "/leads" in _base()

    def test_crm_inbox(self):
        c = _base()
        assert '"/crm"' in c or "'/crm'" in c or "/crm" in c

    def test_campaigns(self):
        assert "/crm/campaigns" in _base()

    def test_analytics(self):
        assert "/analytics" in _base()

    def test_agent(self):
        assert "/agent" in _base()

    def test_security(self):
        assert "/admin/security" in _base()


class TestActiveState:
    def test_nav_link_active_class(self):
        assert "vp-nav-link" in _base()
        assert ".active" in _base()

    def test_active_page_dashboard(self):
        assert "active_page == 'dashboard'" in _base()

    def test_active_page_crm(self):
        assert "active_page == 'crm'" in _base()

    def test_active_page_campaigns(self):
        assert "active_page == 'campaigns'" in _base()

    def test_active_page_agent(self):
        assert "active_page == 'agent'" in _base()

    def test_active_page_security(self):
        assert "active_page == 'security'" in _base()

    def test_active_page_pipeline(self):
        assert "active_page == 'pipeline'" in _base()

    def test_active_page_leads(self):
        assert "active_page == 'leads'" in _base()

    def test_active_page_analytics(self):
        assert "active_page == 'analytics'" in _base()

    def test_active_border_left(self):
        assert "border-left" in _base()


class TestTopbar:
    def test_topbar_left(self):
        assert "vp-topbar-left" in _base()

    def test_topbar_right(self):
        assert "vp-topbar-right" in _base()

    def test_topbar_title(self):
        assert "vp-topbar-title" in _base()

    def test_topbar_subtitle_support(self):
        assert "vp-topbar-subtitle" in _base()
        assert "page_subtitle" in _base()

    def test_role_badge(self):
        assert "vp-role-badge" in _base()

    def test_title_agent(self):
        assert "AI Agent" in _base()

    def test_title_crm(self):
        assert "CRM Inbox" in _base()

    def test_title_security(self):
        assert "Security" in _base()

    def test_title_campaigns(self):
        assert "Campaigns" in _base()

    def test_title_fallback(self):
        assert "Systemax CRM" in _base()


class TestStatusDot:
    def test_status_dot_class(self):
        assert "vp-status-dot" in _base()

    def test_status_dot_green(self):
        assert "vp-status-dot-green" in _base()


class TestSidebarFooter:
    def test_footer_class(self):
        assert "vp-sidebar-footer" in _base()

    def test_safe_mode(self):
        assert "Safe mode" in _base()

    def test_flags_off(self):
        assert "Flags OFF" in _base()

    def test_version(self):
        assert "v1.0" in _base()


class TestMobile:
    def test_mobile_menu_btn(self):
        assert "vp-mobile-menu-btn" in _base()

    def test_sidebar_close(self):
        assert "vp-sidebar-close" in _base()

    def test_sidebar_overlay(self):
        assert "vp-sidebar-overlay" in _base()

    def test_media_query(self):
        assert "@media" in _base()
        assert "1023px" in _base()

    def test_open_sidebar_js(self):
        assert "openSidebar" in _base()

    def test_close_sidebar_js(self):
        assert "closeSidebar" in _base()


class TestSVGIcons:
    def test_svg_in_nav(self):
        c = _base()
        assert c.count("<svg") >= 8

    def test_no_html_entities(self):
        c = _base()
        assert "&#9632;" not in c
        assert "&#9782;" not in c
        assert "&#9776;" not in c


class TestLoginIsolation:
    def test_no_sidebar(self):
        c = _login()
        assert "vp-sidebar" not in c

    def test_no_base_extends(self):
        assert 'extends "base.html"' not in _login()

    def test_no_nav_links(self):
        c = _login()
        assert "/dashboard" not in c
        assert "/pipeline" not in c


class TestSafety:
    def test_no_innerhtml(self):
        assert "innerHTML" not in _base()

    def test_no_token(self):
        c = _base()
        assert "sk-" not in c
        assert "Bearer " not in c


class TestSmoke:
    def test_web_app(self):
        from apps.web.main import app
        assert app is not None

    def test_api_app(self):
        from apps.api.main import app
        assert app is not None
