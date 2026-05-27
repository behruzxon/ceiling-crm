"""Tests for Step CG — AI Button UX Flow Integration."""
from __future__ import annotations

from pathlib import Path

from apps.bot.handlers.private.ai_states import (
    _AI_HELP_TEXT,
    _AI_MODE_STATUS,
    _AI_OPERATOR_PROMPT,
    _AI_PRICE_PROMPT,
    _AI_RESET_SUCCESS,
    _AI_UNAVAILABLE_TEXT,
    _ai_keyboard,
)


class TestAIEntryShowsStatus:
    def test_status_text_exists(self):
        assert "AI yordam rejimi" in _AI_MODE_STATUS

    def test_keyboard_has_buttons(self):
        kb = _ai_keyboard()
        flat = [btn.text for row in kb.keyboard for btn in row]
        assert len(flat) >= 6


class TestAiHelpFlow:
    def test_help_shows_capabilities(self):
        assert "Narx" in _AI_HELP_TEXT
        assert "Katalog" in _AI_HELP_TEXT
        assert "Operator" in _AI_HELP_TEXT

    def test_help_shows_warning(self):
        assert "o'lchovdan keyin" in _AI_HELP_TEXT

    def test_help_no_secrets(self):
        assert "sk-" not in _AI_HELP_TEXT
        assert "BOT_TOKEN" not in _AI_HELP_TEXT


class TestAiResetFlow:
    def test_reset_success_text(self):
        assert "tozalandi" in _AI_RESET_SUCCESS

    def test_reset_handler_uses_clear(self):
        c = Path(
            "apps/bot/handlers/private/ai_support.py",
        ).read_text(encoding="utf-8")
        assert "clear_ai_conversation" in c

    def test_reset_preserves_crm(self):
        lower = _AI_RESET_SUCCESS.lower()
        assert "o'chirildi" not in lower
        assert "delete" not in lower


class TestPriceQuickButton:
    def test_price_prompt_has_example(self):
        assert "5x4" in _AI_PRICE_PROMPT
        assert "20 kv" in _AI_PRICE_PROMPT


class TestOperatorQuickButton:
    def test_operator_asks_phone(self):
        assert "telefon" in _AI_OPERATOR_PROMPT.lower()

    def test_operator_no_fake_promise(self):
        lower = _AI_OPERATOR_PROMPT.lower()
        assert "hozir" not in lower
        assert "darhol" not in lower


class TestFallbackNoRawError:
    def test_unavailable_no_exception(self):
        assert "Exception" not in _AI_UNAVAILABLE_TEXT
        assert "Traceback" not in _AI_UNAVAILABLE_TEXT

    def test_unavailable_friendly(self):
        assert "operator" in _AI_UNAVAILABLE_TEXT.lower()


class TestNoRealCalls:
    def test_no_openai_import_in_states(self):
        c = Path(
            "apps/bot/handlers/private/ai_states.py",
        ).read_text(encoding="utf-8")
        assert "openai" not in c.lower()

    def test_no_telegram_send_in_states(self):
        c = Path(
            "apps/bot/handlers/private/ai_states.py",
        ).read_text(encoding="utf-8")
        assert "send_message" not in c


class TestNoTokenLeak:
    def test_no_token_in_any_text(self):
        for text in [
            _AI_HELP_TEXT, _AI_MODE_STATUS, _AI_RESET_SUCCESS,
            _AI_PRICE_PROMPT, _AI_OPERATOR_PROMPT, _AI_UNAVAILABLE_TEXT,
        ]:
            assert "sk-" not in text
            assert "BOT_TOKEN" not in text


class TestPriorStepsStillPass:
    def test_ai_support_import(self):
        from apps.bot.handlers.private import ai_support
        assert ai_support is not None

    def test_dispatcher_builds(self):
        from apps.bot.main import build_dispatcher
        assert build_dispatcher is not None

    def test_scheduler_imports(self):
        import apps.scheduler.main
        assert apps.scheduler.main is not None
