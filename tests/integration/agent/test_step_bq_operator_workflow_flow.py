"""Integration tests for Step BQ — Operator Workflow flow."""
from __future__ import annotations
from pathlib import Path


class TestFilterChips:
    def test_critical_filter_chip(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert 'data-filter="critical"' in c

    def test_hot_filter_chip(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert 'data-filter="hot"' in c

    def test_operator_needed_chip(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert 'data-filter="operator_needed"' in c

    def test_stopped_hidden_default(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "hideStoppedToggle" in c


class TestLiveSummaryStillWorks:
    def test_fetch_live_summary(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "live-summary" in c

    def test_set_interval(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "setInterval" in c


class TestNotificationStillWorks:
    def test_toggles(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "toggleNotifications" in c
        assert "toggleSound" in c


class TestNoSendOccurs:
    def test_no_telegram_in_template(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "send_message" not in c
        assert "aiogram" not in c

    def test_no_email(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "smtp" not in c.lower()


class TestNoTokenLeak:
    def test_crm_page(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "sk-" not in c
        assert "session_id_hash" not in c

    def test_detail_page(self):
        c = Path("apps/web/templates/crm_contact_detail.html").read_text(encoding="utf-8")
        assert "sk-" not in c
        assert "session_id_hash" not in c


class TestContactDetail:
    def test_checklist_renders(self):
        c = Path("apps/web/templates/crm_contact_detail.html").read_text(encoding="utf-8")
        assert "operatorChecklist" in c

    def test_sla_badge_renders(self):
        c = Path("apps/web/templates/crm_contact_detail.html").read_text(encoding="utf-8")
        assert "slaBadge" in c


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
