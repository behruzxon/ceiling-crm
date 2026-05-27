"""Tests for Step AC — Rollout Presets UI template."""

from __future__ import annotations

from pathlib import Path

_TEMPLATE = Path("apps/web/templates/agent.html").read_text(encoding="utf-8")


class TestPresetsSection:
    def test_rollout_presets_present(self):
        assert "Rollout Presets" in _TEMPLATE

    def test_preset_cards_visible(self):
        assert "OFF" in _TEMPLATE
        assert "LOG ONLY" in _TEMPLATE
        assert "DRY RUN" in _TEMPLATE
        assert "CANARY" in _TEMPLATE
        assert "APPROVAL" in _TEMPLATE
        assert "LIVE SEND" in _TEMPLATE

    def test_preview_js_function(self):
        assert "previewPreset" in _TEMPLATE

    def test_apply_preset_js_function(self):
        assert "applyPreset" in _TEMPLATE

    def test_cancel_preset_function(self):
        assert "cancelPreset" in _TEMPLATE

    def test_diff_panel(self):
        assert "presetDiff" in _TEMPLATE

    def test_blocker_message(self):
        assert "presetMessage" in _TEMPLATE

    def test_confirm_dialog(self):
        assert "confirm(" in _TEMPLATE

    def test_no_secret_values(self):
        assert "api_key" not in _TEMPLATE.lower()
        assert "bot_token" not in _TEMPLATE.lower()

    def test_mutation_banner_compatible(self):
        assert "settingsMutationBanner" in _TEMPLATE


class TestNonRegression:
    def test_control_center_present(self):
        assert "Control Center" in _TEMPLATE

    def test_settings_control_present(self):
        assert "Settings Control" in _TEMPLATE

    def test_overview_cards_present(self):
        assert "Journey eventlar" in _TEMPLATE

    def test_approve_exec_present(self):
        assert "approveExec" in _TEMPLATE
