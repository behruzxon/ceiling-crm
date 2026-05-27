"""Tests for Step CF — AI Button E2E Scenario Simulations.

These tests verify module wiring and detection chains
without real Telegram/OpenAI calls.
"""
from __future__ import annotations

from apps.bot.handlers.private.ai_detection import (
    _is_catalog_request,
    _is_measurement_request,
    _is_price_query,
    parse_combo,
)
from apps.bot.handlers.private.ai_scoring import (
    _OBJECTION_SCORE_DELTAS,
    classify_score,
    detect_objection,
    detect_objection_full,
)
from apps.bot.handlers.private.ai_support_auto_reply import (
    _detect_simple_intent,
)


class TestScenarioPriceFlow:
    """Scenario: user asks price -> provides area -> design -> operator."""

    def test_price_detected(self):
        assert _is_price_query("narx qancha")

    def test_area_parsed(self):
        combo = parse_combo("20 m2 hi tech")
        assert combo["area"] is not None
        assert combo["area"] == 20.0

    def test_design_parsed(self):
        combo = parse_combo("20 m2 hi tech")
        assert combo["design"] == "Hi Tech"

    def test_district_none_initially(self):
        combo = parse_combo("20 m2 hi tech")
        assert combo["district"] is None

    def test_district_detected(self):
        combo = parse_combo("Qarshi tumani 20 m2")
        assert combo["district"] is not None


class TestScenarioPriceObjection:
    """Scenario: price objection -> cheaper option."""

    def test_detect_expensive(self):
        assert detect_objection("qimmat ekan bu narx") == "expensive"

    def test_score_delta_positive(self):
        assert _OBJECTION_SCORE_DELTAS["expensive"] > 0

    def test_auto_reply_intent_price(self):
        assert _detect_simple_intent("narx qancha") == "price"


class TestScenarioTrustObjection:
    """Scenario: trust objection -> warranty/social proof."""

    def test_detect_trust(self):
        assert detect_objection("kafolat bormi") == "trust"

    def test_severity_low(self):
        result = detect_objection_full("kafolat bormi")
        assert result is not None
        assert result.severity == "low"


class TestScenarioStopRequest:
    """Scenario: stop request -> no follow-up."""

    def test_stop_detected(self):
        from core.services.followup_scheduler_service import _STOP_WORDS
        assert "kerak emas" in _STOP_WORDS

    def test_angry_objection(self):
        assert detect_objection("kerakmas") == "angry"

    def test_angry_score_delta(self):
        assert _OBJECTION_SCORE_DELTAS["angry"] < 0


class TestScenarioCyrillicPrice:
    """Scenario: Cyrillic price query -> signal."""

    def test_cyrillic_price(self):
        assert _is_price_query("нархи қанча")

    def test_auto_intent_none_cyrillic(self):
        result = _detect_simple_intent("нархи қанча")
        assert result is None or result == "price"


class TestScenarioPhoneShared:
    """Scenario: phone shared -> CRM update."""

    def test_score_classify_after_phone(self):
        score = 40 + 15  # price + phone
        assert classify_score(score) == "warm"

    def test_hot_after_full_funnel(self):
        score = 15 + 10 + 40  # price + district + phone
        assert classify_score(score) == "hot"


class TestScenarioSafetyChecks:
    def test_no_double_reply_design(self):
        intent = _detect_simple_intent("narx")
        assert intent == "price"
        obj = detect_objection("narx")
        assert obj is None

    def test_catalog_not_price(self):
        assert _is_catalog_request("katalog ko'rsat")
        assert not _is_price_query("katalog ko'rsat")

    def test_measurement_not_catalog(self):
        assert _is_measurement_request("zakaz qilmoqchiman")


class TestScenarioOpenAIFailSafe:
    def test_failsafe_text_exists(self):
        from apps.bot.handlers.private.ai_states import _FAILSAFE_TEXT
        assert len(_FAILSAFE_TEXT) > 20
        assert "operator" in _FAILSAFE_TEXT.lower()

    def test_failsafe_kb_has_button(self):
        from apps.bot.handlers.private.ai_states import _FAILSAFE_KB
        assert len(_FAILSAFE_KB.inline_keyboard) > 0


class TestScenarioCRMFailSafe:
    def test_scoring_functions_never_raise(self):
        assert classify_score(-10) == "cold"
        assert classify_score(200) == "hot"

    def test_objection_on_empty_safe(self):
        assert detect_objection("") is None
        assert detect_objection_full("") is None
