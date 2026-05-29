"""Tests for F1 — Agent Control Center polish (template-level)."""

from __future__ import annotations

from pathlib import Path

_TEMPLATE_PATH = Path("apps/web/templates/agent.html")
_TEMPLATE = _TEMPLATE_PATH.read_text(encoding="utf-8")


def _new_section(start_marker: str, end_marker: str) -> str:
    """Slice the template between two new-section markers (inclusive of start)."""
    start = _TEMPLATE.find(start_marker)
    end = _TEMPLATE.find(end_marker, start + 1)
    assert start >= 0, f"start marker not found: {start_marker}"
    assert end > start, f"end marker not found after start: {end_marker}"
    return _TEMPLATE[start:end]


_PILL_BLOCK = _new_section("Overall Status Pill", "Last Decision Summary Card")
_LAST_DECISION_BLOCK = _new_section("Last Decision Summary Card", "Agent Status Header")


class TestOverallStatusPill:
    def test_pill_container_exists(self) -> None:
        assert "agentOverallStatusPill" in _TEMPLATE

    def test_pill_renders_label_from_summary(self) -> None:
        assert "sm.status_pill_label" in _PILL_BLOCK

    def test_pill_reads_color_from_summary(self) -> None:
        assert "sm.status_pill_color" in _PILL_BLOCK


class TestLogOnlyBadge:
    def test_badge_exists(self) -> None:
        assert "agentLogOnlyBadge" in _PILL_BLOCK

    def test_badge_text_is_log_only(self) -> None:
        assert "LOG_ONLY" in _PILL_BLOCK

    def test_badge_is_conditional_on_log_only(self) -> None:
        assert "{% if sm.log_only %}" in _PILL_BLOCK


class TestNoLiveSendText:
    def test_safe_text_renders(self) -> None:
        assert "sm.safe_text" in _PILL_BLOCK

    def test_safe_text_element_present(self) -> None:
        assert "agentLiveSafeText" in _PILL_BLOCK


class TestLastDecisionCard:
    def test_card_container_exists(self) -> None:
        assert "agentLastDecisionCard" in _TEMPLATE

    def test_card_heading(self) -> None:
        assert "Last decision" in _LAST_DECISION_BLOCK

    def test_card_shows_decision_id(self) -> None:
        assert "ld.decision_id" in _LAST_DECISION_BLOCK

    def test_card_shows_timestamp(self) -> None:
        assert "ld.timestamp" in _LAST_DECISION_BLOCK

    def test_card_shows_intent(self) -> None:
        assert "ld.intent" in _LAST_DECISION_BLOCK

    def test_card_shows_safety_flags(self) -> None:
        assert "ld.safety_flags" in _LAST_DECISION_BLOCK

    def test_card_shows_execution_mode(self) -> None:
        assert "ld.execution_mode" in _LAST_DECISION_BLOCK


class TestEmptyState:
    def test_empty_state_element_exists(self) -> None:
        assert "agentDecisionsEmptyState" in _LAST_DECISION_BLOCK

    def test_empty_state_text_present(self) -> None:
        # The exact Uzbek phrase lives in the dataclass default
        # (AgentControlSummary.empty_state_text) — the template renders
        # it via {{ sm.empty_state_text }}.
        assert "sm.empty_state_text" in _LAST_DECISION_BLOCK

    def test_empty_state_is_conditional(self) -> None:
        assert "{% else %}" in _LAST_DECISION_BLOCK


class TestRefreshButton:
    def test_refresh_button_exists(self) -> None:
        assert "agentRefreshButton" in _PILL_BLOCK

    def test_refresh_is_safe_get(self) -> None:
        assert 'href="/agent?hours=' in _PILL_BLOCK

    def test_refresh_does_not_use_post(self) -> None:
        # Read-only refresh: no POST form anywhere in the new sections.
        assert 'method="post"' not in _PILL_BLOCK.lower()
        assert 'method="post"' not in _LAST_DECISION_BLOCK.lower()


class TestReadOnlyGuarantees:
    def test_no_send_button_in_new_sections(self) -> None:
        for word in ("Yuborish", "Send live", "Send message", "yuborish"):
            assert word not in _PILL_BLOCK
            assert word not in _LAST_DECISION_BLOCK

    def test_no_flag_toggle_in_new_sections(self) -> None:
        # The existing template has previewSetting()/previewPreset() — our
        # new sections must NOT add any new toggle/apply handlers.
        for handler in (
            "previewSetting(",
            "previewPreset(",
            "applySetting(",
            "applyPreset(",
            "rollbackSetting(",
        ):
            assert handler not in _PILL_BLOCK
            assert handler not in _LAST_DECISION_BLOCK

    def test_no_token_or_session_hash_text(self) -> None:
        for needle in (
            "api_key",
            "bot_token",
            "session_hash",
            "system_prompt",
            "Bearer ",
        ):
            assert needle not in _PILL_BLOCK
            assert needle not in _LAST_DECISION_BLOCK

    def test_no_openai_or_telegram_calls_in_new_sections(self) -> None:
        for needle in ("openai.com", "api.telegram.org", "sendMessage"):
            assert needle not in _PILL_BLOCK
            assert needle not in _LAST_DECISION_BLOCK

    def test_summary_is_optional(self) -> None:
        # The new block wraps everything in `{% if sm %}` so the template
        # still renders if the route ever fails to build a summary.
        assert "{% if sm %}" in _TEMPLATE
