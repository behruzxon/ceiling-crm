"""Tests for Step CF — AI FSM / Conversation Flow."""
from __future__ import annotations

from apps.bot.handlers.private.ai_detection import (
    _detect_room_type,
    _is_greeting,
    _normalize_room,
    _room_design_text,
    is_valid_name,
    normalize_name,
)
from apps.bot.handlers.private.ai_states import (
    _CANCEL_PHONE,
    _EXIT_TEXTS,
    _NEUTRAL_REPLY,
    _PRICE_ASK_AREA_TEXT,
    _PRICE_ASK_DESIGN_TEXT,
    _ai_keyboard,
    _phone_request_keyboard,
)


class TestNameValidation:
    def test_valid_name(self):
        assert is_valid_name("Botir")

    def test_valid_two_words(self):
        assert is_valid_name("Botir Karimov")

    def test_reject_empty(self):
        assert not is_valid_name("")

    def test_reject_digits(self):
        assert not is_valid_name("Bot1r")

    def test_reject_keyword_zakaz(self):
        assert not is_valid_name("zakaz")

    def test_reject_keyword_narx(self):
        assert not is_valid_name("narx")

    def test_reject_too_long(self):
        assert not is_valid_name("A" * 50)

    def test_reject_too_many_words(self):
        assert not is_valid_name("one two three four")


class TestNameNormalization:
    def test_strip_whitespace(self):
        assert normalize_name("  botir  ") == "Botir"

    def test_title_case(self):
        assert normalize_name("botir karimov") == "Botir Karimov"


class TestGreetingDetection:
    def test_salom(self):
        assert _is_greeting("salom")

    def test_assalomu_alaykum(self):
        assert _is_greeting("assalomu alaykum")

    def test_hello(self):
        assert _is_greeting("hello")

    def test_cyrillic_greeting(self):
        assert _is_greeting("ассалому алайкум")

    def test_not_greeting(self):
        assert not _is_greeting("narx qancha")

    def test_greeting_with_trailing(self):
        assert _is_greeting("salom, qanday hollar")


class TestRoomDetection:
    def test_mehmonxona(self):
        assert _detect_room_type("mehmonxona uchun") == "mehmonxona"

    def test_zal(self):
        assert _detect_room_type("zal uchun") == "mehmonxona"

    def test_oshxona(self):
        assert _detect_room_type("oshxona uchun") == "oshxona"

    def test_hammom(self):
        assert _detect_room_type("hammom uchun") == "hammom"

    def test_yotoqxona(self):
        assert _detect_room_type("yotoqxona uchun") == "yotoqxona"

    def test_unknown(self):
        assert _detect_room_type("narx qancha") == "unknown"


class TestRoomDesignText:
    def test_mehmonxona_designs(self):
        text = _room_design_text("mehmonxona")
        assert "Gulli" in text
        assert "Hi Tech" in text

    def test_oshxona_designs(self):
        text = _room_design_text("oshxona")
        assert "namlik" in text.lower() or "Hi Tech" in text

    def test_hammom_designs(self):
        text = _room_design_text("hammom")
        assert "namlik" in text.lower() or "chidamli" in text.lower()

    def test_unknown_room_fallback(self):
        text = _room_design_text("other")
        assert "Mramor" in text or "Gulli" in text


class TestRoomNormalization:
    def test_zal_to_mehmonxona(self):
        result = _normalize_room("zal uchun kerak")
        assert "mehmonxona" in result

    def test_vanna_to_hammom(self):
        result = _normalize_room("vanna uchun")
        assert "hammom" in result


class TestStateConstants:
    def test_exit_texts(self):
        assert len(_EXIT_TEXTS) >= 2

    def test_cancel_phone(self):
        assert "Bekor" in _CANCEL_PHONE

    def test_neutral_reply(self):
        assert "narx" in _NEUTRAL_REPLY.lower() or "katalog" in _NEUTRAL_REPLY.lower()

    def test_price_ask_area(self):
        assert "m²" in _PRICE_ASK_AREA_TEXT or "m2" in _PRICE_ASK_AREA_TEXT

    def test_price_ask_design(self):
        assert "Hi Tech" in _PRICE_ASK_DESIGN_TEXT
        assert "Gulli" in _PRICE_ASK_DESIGN_TEXT


class TestKeyboards:
    def test_ai_keyboard_has_menu(self):
        kb = _ai_keyboard()
        flat = [btn.text for row in kb.keyboard for btn in row]
        assert any("Menyu" in t for t in flat)

    def test_phone_keyboard_has_contact(self):
        kb = _phone_request_keyboard()
        flat = [btn for row in kb.keyboard for btn in row]
        contact_btns = [b for b in flat if b.request_contact]
        assert len(contact_btns) >= 1

    def test_phone_keyboard_has_cancel(self):
        kb = _phone_request_keyboard()
        flat = [btn.text for row in kb.keyboard for btn in row]
        assert any("Bekor" in t for t in flat)
