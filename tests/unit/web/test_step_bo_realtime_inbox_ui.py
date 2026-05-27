"""Tests for Step BO — Realtime Inbox UI."""

from __future__ import annotations

from pathlib import Path


class TestLiveAlertBar:
    def _content(self):
        return Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")

    def test_live_alert_bar_exists(self):
        assert "liveAlertBar" in self._content()

    def test_critical_badge(self):
        c = self._content()
        assert "badgeCritical" in c
        assert "countCritical" in c

    def test_danger_badge(self):
        c = self._content()
        assert "badgeDanger" in c
        assert "countDanger" in c

    def test_warning_badge(self):
        c = self._content()
        assert "badgeWarning" in c
        assert "countWarning" in c

    def test_unanswered_badge(self):
        c = self._content()
        assert "badgeUnanswered" in c
        assert "countUnanswered" in c

    def test_hot_unanswered_badge(self):
        c = self._content()
        assert "badgeHotUnanswered" in c
        assert "countHotUnanswered" in c

    def test_operator_badge(self):
        c = self._content()
        assert "badgeOperator" in c
        assert "countOperator" in c


class TestLatestAlertsPanel:
    def _content(self):
        return Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")

    def test_panel_exists(self):
        assert "latestAlertsPanel" in self._content()

    def test_alerts_list(self):
        assert "latestAlertsList" in self._content()


class TestLastUpdated:
    def test_label_exists(self):
        c = Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")
        assert "liveLastUpdated" in c


class TestAutoRefreshJS:
    def _content(self):
        return Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")

    def test_setinterval_exists(self):
        assert "setInterval" in self._content()

    def test_fetch_live_summary(self):
        assert "live-summary" in self._content()

    def test_poll_interval(self):
        assert "POLL_INTERVAL" in self._content()

    def test_uses_textcontent(self):
        c = self._content()
        assert "textContent" in c

    def test_no_innerhtml(self):
        c = self._content()
        assert "innerHTML" not in c

    def test_fetch_error_handling(self):
        c = self._content()
        assert "catch" in c
        assert "xatolik" in c


class TestCriticalPulse:
    def _content(self):
        return Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")

    def test_pulse_class(self):
        assert "critical-pulse" in self._content()

    def test_pulse_animation(self):
        assert "pulse-red" in self._content()

    def test_pulse_logic(self):
        c = self._content()
        assert "prevCritical" in c


class TestSecurity:
    def _content(self):
        return Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")

    def test_no_raw_script_injection(self):
        c = self._content()
        lines = [l for l in c.split("\n") if "innerHTML" in l]
        assert len(lines) == 0

    def test_no_secret_rendered(self):
        c = self._content()
        assert "session_id_hash" not in c
        assert "sk-" not in c

    def test_credentials_same_origin(self):
        assert "same-origin" in self._content()


class TestWebRoute:
    def test_crm_route_exists(self):
        from apps.web.main import app

        paths = [r.path for r in app.routes]
        assert "/crm" in paths or any("/crm" in str(p) for p in paths)
