"""Tests for Step AB — Agent Settings UI template."""
from __future__ import annotations

from pathlib import Path

_TEMPLATE = Path("apps/web/templates/agent.html").read_text(encoding="utf-8")


class TestSettingsControlSection:
    def test_settings_control_present(self):
        assert "Settings Control" in _TEMPLATE

    def test_mutation_banner_present(self):
        assert "settingsMutationBanner" in _TEMPLATE

    def test_settings_table_present(self):
        assert "settingsTable" in _TEMPLATE

    def test_risk_badges_present(self):
        assert "risk" in _TEMPLATE.lower()

    def test_source_badges_present(self):
        assert "source" in _TEMPLATE.lower()


class TestJSFunctions:
    def test_preview_function(self):
        assert "previewSetting" in _TEMPLATE

    def test_apply_function(self):
        assert "applySetting" in _TEMPLATE

    def test_rollback_function(self):
        assert "rollbackSetting" in _TEMPLATE

    def test_load_audit_function(self):
        assert "loadAuditLog" in _TEMPLATE

    def test_show_msg_function(self):
        assert "showMsg" in _TEMPLATE


class TestAuditLogSection:
    def test_audit_log_present(self):
        assert "auditLog" in _TEMPLATE

    def test_audit_log_details(self):
        assert "Audit Log" in _TEMPLATE


class TestSecurity:
    def test_no_secret_placeholders(self):
        assert "api_key" not in _TEMPLATE.lower()
        assert "bot_token" not in _TEMPLATE.lower()

    def test_no_raw_token_display(self):
        assert "confirmation_token_hash" not in _TEMPLATE

    def test_confirm_dialog_present(self):
        assert "confirm(" in _TEMPLATE

    def test_toggle_button_present(self):
        assert "Toggle" in _TEMPLATE

    def test_error_message_container(self):
        assert "settingsMessage" in _TEMPLATE

    def test_high_risk_styled(self):
        assert "high" in _TEMPLATE.lower()


class TestNonRegression:
    def test_control_center_still_present(self):
        assert "Control Center" in _TEMPLATE

    def test_overview_cards_still_present(self):
        assert "Journey eventlar" in _TEMPLATE

    def test_approve_exec_still_present(self):
        assert "approveExec" in _TEMPLATE

    def test_reject_exec_still_present(self):
        assert "rejectExec" in _TEMPLATE
