"""F2 — Operator AI reply suggestion panel template tests.

These tests inspect the rendered Jinja2 template source for the new
panel markup. They never start a server and never call the API.
"""

from __future__ import annotations

from pathlib import Path

_TEMPLATE_PATH = Path("apps/web/templates/crm_contact_detail.html")
_TEMPLATE = _TEMPLATE_PATH.read_text(encoding="utf-8")


def _new_section() -> str:
    start = _TEMPLATE.find("Operator AI Reply Suggestions")
    end = _TEMPLATE.find("AI Trace Viewer", start + 1)
    assert start >= 0, "panel comment not found"
    assert end > start, "AI Trace Viewer not found after panel"
    return _TEMPLATE[start:end]


_PANEL = _new_section()


class TestPanelExists:
    def test_panel_title_present(self) -> None:
        assert "Operator AI Reply Suggestions" in _PANEL

    def test_panel_container_id(self) -> None:
        assert "operatorReplySuggestionsPanel" in _PANEL

    def test_panel_uses_vp_card(self) -> None:
        assert "vp-card" in _PANEL

    def test_panel_uses_vp_card_header(self) -> None:
        assert "vp-card-header" in _PANEL


class TestSuggestionContext:
    def test_template_reads_suggestion_result(self) -> None:
        assert "suggestion_result" in _PANEL

    def test_template_uses_sr_alias(self) -> None:
        assert "set sr = suggestion_result" in _PANEL


class TestDisabledEmptyState:
    def test_disabled_empty_state_id(self) -> None:
        assert "suggestionsDisabledEmpty" in _PANEL

    def test_disabled_uses_vp_empty_state(self) -> None:
        assert "vp-empty-state" in _PANEL

    def test_disabled_default_message_present(self) -> None:
        assert (
            "AI reply suggestions hozir o&#39;chiq" in _PANEL
            or "AI reply suggestions hozir o'chiq" in _PANEL
        )

    def test_disabled_branch_is_conditional(self) -> None:
        assert "not sr or not sr.feature_enabled" in _PANEL


class TestEnabledRender:
    def test_source_preview_block_present(self) -> None:
        assert "suggestionsSource" in _PANEL

    def test_loops_over_suggestions(self) -> None:
        assert "for s in sr.suggestions" in _PANEL

    def test_tone_badge_rendered(self) -> None:
        assert "s.tone" in _PANEL

    def test_risk_badge_rendered(self) -> None:
        assert "s.risk_level" in _PANEL

    def test_uses_vp_badge_classes(self) -> None:
        assert "vp-badge" in _PANEL

    def test_suggestion_text_rendered(self) -> None:
        assert "s.text" in _PANEL

    def test_suggestion_reason_rendered(self) -> None:
        assert "s.reason" in _PANEL

    def test_copy_button_present(self) -> None:
        assert "suggestion-copy-btn" in _PANEL

    def test_copy_button_uses_clipboard(self) -> None:
        assert "navigator.clipboard.writeText" in _PANEL

    def test_safety_note_present(self) -> None:
        assert "suggestionsSafetyNote" in _PANEL


class TestNoSendNoPOST:
    def test_no_send_button_in_panel(self) -> None:
        for word in ("Yuborish", "Send live", "Send message", "Send Telegram"):
            assert word not in _PANEL

    def test_no_post_form_in_panel(self) -> None:
        assert 'method="post"' not in _PANEL.lower()
        assert "method='post'" not in _PANEL.lower()

    def test_no_telegram_send_text(self) -> None:
        assert "api.telegram.org" not in _PANEL
        assert "sendMessage" not in _PANEL

    def test_no_openai_call_from_template(self) -> None:
        assert "openai.com" not in _PANEL
        assert "api.openai.com" not in _PANEL

    def test_no_apply_or_toggle_handlers(self) -> None:
        for h in ("applySetting(", "previewSetting(", "applyPreset(", "previewPreset("):
            assert h not in _PANEL


class TestNoSecretsInPanel:
    def test_no_api_key_text(self) -> None:
        assert "api_key" not in _PANEL
        assert "API_KEY=" not in _PANEL

    def test_no_bot_token_text(self) -> None:
        assert "bot_token" not in _PANEL

    def test_no_db_url_text(self) -> None:
        assert "postgres://" not in _PANEL
        assert "DATABASE_URL" not in _PANEL

    def test_no_session_hash_text(self) -> None:
        assert "session_hash" not in _PANEL

    def test_no_system_prompt_text(self) -> None:
        assert "system_prompt" not in _PANEL
        assert "system prompt" not in _PANEL.lower()


class TestFeatureFlagDefault:
    def test_default_state_renders_disabled_empty(self) -> None:
        # Verify the template short-circuits cleanly when sr is falsy or
        # feature_enabled is false (the default for the new flag).
        assert "{% if not sr or not sr.feature_enabled %}" in _PANEL

    def test_settings_defines_flag_off(self) -> None:
        settings_text = Path("shared/config/settings.py").read_text(encoding="utf-8")
        assert "operator_reply_suggestions_enabled" in settings_text
        assert "OPERATOR_REPLY_SUGGESTIONS_ENABLED" in settings_text
        # Spot-check: the new flag must default to False (Python literal).
        idx = settings_text.find("operator_reply_suggestions_enabled")
        snippet = settings_text[idx : idx + 200]
        assert "default=False" in snippet


class TestRouteWiringSmoke:
    def test_route_imports_builder(self) -> None:
        main_text = Path("apps/web/main.py").read_text(encoding="utf-8")
        assert "build_operator_reply_suggestions" in main_text

    def test_route_passes_suggestion_result(self) -> None:
        main_text = Path("apps/web/main.py").read_text(encoding="utf-8")
        assert '"suggestion_result"' in main_text
