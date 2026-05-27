"""Tests for Step CG — AI Commands (/ai_help, /ai_reset, quick buttons)."""
from __future__ import annotations

from pathlib import Path


def _src() -> str:
    return Path(
        "apps/bot/handlers/private/ai_support.py",
    ).read_text(encoding="utf-8")


class TestAiHelpCommand:
    def test_handler_importable(self):
        from apps.bot.handlers.private.ai_support import cmd_ai_help
        assert callable(cmd_ai_help)

    def test_handler_registered(self):
        c = _src()
        assert "cmd_ai_help" in c
        assert 'Command("ai_help")' in c

    def test_returns_help_text(self):
        c = _src()
        assert "_AI_HELP_TEXT" in c

    def test_bot_command_registered(self):
        c = Path("apps/bot/main.py").read_text(encoding="utf-8")
        assert "ai_help" in c


class TestAiResetCommand:
    def test_handler_importable(self):
        from apps.bot.handlers.private.ai_support import cmd_ai_reset
        assert callable(cmd_ai_reset)

    def test_handler_registered(self):
        c = _src()
        assert "cmd_ai_reset" in c
        assert 'Command("ai_reset")' in c

    def test_calls_clear_conversation(self):
        c = _src()
        assert "clear_ai_conversation" in c

    def test_returns_success_text(self):
        c = _src()
        assert "_AI_RESET_SUCCESS" in c

    def test_bot_command_registered(self):
        c = Path("apps/bot/main.py").read_text(encoding="utf-8")
        assert "ai_reset" in c

    def test_re_enters_ai_mode(self):
        c = _src()
        lines = c.split("\n")
        in_reset = False
        found_set_state = False
        for line in lines:
            if "cmd_ai_reset" in line:
                in_reset = True
            if in_reset and "waiting_for_ai_question" in line:
                found_set_state = True
                break
        assert found_set_state


class TestQuickButtonHandlers:
    def test_help_btn_handler(self):
        c = _src()
        assert "handle_ai_help_btn" in c
        assert "BTN_AI_HELP" in c

    def test_reset_btn_handler(self):
        c = _src()
        assert "handle_ai_reset_btn" in c
        assert "BTN_AI_RESET" in c

    def test_price_btn_handler(self):
        c = _src()
        assert "handle_ai_price_btn" in c
        assert "BTN_AI_PRICE" in c

    def test_catalog_btn_handler(self):
        c = _src()
        assert "handle_ai_catalog_btn" in c
        assert "BTN_AI_CATALOG" in c

    def test_operator_btn_handler(self):
        c = _src()
        assert "handle_ai_operator_btn" in c
        assert "BTN_AI_OPERATOR" in c

    def test_price_btn_shows_prompt(self):
        c = _src()
        assert "_AI_PRICE_PROMPT" in c

    def test_operator_btn_shows_prompt(self):
        c = _src()
        assert "_AI_OPERATOR_PROMPT" in c

    def test_catalog_btn_shows_catalog(self):
        c = _src()
        assert "catalog_list_keyboard" in c


class TestRateLimitText:
    def test_rate_limit_uses_constant(self):
        c = _src()
        assert "_AI_RATE_LIMIT_TEXT" in c

    def test_no_hardcoded_limit_message(self):
        c = _src()
        assert "Kunlik AI limit tugadi" not in c


class TestExportCompatibility:
    def test_router(self):
        from apps.bot.handlers.private.ai_support import router
        assert router is not None

    def test_states(self):
        from apps.bot.handlers.private.ai_support import AiSupportStates
        assert AiSupportStates is not None

    def test_load_memory(self):
        from apps.bot.handlers.private.ai_support import _load_ai_memory
        assert callable(_load_ai_memory)

    def test_get_lead_score(self):
        from apps.bot.handlers.private.ai_support import _get_lead_score
        assert callable(_get_lead_score)

    def test_add_lead_score(self):
        from apps.bot.handlers.private.ai_support import _add_lead_score
        assert callable(_add_lead_score)

    def test_clear_conversation(self):
        from apps.bot.handlers.private.ai_support import (
            clear_ai_conversation,
        )
        assert callable(clear_ai_conversation)

    def test_cmd_ai_start(self):
        from apps.bot.handlers.private.ai_support import cmd_ai_start
        assert callable(cmd_ai_start)

    def test_cmd_ai_help(self):
        from apps.bot.handlers.private.ai_support import cmd_ai_help
        assert callable(cmd_ai_help)

    def test_cmd_ai_reset(self):
        from apps.bot.handlers.private.ai_support import cmd_ai_reset
        assert callable(cmd_ai_reset)


class TestSmoke:
    def test_dispatcher_builds(self):
        from apps.bot.main import build_dispatcher
        assert build_dispatcher is not None

    def test_ai_support_imports(self):
        from apps.bot.handlers.private import ai_support
        assert ai_support is not None
