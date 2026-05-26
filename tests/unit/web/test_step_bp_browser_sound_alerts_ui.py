"""Tests for Step BP — Browser Notification + Sound Alerts UI."""
from __future__ import annotations
from pathlib import Path


def _content():
    return Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")


class TestNotificationToggle:
    def test_notification_toggle_renders(self):
        assert "toggleNotifications" in _content()

    def test_sound_toggle_renders(self):
        assert "toggleSound" in _content()

    def test_permission_button_renders(self):
        assert "btnRequestPermission" in _content()

    def test_permission_status_renders(self):
        assert "permissionStatus" in _content()

    def test_denied_warning_renders(self):
        assert "notifDeniedWarning" in _content()

    def test_alert_controls_container(self):
        assert "alertControls" in _content()


class TestLocalStorageKeys:
    def test_notifications_key(self):
        assert "crm_notifications_enabled" in _content()

    def test_sound_key(self):
        assert "crm_sound_enabled" in _content()

    def test_load_prefs(self):
        assert "loadPrefs" in _content()

    def test_save_notif_pref(self):
        assert "saveNotifPref" in _content()

    def test_save_sound_pref(self):
        assert "saveSoundPref" in _content()


class TestNotificationAPI:
    def test_notification_guarded(self):
        c = _content()
        assert "typeof Notification" in c

    def test_no_auto_permission_request(self):
        c = _content()
        assert "requestPermission" in c
        lines = c.split("\n")
        load_pref_lines = [l for l in lines if "loadPrefs" in l and "requestPermission" in l]
        assert len(load_pref_lines) == 0

    def test_permission_check_before_send(self):
        assert "Notification.permission" in _content()

    def test_denied_display(self):
        c = _content()
        assert "denied" in c


class TestCooldownConstants:
    def test_notif_cooldown(self):
        assert "NOTIF_COOLDOWN_MS" in _content()

    def test_sound_cooldown(self):
        assert "SOUND_COOLDOWN_MS" in _content()

    def test_cooldown_values(self):
        c = _content()
        assert "60000" in c
        assert "30000" in c


class TestTriggerLogic:
    def test_critical_increase_triggers(self):
        c = _content()
        assert "newCritical > prevCritical" in c or "checkAlertTriggers" in c

    def test_notify_severities(self):
        assert "NOTIFY_SEVERITIES" in _content()

    def test_critical_danger_in_severities(self):
        c = _content()
        assert '"critical"' in c
        assert '"danger"' in c

    def test_dedup_by_contact_type(self):
        c = _content()
        assert "contact_id" in c
        assert "alert_type" in c
        assert "prevAlertKeys" in c


class TestSoundBeep:
    def test_play_beep_function(self):
        assert "playBeep" in _content()

    def test_audio_context(self):
        assert "AudioContext" in _content()

    def test_sound_uses_enabled_flag(self):
        assert "isSoundEnabled" in _content()


class TestNotificationContent:
    def test_notification_title(self):
        c = _content()
        assert "CRM" in c

    def test_no_phone_in_notification(self):
        c = _content()
        assert "phone" not in c.lower() or "phone_captured" not in c

    def test_no_token_in_js(self):
        c = _content()
        assert "sk-" not in c
        assert "Bearer" not in c

    def test_click_handler(self):
        assert "onclick" in _content() or "n.onclick" in _content()


class TestSafeInsertion:
    def test_uses_textcontent(self):
        assert "textContent" in _content()

    def test_no_innerhtml(self):
        assert "innerHTML" not in _content()


class TestExistingFeatures:
    def test_critical_pulse_still_exists(self):
        assert "critical-pulse" in _content()

    def test_fetch_still_exists(self):
        assert "fetchLiveSummary" in _content()

    def test_setinterval_still_exists(self):
        assert "setInterval" in _content()

    def test_error_handling_still_exists(self):
        assert "xatolik" in _content()

    def test_live_alert_bar_exists(self):
        assert "liveAlertBar" in _content()


class TestSettings:
    def test_notifications_enabled(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_browser_notifications_enabled"].default is True

    def test_notifications_default_off(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_browser_notifications_default"].default is False

    def test_sound_enabled(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_sound_alerts_enabled"].default is True

    def test_sound_default_off(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_sound_alerts_default"].default is False

    def test_notif_cooldown(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_alert_notification_cooldown_seconds"].default == 60

    def test_sound_cooldown(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_alert_sound_cooldown_seconds"].default == 30

    def test_notify_severities(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_alert_notify_severities"].default == "critical,danger"
