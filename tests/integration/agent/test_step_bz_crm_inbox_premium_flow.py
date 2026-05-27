"""Integration tests for Step BZ — CRM Inbox Premium flow."""
from __future__ import annotations

from pathlib import Path


class TestPremiumLayout:
    def test_vp_kpi_grid(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "vp-kpi-grid" in c
    def test_vp_card(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "vp-card" in c
    def test_vp_table(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "vp-table" in c
    def test_vp_badge(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "vp-badge" in c


class TestLivePollingPreserved:
    def test_fetch(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "fetchLiveSummary" in c
        assert "setInterval" in c
    def test_url(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "live-summary" in c


class TestFiltersPreserved:
    def test_data_status(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "data-status" in c
    def test_data_temp(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "data-temp" in c
    def test_hidden_by_filter(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "hidden-by-filter" in c


class TestNotificationPreserved:
    def test_toggles(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "toggleNotifications" in c
        assert "toggleSound" in c


class TestNoSend:
    def test_no_telegram(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "send_message" not in c
        assert "aiogram" not in c


class TestNoTokenLeak:
    def test_no_secret(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "sk-" not in c


class TestMobile:
    def test_responsive(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "768px" in c


class TestSmoke:
    def test_api(self):
        from apps.api.main import app
        assert app is not None
    def test_web(self):
        from apps.web.main import app
        assert app is not None
    def test_scheduler(self):
        import apps.scheduler.main
        assert apps.scheduler.main is not None
