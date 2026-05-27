"""Integration tests for Step BP — Browser Alert flow."""
from __future__ import annotations

from pathlib import Path


class TestCRMPageRenders:
    def test_notification_controls(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "toggleNotifications" in c
        assert "toggleSound" in c
        assert "btnRequestPermission" in c

    def test_live_summary_updates(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "fetchLiveSummary" in c
        assert "setInterval" in c

    def test_critical_trigger_path(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "checkAlertTriggers" in c

    def test_preferences_default_off(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "crm_notifications_enabled" in c
        assert "crm_sound_enabled" in c


class TestNoServerSend:
    def test_no_telegram_in_template(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "send_message" not in c
        assert "aiogram" not in c

    def test_no_email_in_template(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "smtp" not in c.lower()
        assert "email" not in c.lower()


class TestNoTokenLeak:
    def test_no_secret_in_template(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "sk-" not in c
        assert "session_id_hash" not in c


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
