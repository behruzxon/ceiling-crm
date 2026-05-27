"""Tests for conversation replay in contact detail template — Step 6."""

from __future__ import annotations

from pathlib import Path

TEMPLATE_PATH = Path("apps/web/templates/crm_contact_detail.html")


def _read_template() -> str:
    assert TEMPLATE_PATH.exists(), f"Template not found: {TEMPLATE_PATH}"
    return TEMPLATE_PATH.read_text(encoding="utf-8")


class TestConversationReplaySection:
    def test_template_exists(self) -> None:
        assert TEMPLATE_PATH.exists()

    def test_has_conversation_replay_title(self) -> None:
        content = _read_template()
        assert "Conversation Replay" in content

    def test_has_replay_card(self) -> None:
        content = _read_template()
        assert "conversationReplay" in content

    def test_has_replay_timeline(self) -> None:
        content = _read_template()
        assert "replayTimeline" in content

    def test_has_empty_state(self) -> None:
        content = _read_template()
        assert "replayEmpty" in content
        assert "yetarli voqea" in content.lower() or "voqea yo" in content.lower()


class TestReplayBadges:
    def test_user_badge(self) -> None:
        content = _read_template()
        assert "replayUserBadge" in content

    def test_bot_badge(self) -> None:
        content = _read_template()
        assert "replayBotBadge" in content

    def test_price_badge(self) -> None:
        content = _read_template()
        assert "replayPriceBadge" in content

    def test_objection_badge(self) -> None:
        content = _read_template()
        assert "replayObjectionBadge" in content

    def test_handoff_badge(self) -> None:
        content = _read_template()
        assert "replayHandoffBadge" in content

    def test_stop_badge(self) -> None:
        content = _read_template()
        assert "replayStopBadge" in content

    def test_total_badge(self) -> None:
        content = _read_template()
        assert "replayTotalBadge" in content


class TestReplayCSSClasses:
    def test_replay_event_icon_user(self) -> None:
        content = _read_template()
        assert "replay-event-icon-user" in content

    def test_replay_event_icon_bot(self) -> None:
        content = _read_template()
        assert "replay-event-icon-bot" in content

    def test_replay_event_icon_ai(self) -> None:
        content = _read_template()
        assert "replay-event-icon-ai" in content

    def test_replay_event_icon_operator(self) -> None:
        content = _read_template()
        assert "replay-event-icon-operator" in content

    def test_replay_event_icon_system(self) -> None:
        content = _read_template()
        assert "replay-event-icon-system" in content

    def test_replay_timeline_css(self) -> None:
        content = _read_template()
        assert ".replay-timeline" in content

    def test_replay_event_css(self) -> None:
        content = _read_template()
        assert ".replay-event" in content

    def test_replay_event_preview_css(self) -> None:
        content = _read_template()
        assert ".replay-event-preview" in content

    def test_replay_severity_warning_css(self) -> None:
        content = _read_template()
        assert ".replay-severity-warning" in content

    def test_replay_severity_info_css(self) -> None:
        content = _read_template()
        assert ".replay-severity-info" in content

    def test_replay_severity_danger_css(self) -> None:
        content = _read_template()
        assert ".replay-severity-danger" in content


class TestReplaySummary:
    def test_summary_section(self) -> None:
        content = _read_template()
        assert "replaySummary" in content

    def test_next_action_element(self) -> None:
        content = _read_template()
        assert "replayNextAction" in content

    def test_event_count_element(self) -> None:
        content = _read_template()
        assert "replayEventCount" in content


class TestReplayJS:
    def test_load_replay_function(self) -> None:
        content = _read_template()
        assert "loadReplay" in content

    def test_render_replay_function(self) -> None:
        content = _read_template()
        assert "renderReplay" in content

    def test_replay_icon_map(self) -> None:
        content = _read_template()
        assert "REPLAY_ICON_MAP" in content

    def test_actor_css_map(self) -> None:
        content = _read_template()
        assert "ACTOR_CSS" in content

    def test_fetches_api_endpoint(self) -> None:
        content = _read_template()
        assert "/conversation-replay" in content


class TestReplaySecurity:
    def test_no_raw_json_dump(self) -> None:
        content = _read_template()
        assert "JSON.stringify" not in content or "JSON.stringify({text" in content

    def test_no_token_in_template(self) -> None:
        content = _read_template()
        assert "sk-" not in content
        assert "BOT_TOKEN" not in content

    def test_no_openai_key(self) -> None:
        content = _read_template()
        assert "OPENAI_API_KEY" not in content

    def test_no_database_url(self) -> None:
        content = _read_template()
        assert "postgresql://" not in content

    def test_uses_vp_card(self) -> None:
        content = _read_template()
        assert "vp-card" in content

    def test_uses_vp_badge(self) -> None:
        content = _read_template()
        assert "vp-badge" in content


class TestReplayResponsive:
    def test_mobile_breakpoint(self) -> None:
        content = _read_template()
        assert "@media" in content
        assert "768px" in content

    def test_replay_before_chat_timeline(self) -> None:
        content = _read_template()
        replay_pos = content.find("conversationReplay")
        timeline_pos = content.find("chatTimeline")
        assert replay_pos < timeline_pos
