"""Tests for the CRM Conversation Inbox web page + operator composer."""

from __future__ import annotations

from pathlib import Path

_TPL = "apps/web/templates/crm_conversations.html"


def _t() -> str:
    return Path(_TPL).read_text(encoding="utf-8")


def _base() -> str:
    return Path("apps/web/templates/base.html").read_text(encoding="utf-8")


def _main() -> str:
    return Path("apps/web/main.py").read_text(encoding="utf-8")


def _detail() -> str:
    return Path("apps/web/templates/crm_contact_detail.html").read_text(encoding="utf-8")


class TestRoute:
    def test_route(self):
        assert "/crm/inbox" in _main()

    def test_handler(self):
        assert "crm_inbox" in _main()

    def test_template_exists(self):
        assert Path(_TPL).exists()

    def test_calls_conversations_api(self):
        assert "/api/v1/admin/crm/conversations" in _main()

    def test_calls_messages_api(self):
        assert "/conversations/{contact_id}/messages" in _main() or "/messages" in _main()

    def test_passes_send_enabled(self):
        assert "operator_web_send_enabled" in _main()
        assert "send_enabled" in _main()


class TestSidebar:
    def test_sidebar_link(self):
        assert "/crm/inbox" in _base()

    def test_active_highlight(self):
        assert "active_page == 'inbox'" in _base()

    def test_topbar_title(self):
        assert "Conversation Inbox" in _base()


class TestActivePage:
    def test_active_page(self):
        assert 'active_page = "inbox"' in _t()


class TestConversationList:
    def test_list_iter(self):
        assert "conversations" in _t()

    def test_search(self):
        assert "convSearch" in _t()

    def test_shows_preview(self):
        assert "last_message_preview" in _t()

    def test_shows_temperature_badge(self):
        assert "vp-badge-danger" in _t() or "hot" in _t()

    def test_links_to_contact(self):
        assert "/crm/inbox?contact_id=" in _t()

    def test_empty_state_list(self):
        assert "vp-empty-state" in _t()


class TestTimeline:
    def test_timeline(self):
        assert "vp-timeline" in _t()

    def test_messages_iter(self):
        assert "messages" in _t()

    def test_inbound_vs_outbound(self):
        assert "inbound" in _t()

    def test_operator_styling(self):
        assert "operator" in _t().lower()

    def test_timestamps(self):
        assert "created_at" in _t()

    def test_empty_state_timeline(self):
        assert "xabarlar yo'q" in _t()


class TestContactInfo:
    def test_phone_masked(self):
        assert "phone_masked" in _t()

    def test_lead_status(self):
        assert "lead_status" in _t()

    def test_district(self):
        assert "district" in _t()

    def test_link_to_contact_page(self):
        assert "/crm/{{ active_contact_id }}" in _t()


class TestComposer:
    def test_composer_present(self):
        assert "composer" in _t()

    def test_send_enabled_branch(self):
        assert "send_enabled" in _t()

    def test_textarea_when_enabled(self):
        assert "replyText" in _t()

    def test_char_count(self):
        assert "charCount" in _t()

    def test_send_button_when_enabled(self):
        assert "sendReply(" in _t()

    def test_confirmation_before_send(self):
        assert "confirm(" in _t()

    def test_posts_to_operator_reply_api(self):
        assert "/operator-reply" in _t()

    def test_send_uses_confirm_send_true(self):
        assert "confirm_send: true" in _t()


class TestSendDisabledState:
    def test_disabled_notice_when_off(self):
        # When send_enabled is false the template shows a disabled notice + flag.
        s = _t()
        assert "send disabled" in s.lower() or "o'chirilgan" in s.lower()
        assert "OPERATOR_WEB_SEND_ENABLED" in s

    def test_no_textarea_when_disabled(self):
        # The textarea/send only render inside the send_enabled branch.
        s = _t()
        assert "{% if send_enabled %}" in s
        assert "{% else %}" in s


class TestNoForbiddenActions:
    def test_no_bulk(self):
        assert "bulk" not in _t().lower()

    def test_no_campaign(self):
        assert "campaign" not in _t().lower()

    def test_no_auto_send(self):
        assert "auto_send" not in _t().lower()

    def test_no_hidden_send_when_disabled(self):
        # Exactly one send *button* (onclick), rendered only inside the
        # send_enabled branch; the JS function definition is harmless when off.
        s = _t()
        assert s.count('onclick="sendReply(') == 1


class TestSafety:
    def test_no_token(self):
        assert "sk-" not in _t()

    def test_no_raw_chat_id_exposed(self):
        assert "telegram_chat_id" not in _t()


class TestContactDetailLink:
    def test_detail_links_to_inbox(self):
        assert "/crm/inbox?contact_id=" in _detail()


class TestMobile:
    def test_responsive(self):
        assert "@media" in _t() or "max-width" in _t()


class TestSmoke:
    def test_web_app(self):
        from apps.web.main import app

        assert app is not None

    def test_template_parses(self):
        from jinja2 import Environment, FileSystemLoader

        env = Environment(loader=FileSystemLoader("apps/web/templates"))
        assert env.get_template("crm_conversations.html") is not None
