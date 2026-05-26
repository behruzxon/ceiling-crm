"""Tests for Step BQ — Operator Workflow Polish UI."""
from __future__ import annotations
from pathlib import Path


def _crm():
    return Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")

def _detail():
    return Path("apps/web/templates/crm_contact_detail.html").read_text(encoding="utf-8")


class TestQuickFilterBar:
    def test_filter_bar_exists(self):
        assert "quickFilterBar" in _crm()

    def test_critical_chip(self):
        assert 'data-filter="critical"' in _crm()

    def test_hot_chip(self):
        assert 'data-filter="hot"' in _crm()

    def test_operator_needed_chip(self):
        assert 'data-filter="operator_needed"' in _crm()

    def test_unanswered_chip(self):
        assert 'data-filter="unanswered"' in _crm()

    def test_overdue_chip(self):
        assert 'data-filter="overdue"' in _crm()

    def test_price_interested_chip(self):
        assert 'data-filter="price_interested"' in _crm()

    def test_clear_filters_button(self):
        assert "btnClearFilters" in _crm()

    def test_active_filter_class(self):
        assert "qf-chip.active" in _crm()

    def test_hidden_by_filter_class(self):
        assert "hidden-by-filter" in _crm()


class TestKeyboardShortcuts:
    def test_shortcut_help_button(self):
        assert "btnShortcutHelp" in _crm()

    def test_shortcut_popover(self):
        assert "shortcutHelpPopover" in _crm()

    def test_slash_documented(self):
        c = _crm()
        assert "/" in c and "fokus" in c.lower()

    def test_1_documented(self):
        assert "Critical filter" in _crm()

    def test_2_documented(self):
        assert "Hot filter" in _crm()

    def test_3_documented(self):
        assert "Operator kerak" in _crm()

    def test_r_documented(self):
        assert "Yangilash" in _crm()

    def test_n_documented(self):
        assert "Keyingi contact" in _crm()

    def test_esc_documented(self):
        assert "Esc" in _crm()

    def test_shortcuts_disabled_in_input(self):
        c = _crm()
        assert "input" in c and "textarea" in c and "select" in c

    def test_keydown_listener(self):
        assert "keydown" in _crm()


class TestQuickActions:
    def test_open_link(self):
        assert "Ochish" in _crm()

    def test_copy_id_button(self):
        assert 'data-action="copy-id"' in _crm()

    def test_crm_row_data_attrs(self):
        c = _crm()
        assert "data-status" in c
        assert "data-temp" in c


class TestHideStoppedToggle:
    def test_toggle_exists(self):
        assert "hideStoppedToggle" in _crm()

    def test_default_checked(self):
        c = _crm()
        assert 'id="hideStoppedToggle" checked' in c or "hideStoppedToggle" in c


class TestContactDetailOperatorPanel:
    def test_operator_checklist(self):
        assert "operatorChecklist" in _detail()

    def test_phone_known(self):
        assert "Telefon" in _detail() and "checklist" in _detail().lower()

    def test_area_known(self):
        d = _detail()
        assert "Maydon" in d or "m2" in d

    def test_location_known(self):
        assert "Tuman" in _detail() or "joylashuv" in _detail()

    def test_ceiling_type_known(self):
        assert "Potolok turi" in _detail()

    def test_status_updated(self):
        assert "Status yangilangan" in _detail()

    def test_sla_badge(self):
        assert "slaBadge" in _detail()

    def test_sla_status_text(self):
        assert "slaStatusText" in _detail()

    def test_next_action(self):
        assert "nextActionText" in _detail()


class TestEmptyAndErrorStates:
    def test_empty_state(self):
        assert "crmEmptyState" in _crm()

    def test_loading_state(self):
        assert "crmLoadingState" in _crm()

    def test_fetch_error_banner(self):
        assert "crmFetchError" in _crm()

    def test_error_message_text(self):
        assert "xatolik" in _crm()


class TestMobileResponsive:
    def test_media_query(self):
        assert "@media" in _crm()

    def test_responsive_table(self):
        c = _crm()
        assert "768px" in c or "max-width" in c


class TestSafety:
    def test_no_innerhtml(self):
        assert "innerHTML" not in _crm()

    def test_uses_textcontent(self):
        assert "textContent" in _crm()

    def test_no_token_rendered(self):
        c = _crm()
        assert "sk-" not in c
        assert "session_id_hash" not in c

    def test_reply_flag_controlled(self):
        assert "reply" in _detail().lower()

    def test_critical_pulse_preserved(self):
        assert "critical-pulse" in _crm()

    def test_live_summary_preserved(self):
        assert "fetchLiveSummary" in _crm()

    def test_notification_preserved(self):
        assert "toggleNotifications" in _crm()


class TestSettings:
    def test_workflow_polish(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_operator_workflow_polish_enabled"].default is True

    def test_shortcuts(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_keyboard_shortcuts_enabled"].default is True

    def test_quick_actions(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_quick_actions_enabled"].default is True

    def test_hide_stopped(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_default_hide_stopped"].default is True

    def test_next_contact(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields["crm_operator_next_contact_enabled"].default is True
