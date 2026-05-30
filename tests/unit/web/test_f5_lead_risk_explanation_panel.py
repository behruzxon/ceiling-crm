"""F5 — Lead Risk Explanation panel template tests."""

from __future__ import annotations

from pathlib import Path

_TEMPLATE_PATH = Path("apps/web/templates/crm_contact_detail.html")
_TEMPLATE = _TEMPLATE_PATH.read_text(encoding="utf-8")


def _new_section() -> str:
    start = _TEMPLATE.find("Lead Risk Explanation")
    end = _TEMPLATE.find("Operator AI Reply Suggestions", start + 1)
    assert start >= 0, "Lead Risk Explanation comment not found"
    assert end > start, "Operator AI Reply Suggestions not found after risk panel"
    return _TEMPLATE[start:end]


_PANEL = _new_section()


class TestPanelExists:
    def test_panel_title(self) -> None:
        assert "Lead Risk Explanation" in _PANEL

    def test_panel_container_id(self) -> None:
        assert "leadRiskPanel" in _PANEL

    def test_panel_uses_vp_card(self) -> None:
        assert "vp-card" in _PANEL

    def test_panel_uses_vp_card_header(self) -> None:
        assert "vp-card-header" in _PANEL


class TestPanelOrder:
    def test_panel_after_next_best_action(self) -> None:
        nba_idx = _TEMPLATE.find("nextBestActionPanel")
        risk_idx = _TEMPLATE.find("leadRiskPanel")
        assert nba_idx >= 0 and risk_idx > nba_idx

    def test_panel_before_operator_suggestions(self) -> None:
        risk_idx = _TEMPLATE.find("leadRiskPanel")
        ops_idx = _TEMPLATE.find("operatorReplySuggestionsPanel")
        assert risk_idx >= 0 and ops_idx > risk_idx


class TestContent:
    def test_risk_badge_present(self) -> None:
        assert "leadRiskBadge" in _PANEL
        assert "lr.risk_level" in _PANEL

    def test_score_block(self) -> None:
        assert "leadRiskScore" in _PANEL
        assert "lr.score" in _PANEL

    def test_confidence_block(self) -> None:
        assert "leadRiskConfidence" in _PANEL
        assert "lr.confidence" in _PANEL

    def test_summary_block(self) -> None:
        assert "leadRiskSummary" in _PANEL
        assert "lr.summary" in _PANEL

    def test_reasons_list_block(self) -> None:
        assert "leadRiskReasons" in _PANEL
        assert "for r in lr.reasons" in _PANEL

    def test_reason_label_rendered(self) -> None:
        assert "r.label" in _PANEL

    def test_reason_detail_rendered(self) -> None:
        assert "r.detail" in _PANEL

    def test_safety_note_block(self) -> None:
        assert "leadRiskSafetyNote" in _PANEL
        assert "lr.safety_note" in _PANEL

    def test_empty_state_block(self) -> None:
        assert "leadRiskEmpty" in _PANEL
        assert (
            "Riskni tushuntirish uchun yetarli signal yo&#39;q" in _PANEL
            or "Riskni tushuntirish uchun yetarli signal yo'q" in _PANEL
        )


class TestBadgeMapping:
    def test_uses_vp_badge_class(self) -> None:
        assert "vp-badge" in _PANEL

    def test_uses_tone_to_class_mapping(self) -> None:
        for cls in ("vp-badge-hot", "vp-badge-warning", "vp-badge-success", "vp-badge-neutral"):
            assert cls in _PANEL


class TestSafetyNoSendNoPOST:
    def test_no_send_button(self) -> None:
        for word in ("Yuborish", "Send live", "Send message", "Send Telegram"):
            assert word not in _PANEL

    def test_no_post_form(self) -> None:
        assert 'method="post"' not in _PANEL.lower()
        assert "method='post'" not in _PANEL.lower()
        assert "<form" not in _PANEL.lower()

    def test_no_telegram_url(self) -> None:
        assert "t.me/" not in _PANEL
        assert "api.telegram.org" not in _PANEL
        assert "sendMessage" not in _PANEL

    def test_no_openai_text(self) -> None:
        assert "openai.com" not in _PANEL
        assert "api.openai.com" not in _PANEL

    def test_no_flag_toggle_handlers(self) -> None:
        for h in ("previewSetting(", "previewPreset(", "applyPreset(", "rollbackSetting("):
            assert h not in _PANEL


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

    def test_no_system_prompt_text(self) -> None:
        assert "system_prompt" not in _PANEL


class TestRouteWiring:
    def test_route_imports_explain(self) -> None:
        main_text = Path("apps/web/main.py").read_text(encoding="utf-8")
        assert "explain_lead_risk" in main_text

    def test_route_passes_lead_risk_to_template(self) -> None:
        main_text = Path("apps/web/main.py").read_text(encoding="utf-8")
        assert '"lead_risk"' in main_text
