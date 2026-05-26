"""Tests for Step CB — Full Web UI Premium Completion."""
from __future__ import annotations
from pathlib import Path

def _t(name):
    return Path(f"apps/web/templates/{name}").read_text(encoding="utf-8")


class TestAgentPage:
    def test_active_page(self):
        assert 'active_page = "agent"' in _t("agent.html")
    def test_stage_badge(self):
        assert "stage" in _t("agent.html").lower()
    def test_health_badge(self):
        assert "health" in _t("agent.html").lower()
    def test_dangerous_flags(self):
        assert "flag" in _t("agent.html").lower()
    def test_rollout_timeline(self):
        c = _t("agent.html")
        assert "OFF" in c and "LOG ONLY" in c and "DRY RUN" in c
    def test_preset_cards(self):
        c = _t("agent.html")
        assert "previewPreset" in c
    def test_settings_table(self):
        assert "settingsTable" in _t("agent.html")
    def test_approval_queue(self):
        c = _t("agent.html")
        assert "approveExec" in c or "Tasdiq" in c
    def test_observation_panel(self):
        assert "observationPanel" in _t("agent.html")
    def test_vp_kpi_grid(self):
        assert "vp-kpi-grid" in _t("agent.html")
    def test_vp_card(self):
        assert "vp-card" in _t("agent.html")


class TestCampaignsPage:
    def test_active_page(self):
        assert 'active_page = "campaigns"' in _t("crm_campaigns.html")
    def test_send_off_banner(self):
        c = _t("crm_campaigns.html")
        assert "o'chirilgan" in c or "disabled" in c.lower()
    def test_segment_cards(self):
        assert "vp-kpi-card" in _t("crm_campaigns.html") or "vp-kpi-grid" in _t("crm_campaigns.html")
    def test_draft_list(self):
        assert "vp-table" in _t("crm_campaigns.html")
    def test_vp_card(self):
        assert "vp-card" in _t("crm_campaigns.html")
    def test_empty_state(self):
        assert "vp-empty-state" in _t("crm_campaigns.html")


class TestSecurityPage:
    def test_active_page(self):
        assert 'active_page = "security"' in _t("security.html")
    def test_page_title(self):
        assert "page_title" in _t("security.html")
    def test_subtitle(self):
        assert "page_subtitle" in _t("security.html")
    def test_kpi_cards(self):
        c = _t("security.html")
        assert "Failed login" in c
        assert "Blocked login" in c
        assert "Aktiv sessiyalar" in c
    def test_suspicious_panel(self):
        assert "Shubhali holatlar" in _t("security.html")
    def test_recommendations(self):
        assert "Tavsiyalar" in _t("security.html")
    def test_no_session_hash(self):
        assert "session_id_hash" not in _t("security.html")


class TestDashboard:
    def test_active_page(self):
        assert "active_page" in _t("dashboard.html")

class TestLeads:
    def test_active_page(self):
        assert "active_page" in _t("leads.html")

class TestPipeline:
    def test_active_page(self):
        assert "active_page" in _t("pipeline.html")

class TestAnalytics:
    def test_active_page(self):
        assert "active_page" in _t("analytics.html")


class TestLoginPage:
    def test_standalone(self):
        assert 'extends "base.html"' not in _t("login.html")
    def test_no_sidebar(self):
        assert "vp-sidebar" not in _t("login.html")
    def test_gradient_bg(self):
        assert "gradient" in _t("login.html")
    def test_card_container(self):
        assert "border-radius" in _t("login.html")
    def test_brand(self):
        c = _t("login.html")
        assert "Vashpotolok" in c or "CeilingCRM" in c
    def test_error_state(self):
        assert "error" in _t("login.html")
    def test_mobile(self):
        assert "max-w-md" in _t("login.html")
    def test_visible_labels(self):
        c = _t("login.html")
        assert "Admin ID" in c
        assert "Token" in c


class TestDesignSystemUsage:
    def test_vp_card_agent(self):
        assert "vp-card" in _t("agent.html")
    def test_vp_card_campaigns(self):
        assert "vp-card" in _t("crm_campaigns.html")
    def test_vp_badge_campaigns(self):
        assert "vp-badge" in _t("crm_campaigns.html")
    def test_vp_table_campaigns(self):
        assert "vp-table" in _t("crm_campaigns.html")
    def test_vp_alert_campaigns(self):
        assert "vp-alert" in _t("crm_campaigns.html")
    def test_vp_empty_campaigns(self):
        assert "vp-empty-state" in _t("crm_campaigns.html")


class TestMobileResponsive:
    def test_agent_responsive(self):
        assert "vp-responsive-grid" in _t("agent.html") or "auto-fill" in _t("agent.html")
    def test_security_responsive(self):
        c = _t("security.html")
        assert "md:grid-cols" in c or "lg:grid-cols" in c


class TestSafety:
    def test_no_token_agent(self):
        c = _t("agent.html")
        assert "sk-" not in c
    def test_no_token_security(self):
        assert "sk-" not in _t("security.html")
    def test_no_token_campaigns(self):
        assert "sk-" not in _t("crm_campaigns.html")
    def test_no_token_login(self):
        assert "sk-" not in _t("login.html")
    def test_no_session_hash_agent(self):
        assert "session_id_hash" not in _t("agent.html")


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
