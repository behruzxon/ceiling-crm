"""F4 — Next Best Action panel template tests."""

from __future__ import annotations

from pathlib import Path

_TEMPLATE_PATH = Path("apps/web/templates/crm_contact_detail.html")
_TEMPLATE = _TEMPLATE_PATH.read_text(encoding="utf-8")


def _new_section() -> str:
    start = _TEMPLATE.find("Next Best Action")
    end = _TEMPLATE.find("Operator AI Reply Suggestions", start + 1)
    assert start >= 0, "Next Best Action comment not found"
    assert end > start, "Operator AI Reply Suggestions not found after NBA"
    return _TEMPLATE[start:end]


_PANEL = _new_section()


class TestPanelExists:
    def test_panel_title(self) -> None:
        assert "Next Best Action" in _PANEL

    def test_panel_container_id(self) -> None:
        assert "nextBestActionPanel" in _PANEL

    def test_panel_uses_vp_card(self) -> None:
        assert "vp-card" in _PANEL

    def test_panel_uses_vp_card_header(self) -> None:
        assert "vp-card-header" in _PANEL


class TestPanelOrder:
    def test_panel_renders_before_operator_suggestions(self) -> None:
        nba_idx = _TEMPLATE.find("nextBestActionPanel")
        ops_idx = _TEMPLATE.find("operatorReplySuggestionsPanel")
        calc_idx = _TEMPLATE.find("manualPriceCalculatorPanel")
        assert nba_idx >= 0 and ops_idx > nba_idx
        assert nba_idx >= 0 and calc_idx > nba_idx


class TestContent:
    def test_priority_badge_present(self) -> None:
        assert "nbaPriorityBadge" in _PANEL

    def test_label_block(self) -> None:
        assert "nbaLabel" in _PANEL
        assert "nba.label" in _PANEL

    def test_reason_block(self) -> None:
        assert "nbaReason" in _PANEL
        assert "nba.reason" in _PANEL

    def test_confidence_block(self) -> None:
        assert "nbaConfidence" in _PANEL
        assert "nba.confidence" in _PANEL

    def test_cta_button_conditional(self) -> None:
        assert "nbaCtaButton" in _PANEL
        assert "nba.cta_url" in _PANEL

    def test_safety_note_block(self) -> None:
        assert "nbaSafetyNote" in _PANEL
        assert "nba.safety_note" in _PANEL

    def test_empty_state_block(self) -> None:
        assert "nbaEmpty" in _PANEL
        assert (
            "Hozircha aniq keyingi harakat yo&#39;q" in _PANEL
            or "Hozircha aniq keyingi harakat yo'q" in _PANEL
        )


class TestBadgeMapping:
    def test_uses_vp_badge_classes(self) -> None:
        assert "vp-badge" in _PANEL

    def test_uses_tone_to_class_mapping(self) -> None:
        for cls in (
            "vp-badge-hot",
            "vp-badge-warning",
            "vp-badge-success",
            "vp-badge-neutral",
            "vp-badge-info",
        ):
            assert cls in _PANEL


class TestSafetyNoSendNoPOST:
    def test_no_send_button(self) -> None:
        for word in ("Yuborish", "Send live", "Send message", "Send Telegram"):
            assert word not in _PANEL

    def test_no_post_form(self) -> None:
        assert 'method="post"' not in _PANEL.lower()
        assert "method='post'" not in _PANEL.lower()
        assert "<form" not in _PANEL.lower()

    def test_no_telegram_url_in_panel(self) -> None:
        assert "t.me/" not in _PANEL
        assert "api.telegram.org" not in _PANEL
        assert "sendMessage" not in _PANEL

    def test_no_openai_text(self) -> None:
        assert "openai.com" not in _PANEL
        assert "api.openai.com" not in _PANEL

    def test_no_flag_toggle_handlers(self) -> None:
        for h in ("previewSetting(", "previewPreset(", "applyPreset(", "rollbackSetting("):
            assert h not in _PANEL

    def test_cta_only_uses_in_page_anchor(self) -> None:
        # The CTA href is `{{ nba.cta_url }}`. Service-level tests pin
        # the whitelist; template-side we just confirm the rendered link
        # is not an external URL or javascript: scheme by inspection of
        # the panel source.
        assert 'href="http' not in _PANEL
        assert "javascript:" not in _PANEL


class TestNoSecretsInPanel:
    def test_no_api_key_text(self) -> None:
        assert "api_key" not in _PANEL

    def test_no_bot_token_text(self) -> None:
        assert "bot_token" not in _PANEL

    def test_no_db_url_text(self) -> None:
        assert "postgres://" not in _PANEL
        assert "DATABASE_URL" not in _PANEL

    def test_no_session_hash_text(self) -> None:
        assert "session_hash" not in _PANEL


class TestRouteWiring:
    def test_route_imports_compute(self) -> None:
        main_text = Path("apps/web/main.py").read_text(encoding="utf-8")
        assert "compute_next_best_action" in main_text

    def test_route_passes_next_best_action_to_template(self) -> None:
        main_text = Path("apps/web/main.py").read_text(encoding="utf-8")
        assert '"next_best_action"' in main_text
