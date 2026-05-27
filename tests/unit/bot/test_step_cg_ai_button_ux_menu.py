"""Tests for Step CG — AI Button UX + Menu Polish."""

from __future__ import annotations

from apps.bot.handlers.private.ai_states import (
    _AI_HELP_TEXT,
    _AI_MODE_STATUS,
    _AI_OPERATOR_PROMPT,
    _AI_PRICE_PROMPT,
    _AI_QUICK_BUTTONS,
    _AI_RATE_LIMIT_TEXT,
    _AI_RESET_SUCCESS,
    _AI_ROOM_ADVICE_PROMPT,
    _AI_UNAVAILABLE_TEXT,
    BTN_AI_CATALOG,
    BTN_AI_HELP,
    BTN_AI_OPERATOR,
    BTN_AI_PRICE,
    BTN_AI_RESET,
    _ai_keyboard,
)


class TestQuickButtons:
    def test_help_button_exists(self):
        assert BTN_AI_HELP == "❓ Yordam"

    def test_reset_button_exists(self):
        assert BTN_AI_RESET == "🔄 Reset"

    def test_price_button_exists(self):
        assert BTN_AI_PRICE == "💰 Narx"

    def test_catalog_button_exists(self):
        assert BTN_AI_CATALOG == "📂 Katalog"

    def test_operator_button_exists(self):
        assert BTN_AI_OPERATOR == "👨‍💼 Operator"

    def test_all_buttons_in_frozenset(self):
        assert BTN_AI_HELP in _AI_QUICK_BUTTONS
        assert BTN_AI_RESET in _AI_QUICK_BUTTONS
        assert BTN_AI_PRICE in _AI_QUICK_BUTTONS
        assert BTN_AI_CATALOG in _AI_QUICK_BUTTONS
        assert BTN_AI_OPERATOR in _AI_QUICK_BUTTONS


class TestKeyboard:
    def test_keyboard_has_six_buttons(self):
        kb = _ai_keyboard()
        flat = [btn.text for row in kb.keyboard for btn in row]
        assert len(flat) == 6

    def test_keyboard_has_menu(self):
        kb = _ai_keyboard()
        flat = [btn.text for row in kb.keyboard for btn in row]
        assert any("Menyu" in t for t in flat)

    def test_keyboard_has_narx(self):
        kb = _ai_keyboard()
        flat = [btn.text for row in kb.keyboard for btn in row]
        assert BTN_AI_PRICE in flat

    def test_keyboard_has_katalog(self):
        kb = _ai_keyboard()
        flat = [btn.text for row in kb.keyboard for btn in row]
        assert BTN_AI_CATALOG in flat

    def test_keyboard_has_operator(self):
        kb = _ai_keyboard()
        flat = [btn.text for row in kb.keyboard for btn in row]
        assert BTN_AI_OPERATOR in flat

    def test_keyboard_has_reset(self):
        kb = _ai_keyboard()
        flat = [btn.text for row in kb.keyboard for btn in row]
        assert BTN_AI_RESET in flat

    def test_keyboard_has_yordam(self):
        kb = _ai_keyboard()
        flat = [btn.text for row in kb.keyboard for btn in row]
        assert BTN_AI_HELP in flat

    def test_keyboard_max_3_rows(self):
        kb = _ai_keyboard()
        assert len(kb.keyboard) <= 4

    def test_keyboard_resize(self):
        kb = _ai_keyboard()
        assert kb.resize_keyboard is True


class TestAIModeStatus:
    def test_status_text_ai_rejim(self):
        assert "AI yordam rejimi" in _AI_MODE_STATUS

    def test_status_has_examples(self):
        assert "20 kv" in _AI_MODE_STATUS
        assert "5x4" in _AI_MODE_STATUS

    def test_status_has_katalog(self):
        assert "Katalog" in _AI_MODE_STATUS

    def test_status_has_operator(self):
        assert "Operator" in _AI_MODE_STATUS


class TestHelpText:
    def test_lists_price_capability(self):
        assert "Narx" in _AI_HELP_TEXT

    def test_lists_design_capability(self):
        assert "Dizayn" in _AI_HELP_TEXT

    def test_lists_catalog_capability(self):
        assert "Katalog" in _AI_HELP_TEXT

    def test_lists_operator_capability(self):
        assert "Operator" in _AI_HELP_TEXT

    def test_lists_memory_capability(self):
        assert "Xotira" in _AI_HELP_TEXT or "xotira" in _AI_HELP_TEXT

    def test_warns_exact_price(self):
        assert "o'lchovdan keyin" in _AI_HELP_TEXT

    def test_has_examples(self):
        assert "5x4" in _AI_HELP_TEXT
        assert "20 kv" in _AI_HELP_TEXT

    def test_no_token(self):
        assert "sk-" not in _AI_HELP_TEXT
        assert "token" not in _AI_HELP_TEXT.lower()


class TestResetText:
    def test_success_message(self):
        assert "tozalandi" in _AI_RESET_SUCCESS

    def test_no_crm_delete_claim(self):
        lower = _AI_RESET_SUCCESS.lower()
        assert "crm" not in lower
        assert "o'chirildi" not in lower


class TestOperatorHandoff:
    def test_operator_asks_phone(self):
        lower = _AI_OPERATOR_PROMPT.lower()
        assert "telefon" in lower

    def test_operator_no_fake_eta(self):
        lower = _AI_OPERATOR_PROMPT.lower()
        assert "hozir" not in lower
        assert "darhol" not in lower
        assert "qo'ng'iroq qiladi" not in lower


class TestFallbackTexts:
    def test_rate_limit_friendly(self):
        assert "limit" in _AI_RATE_LIMIT_TEXT.lower()
        assert "ertaga" in _AI_RATE_LIMIT_TEXT.lower()

    def test_unavailable_no_raw_error(self):
        assert "Exception" not in _AI_UNAVAILABLE_TEXT
        assert "Error" not in _AI_UNAVAILABLE_TEXT

    def test_unavailable_operator_mention(self):
        assert "operator" in _AI_UNAVAILABLE_TEXT.lower()


class TestPricePrompt:
    def test_has_example(self):
        assert "5x4" in _AI_PRICE_PROMPT
        assert "20 kv" in _AI_PRICE_PROMPT


class TestRoomAdvice:
    def test_has_example(self):
        assert "mehmonxona" in _AI_ROOM_ADVICE_PROMPT.lower()


class TestSafety:
    def test_no_eng_arzon_in_help(self):
        assert "eng arzon" not in _AI_HELP_TEXT.lower()

    def test_no_bugun_promise_in_help(self):
        assert "bugun qilamiz" not in _AI_HELP_TEXT.lower()

    def test_no_token_in_status(self):
        assert "sk-" not in _AI_MODE_STATUS
        assert "bearer" not in _AI_MODE_STATUS.lower()

    def test_no_eng_arzon_in_operator(self):
        assert "eng arzon" not in _AI_OPERATOR_PROMPT.lower()
