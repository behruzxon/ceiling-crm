"""Tests for Step BZ — CRM Inbox Premium Redesign."""

from __future__ import annotations

from pathlib import Path


def _c():
    return Path("apps/web/templates/crm_contacts.html").read_text(encoding="utf-8")


class TestPageHeader:
    def test_crm_inbox_title(self):
        assert "CRM Inbox" in _c()

    def test_subtitle(self):
        assert "page_subtitle" in _c()

    def test_last_updated(self):
        assert "liveLastUpdated" in _c()


class TestKPICards:
    def test_kpi_grid(self):
        assert "vp-kpi-grid" in _c()

    def test_kpi_card(self):
        assert "vp-kpi-card" in _c()

    def test_critical_card(self):
        assert "badgeCritical" in _c()

    def test_hot_card(self):
        assert "badgeHotUnanswered" in _c()

    def test_unanswered_card(self):
        assert "badgeUnanswered" in _c()

    def test_operator_card(self):
        assert "badgeOperator" in _c()

    def test_danger_card(self):
        assert "badgeDanger" in _c()

    def test_warning_card(self):
        assert "badgeWarning" in _c()

    def test_severity_border(self):
        assert "border-top:3px solid" in _c()


class TestControls:
    def test_notification_toggle(self):
        assert "toggleNotifications" in _c()

    def test_sound_toggle(self):
        assert "toggleSound" in _c()

    def test_permission_btn(self):
        assert "btnRequestPermission" in _c()

    def test_permission_status(self):
        assert "permissionStatus" in _c()

    def test_denied_warning(self):
        assert "notifDeniedWarning" in _c()

    def test_shortcut_help_btn(self):
        assert "btnShortcutHelp" in _c()

    def test_shortcut_popover(self):
        assert "shortcutHelpPopover" in _c()


class TestAlertPanel:
    def test_panel(self):
        assert "latestAlertsPanel" in _c()

    def test_list(self):
        assert "latestAlertsList" in _c()

    def test_critical_pulse(self):
        assert "critical-pulse" in _c()

    def test_empty_state(self):
        assert "alert yo'q" in _c() or "latestAlertsEmpty" in _c()


class TestQuickFilters:
    def test_bar(self):
        assert "quickFilterBar" in _c()

    def test_critical_chip(self):
        assert 'data-filter="critical"' in _c()

    def test_hot_chip(self):
        assert 'data-filter="hot"' in _c()

    def test_operator_chip(self):
        assert 'data-filter="operator_needed"' in _c()

    def test_unanswered_chip(self):
        assert 'data-filter="unanswered"' in _c()

    def test_overdue_chip(self):
        assert 'data-filter="overdue"' in _c()

    def test_price_chip(self):
        assert 'data-filter="price_interested"' in _c()

    def test_clear_btn(self):
        assert "btnClearFilters" in _c()

    def test_hide_stopped(self):
        assert "hideStoppedToggle" in _c()

    def test_active_class(self):
        assert "qf-chip.active" in _c()


class TestSearch:
    def test_search_input(self):
        assert "crmSearch" in _c()

    def test_vp_input_class(self):
        assert "vp-input" in _c()

    def test_status_filter(self):
        assert "crmStatusFilter" in _c()

    def test_temp_filter(self):
        assert "crmTempFilter" in _c()


class TestContactTable:
    def test_table(self):
        assert "crmContactsTable" in _c()

    def test_vp_table(self):
        assert "vp-table" in _c()

    def test_crm_row(self):
        assert "crm-row" in _c()

    def test_data_status(self):
        assert "data-status" in _c()

    def test_data_temp(self):
        assert "data-temp" in _c()

    def test_status_badge(self):
        assert "vp-badge" in _c()

    def test_temp_badge(self):
        assert "vp-badge-hot" in _c()

    def test_open_link(self):
        assert "Ochish" in _c()

    def test_copy_id(self):
        assert 'data-action="copy-id"' in _c()


class TestStates:
    def test_loading(self):
        assert "crmLoadingState" in _c()

    def test_empty(self):
        assert "crmEmptyState" in _c()

    def test_error(self):
        assert "crmFetchError" in _c()

    def test_vp_alert_danger(self):
        assert "vp-alert-danger" in _c() or "vp-alert" in _c()


class TestMobile:
    def test_media_query(self):
        assert "@media" in _c()

    def test_768px(self):
        assert "768px" in _c()

    def test_kpi_2col(self):
        assert "repeat(2, 1fr)" in _c()


class TestJS:
    def test_fetch(self):
        assert "fetchLiveSummary" in _c()

    def test_setinterval(self):
        assert "setInterval" in _c()

    def test_textcontent(self):
        assert "textContent" in _c()

    def test_no_innerhtml(self):
        assert "innerHTML" not in _c()

    def test_live_summary_url(self):
        assert "live-summary" in _c()

    def test_localstorage_keys(self):
        c = _c()
        assert "crm_notifications_enabled" in c
        assert "crm_sound_enabled" in c

    def test_keyboard_shortcuts(self):
        assert "keydown" in _c()


class TestSafety:
    def test_no_token(self):
        c = _c()
        assert "sk-" not in c
        assert "session_id_hash" not in c

    def test_same_origin(self):
        assert "same-origin" in _c()
