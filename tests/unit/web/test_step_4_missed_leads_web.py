"""Tests for Step 4 — Missed Leads Web Page."""

from __future__ import annotations

from pathlib import Path


def _t() -> str:
    return Path("apps/web/templates/crm_missed_leads.html").read_text(encoding="utf-8")


def _base() -> str:
    return Path("apps/web/templates/base.html").read_text(encoding="utf-8")


class TestRouteExists:
    def test_web_route(self):
        c = Path("apps/web/main.py").read_text(encoding="utf-8")
        assert "/crm/missed-leads" in c

    def test_template_exists(self):
        assert Path("apps/web/templates/crm_missed_leads.html").exists()


class TestSidebar:
    def test_sidebar_link(self):
        assert "/crm/missed-leads" in _base()

    def test_active_highlight(self):
        assert "active_page == 'missed_leads'" in _base()

    def test_topbar_title(self):
        assert "Missed Leads" in _base()


class TestActivePage:
    def test_active_page_set(self):
        assert 'active_page = "missed_leads"' in _t()


class TestTitle:
    def test_title(self):
        assert "Missed Leads" in _t()

    def test_subtitle(self):
        c = _t().lower()
        assert "yo'qolib" in c or "nazorat" in c


class TestKPICards:
    def test_critical(self):
        assert "critical" in _t().lower()

    def test_high(self):
        assert "high" in _t().lower()

    def test_hot_unanswered(self):
        assert "hot_unanswered" in _t() or "Hot javobsiz" in _t()

    def test_operator_waiting(self):
        assert "operator_waiting" in _t() or "Operator kutmoqda" in _t()

    def test_phone_shared(self):
        assert "phone_shared" in _t() or "Telefon ulashgan" in _t()

    def test_oldest_wait(self):
        assert "oldest_wait" in _t() or "kutish" in _t().lower()


class TestFilters:
    def test_severity_filter(self):
        assert "sevFilter" in _t()

    def test_reason_filter(self):
        assert "reasonFilter" in _t()

    def test_refresh(self):
        assert "Yangilash" in _t() or "reload" in _t()


class TestRecommendations:
    def test_recommendations_section(self):
        assert "Tavsiyalar" in _t()

    def test_vp_alert(self):
        assert "vp-alert" in _t()


class TestTable:
    def test_vp_table(self):
        assert "vp-table" in _t()

    def test_severity_badge(self):
        assert "vp-badge-danger" in _t()

    def test_reason_badge(self):
        assert "vp-badge-neutral" in _t()

    def test_open_contact(self):
        assert "Ochish" in _t()


class TestEmptyState:
    def test_empty_message(self):
        c = _t().lower()
        assert "nazoratda" in c or "yo'q" in c

    def test_vp_empty_state(self):
        assert "vp-empty-state" in _t()


class TestNoSendButton:
    def test_no_send_message(self):
        c = _t().lower()
        assert "send_message" not in c
        assert "yuborish" not in c or "telefon" in c


class TestMobile:
    def test_responsive(self):
        assert "max-width" in _t() or "@media" in _t()


class TestSafety:
    def test_no_token(self):
        assert "sk-" not in _t()

    def test_no_session_hash(self):
        assert "session_id_hash" not in _t()

    def test_no_fake_eta(self):
        c = _t().lower()
        assert "hozir qo'ng'iroq" not in c


class TestDocExists:
    def test_doc_118(self):
        assert Path("docs/AI_AGENT_SYSTEM/118_MISSED_LEADS_DASHBOARD.md").exists()


class TestSmoke:
    def test_api(self):
        from apps.api.main import app

        assert app is not None

    def test_web(self):
        from apps.web.main import app

        assert app is not None
