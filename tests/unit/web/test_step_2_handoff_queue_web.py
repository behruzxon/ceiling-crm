"""Tests for Step 2 — Handoff Queue Web Page."""
from __future__ import annotations

from pathlib import Path


def _t(name: str) -> str:
    return Path(f"apps/web/templates/{name}").read_text(encoding="utf-8")


def _base() -> str:
    return _t("base.html")


class TestRouteExists:
    def test_web_route(self):
        c = Path("apps/web/main.py").read_text(encoding="utf-8")
        assert "/crm/handoffs" in c

    def test_template_exists(self):
        assert Path("apps/web/templates/crm_handoffs.html").exists()


class TestActivePage:
    def test_active_page_set(self):
        assert 'active_page = "handoffs"' in _t("crm_handoffs.html")

    def test_base_sidebar_link(self):
        assert "/crm/handoffs" in _base()

    def test_base_active_highlight(self):
        assert "active_page == 'handoffs'" in _base()

    def test_topbar_title(self):
        assert "Handoff Queue" in _base()


class TestPageTitle:
    def test_title(self):
        assert "Handoff Queue" in _t("crm_handoffs.html")

    def test_subtitle(self):
        c = _t("crm_handoffs.html")
        assert "operator" in c.lower() or "navbat" in c.lower()


class TestKPICards:
    def test_open_kpi(self):
        assert "total_open" in _t("crm_handoffs.html")

    def test_waiting_phone_kpi(self):
        assert "total_waiting_phone" in _t("crm_handoffs.html")

    def test_assigned_kpi(self):
        assert "total_assigned" in _t("crm_handoffs.html")

    def test_urgent_kpi(self):
        assert "total_urgent" in _t("crm_handoffs.html")

    def test_high_kpi(self):
        assert "total_high" in _t("crm_handoffs.html")


class TestFilters:
    def test_status_filter(self):
        assert "statusFilter" in _t("crm_handoffs.html")

    def test_priority_filter(self):
        assert "priorityFilter" in _t("crm_handoffs.html")

    def test_refresh_button(self):
        c = _t("crm_handoffs.html")
        assert "Yangilash" in c or "reload" in c


class TestQueueTable:
    def test_table_exists(self):
        assert "vp-table" in _t("crm_handoffs.html")

    def test_priority_badges(self):
        c = _t("crm_handoffs.html")
        assert "vp-badge-danger" in c
        assert "vp-badge-warning" in c

    def test_status_badges(self):
        c = _t("crm_handoffs.html")
        assert "vp-badge" in c

    def test_phone_masked_column(self):
        assert "phone_masked" in _t("crm_handoffs.html")


class TestActions:
    def test_assign_action(self):
        assert "assign" in _t("crm_handoffs.html")

    def test_contacted_action(self):
        assert "contacted" in _t("crm_handoffs.html")

    def test_resolve_action(self):
        assert "resolve" in _t("crm_handoffs.html")

    def test_cancel_action(self):
        assert "cancel" in _t("crm_handoffs.html")

    def test_contact_link(self):
        assert "Kontakt" in _t("crm_handoffs.html")


class TestEmptyState:
    def test_empty_message(self):
        c = _t("crm_handoffs.html")
        assert "operator so'rovlari yo'q" in c.lower()

    def test_vp_empty_state(self):
        assert "vp-empty-state" in _t("crm_handoffs.html")


class TestMobile:
    def test_responsive(self):
        c = _t("crm_handoffs.html")
        assert "max-width" in c or "@media" in c


class TestSafety:
    def test_no_token(self):
        assert "sk-" not in _t("crm_handoffs.html")

    def test_no_session_hash(self):
        assert "session_id_hash" not in _t("crm_handoffs.html")

    def test_no_fake_eta(self):
        c = _t("crm_handoffs.html").lower()
        assert "hozir qo'ng'iroq" not in c


class TestAPISmoke:
    def test_api_imports(self):
        from apps.api.main import app
        assert app is not None

    def test_web_imports(self):
        from apps.web.main import app
        assert app is not None


class TestDocExists:
    def test_doc_116(self):
        assert Path(
            "docs/AI_AGENT_SYSTEM/116_HANDOFF_QUEUE_API_WEB_PAGE.md",
        ).exists()
