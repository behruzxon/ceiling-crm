"""Tests for Step CD — Final UI Route Quality (50+ tests)."""

from __future__ import annotations

from pathlib import Path


def _t(name: str) -> str:
    return Path(f"apps/web/templates/{name}").read_text(encoding="utf-8")


# ── Login standalone ─────────────────────────────────────────────


class TestLoginStandalone:
    def test_no_sidebar(self):
        assert "vp-sidebar" not in _t("login.html")

    def test_no_extends_base(self):
        assert 'extends "base.html"' not in _t("login.html")

    def test_brand_exists(self):
        c = _t("login.html")
        assert "Vashpotolok" in c or "CeilingCRM" in c

    def test_gradient_bg(self):
        assert "gradient" in _t("login.html")

    def test_password_field(self):
        assert 'type="password"' in _t("login.html") or "password" in _t("login.html")


# ── Sidebar navigation ──────────────────────────────────────────


class TestSidebarNav:
    def _base(self):
        return _t("base.html")

    def test_has_dashboard(self):
        assert "/dashboard" in self._base()

    def test_has_crm(self):
        assert "/crm" in self._base()

    def test_has_campaigns(self):
        assert "/crm/campaigns" in self._base()

    def test_has_agent(self):
        assert "/agent" in self._base()

    def test_has_security(self):
        assert "/admin/security" in self._base()

    def test_has_pipeline(self):
        assert "/pipeline" in self._base()

    def test_has_leads(self):
        assert "/leads" in self._base()

    def test_has_analytics(self):
        assert "/analytics" in self._base()

    def test_nav_link_class(self):
        assert "vp-nav-link" in self._base()

    def test_nav_section_class(self):
        assert "vp-nav-section" in self._base()


# ── Active page support ─────────────────────────────────────────


class TestActivePageBase:
    def test_dashboard_highlight(self):
        assert "active_page == 'dashboard'" in _t("base.html")

    def test_crm_highlight(self):
        assert "active_page == 'crm'" in _t("base.html")

    def test_campaigns_highlight(self):
        assert "active_page == 'campaigns'" in _t("base.html")

    def test_agent_highlight(self):
        assert "active_page == 'agent'" in _t("base.html")

    def test_security_highlight(self):
        assert "active_page == 'security'" in _t("base.html")

    def test_pipeline_highlight(self):
        assert "active_page == 'pipeline'" in _t("base.html")

    def test_leads_highlight(self):
        assert "active_page == 'leads'" in _t("base.html")

    def test_analytics_highlight(self):
        assert "active_page == 'analytics'" in _t("base.html")


class TestActivePageSet:
    def test_dashboard(self):
        assert "active_page" in _t("dashboard.html")

    def test_pipeline(self):
        assert 'active_page = "pipeline"' in _t("pipeline.html")

    def test_leads(self):
        assert 'active_page = "leads"' in _t("leads.html")

    def test_analytics(self):
        assert 'active_page = "analytics"' in _t("analytics.html")

    def test_crm(self):
        assert 'active_page = "crm"' in _t("crm_contacts.html")

    def test_campaigns(self):
        assert 'active_page = "campaigns"' in _t("crm_campaigns.html")

    def test_agent(self):
        assert 'active_page = "agent"' in _t("agent.html")

    def test_security(self):
        assert 'active_page = "security"' in _t("security.html")


# ── CRM pages ───────────────────────────────────────────────────


class TestCRMContactDetail:
    def test_responsive_grid(self):
        c = _t("crm_contact_detail.html")
        assert "vp-responsive-grid" in c or "grid" in c

    def test_vp_card(self):
        assert "vp-card" in _t("crm_contact_detail.html")


class TestCRMInbox:
    def test_kpi_cards(self):
        c = _t("crm_contacts.html")
        assert "vp-kpi-card" in c or "vp-kpi-grid" in c

    def test_vp_table(self):
        assert "vp-table" in _t("crm_contacts.html")


# ── Campaign and security safety ────────────────────────────────


class TestCampaignSafety:
    def test_send_off_warning(self):
        c = _t("crm_campaigns.html")
        assert "o'chirilgan" in c or "disabled" in c.lower()

    def test_vp_alert(self):
        assert "vp-alert" in _t("crm_campaigns.html")


class TestSecuritySafety:
    def test_security_monitoring_present(self):
        c = _t("security.html")
        assert "Shubhali holatlar" in c

    def test_failed_login_kpi(self):
        assert "Failed login" in _t("security.html")

    def test_blocked_login_kpi(self):
        assert "Blocked login" in _t("security.html")

    def test_active_sessions_kpi(self):
        assert "Aktiv sessiyalar" in _t("security.html")


# ── Design system usage ─────────────────────────────────────────


class TestDesignSystem:
    def test_vp_card_dashboard(self):
        c = _t("dashboard.html")
        assert "vp-card" in c or "vp-kpi-card" in c or "card" in c.lower()

    def test_vp_card_crm(self):
        assert "vp-card" in _t("crm_contacts.html")

    def test_vp_card_agent(self):
        assert "vp-card" in _t("agent.html")

    def test_vp_badge_campaigns(self):
        assert "vp-badge" in _t("crm_campaigns.html")

    def test_vp_btn_agent(self):
        c = _t("agent.html")
        assert "vp-btn" in c or "btn" in c.lower() or "onclick" in c

    def test_security_card_style(self):
        c = _t("security.html")
        assert "bg-white" in c or "vp-card" in c


# ── Token/secret safety ─────────────────────────────────────────


class TestNoSecretsRendered:
    def test_no_session_hash(self):
        for name in ["base.html", "login.html", "agent.html", "security.html"]:
            assert "session_id_hash" not in _t(name), f"session_id_hash in {name}"

    def test_no_bot_token(self):
        for name in ["base.html", "login.html", "agent.html", "dashboard.html"]:
            c = _t(name)
            assert "bot_token" not in c.lower(), f"bot_token in {name}"

    def test_no_sk_key(self):
        for name in ["base.html", "agent.html", "security.html", "crm_campaigns.html"]:
            assert "sk-" not in _t(name), f"sk- in {name}"

    def test_no_deployed_claim(self):
        for name in ["dashboard.html", "agent.html", "security.html"]:
            c = _t(name).lower()
            assert "deployed to production" not in c, f"deployed claim in {name}"


# ── Mobile responsive ───────────────────────────────────────────


class TestMobileResponsive:
    def test_base_mobile_btn(self):
        assert "vp-mobile-menu-btn" in _t("base.html")

    def test_base_overlay(self):
        assert "vp-sidebar-overlay" in _t("base.html")

    def test_base_media_query(self):
        assert "max-width" in _t("base.html")


# ── Smoke imports ────────────────────────────────────────────────


class TestSmoke:
    def test_web_app(self):
        from apps.web.main import app

        assert app is not None

    def test_api_app(self):
        from apps.api.main import app

        assert app is not None
