"""Tests for Step CF — AI Multilingual & Fuzzy Cases."""

from __future__ import annotations

from apps.bot.handlers.private.ai_detection import (
    _is_catalog_request,
    _is_measurement_request,
    _is_price_query,
)
from apps.bot.handlers.private.ai_scoring import (
    detect_objection,
    detect_objection_full,
)


class TestCyrillicUzbek:
    def test_narxi_qancha(self):
        assert _is_price_query("нархи қанча")

    def test_cyrillic_expensive(self):
        assert detect_objection("қиммат") == "expensive"

    def test_cyrillic_trust(self):
        assert detect_objection("ишонмайман") == "trust"

    def test_cyrillic_delay(self):
        assert detect_objection("кейинроқ") == "delay"

    def test_cyrillic_catalog(self):
        assert _is_catalog_request("каталог кўрсат")

    def test_cyrillic_measurement(self):
        assert _is_measurement_request("ўлчов керак")

    def test_cyrillic_compare(self):
        assert detect_objection("арзонроқ") == "compare"

    def test_cyrillic_angry(self):
        assert detect_objection("керакмас") == "angry"


class TestRussian:
    def test_skolko_stoit(self):
        assert _is_price_query("сколько стоит")

    def test_dorogo(self):
        assert detect_objection("дорого") == "expensive"

    def test_dorogo_ochen(self):
        result = detect_objection_full("очень дорого")
        assert result is not None
        assert result.objection_type == "expensive"

    def test_ne_veriu(self):
        assert detect_objection("не верю") == "trust"

    def test_potom(self):
        assert detect_objection("потом") == "delay"

    def test_deshevle(self):
        assert detect_objection("дешевле") == "compare"


class TestFuzzyVariants:
    def test_qimmatda(self):
        result = detect_objection_full("qimmatda bu narx")
        assert result is not None
        assert result.objection_type == "expensive"

    def test_qimmatroq(self):
        result = detect_objection_full("qimmatroq ekan")
        assert result is not None
        assert result.objection_type == "expensive"

    def test_pulim_yetmayapti(self):
        result = detect_objection_full("pulim yetmayapti")
        assert result is not None
        assert result.objection_type == "expensive"

    def test_oylash_variant(self):
        result = detect_objection_full("o'ylab ko'raman")
        assert result is not None
        assert result.objection_type == "delay"

    def test_narx_baland(self):
        result = detect_objection_full("narx baland ekan")
        assert result is not None
        assert result.objection_type == "expensive"


class TestMixedInput:
    def test_area_with_cyrillic(self):
        assert _is_price_query("20 kv нарх")

    def test_emoji_only_safe(self):
        assert not _is_price_query("😊")
        assert detect_objection("😊") is None

    def test_short_ok_no_objection(self):
        assert detect_objection("ok") is None

    def test_single_char_safe(self):
        assert detect_objection("a") is None
        assert not _is_price_query("a")

    def test_empty_string_safe(self):
        assert detect_objection("") is None
        assert not _is_price_query("")


class TestDesignNamesCrossLanguage:
    def test_gulli_detected(self):
        from apps.bot.handlers.private.ai_detection import (
            _extract_design_from_text,
        )

        assert _extract_design_from_text("gulli potolok") == "Gulli"

    def test_hi_tech_detected(self):
        from apps.bot.handlers.private.ai_detection import (
            _extract_design_from_text,
        )

        assert _extract_design_from_text("hi tech dizayn") == "Hi Tech"

    def test_mramor_detected(self):
        from apps.bot.handlers.private.ai_detection import (
            _extract_design_from_text,
        )

        assert _extract_design_from_text("mramor kerak") == "Mramor"

    def test_osmon_detected(self):
        from apps.bot.handlers.private.ai_detection import (
            _extract_design_from_text,
        )

        assert _extract_design_from_text("osmon dizayni") == "Osmon"

    def test_no_design(self):
        from apps.bot.handlers.private.ai_detection import (
            _extract_design_from_text,
        )

        assert _extract_design_from_text("salom dunyo") is None
