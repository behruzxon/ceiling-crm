"""Tests for Step CO — Price Calculator Bot Wiring."""
from __future__ import annotations

from pathlib import Path

from core.services.price_calculator_service import PriceCalculatorService

svc = PriceCalculatorService()


def _src() -> str:
    return Path(
        "apps/bot/handlers/private/ai_support.py",
    ).read_text(encoding="utf-8")


class TestWiringExists:
    def test_try_price_calculator_exists(self):
        assert "_try_price_calculator" in _src()

    def test_price_calculator_import(self):
        assert "PriceCalculatorService" in _src()

    def test_extract_and_respond_used(self):
        assert "extract_and_respond" in _src()

    def test_fallback_on_error(self):
        c = _src()
        assert "except Exception" in c


class TestPriceButtonPrompt:
    def test_prompt_unchanged(self):
        from apps.bot.handlers.private.ai_states import _AI_PRICE_PROMPT
        assert "5x4" in _AI_PRICE_PROMPT
        assert "20 kv" in _AI_PRICE_PROMPT


class TestDeterministicEstimate:
    def test_20kv_gulli(self):
        r = svc.extract_and_respond("20 kv gulli")
        assert r.estimate is not None
        assert r.estimate.total_uzs > 0

    def test_5x4_gulli(self):
        r = svc.extract_and_respond("5x4 gulli")
        assert r.estimate is not None
        assert r.estimate.area_m2 == 20.0

    def test_20kv_led(self):
        r = svc.extract_and_respond("20 kv led")
        assert r.estimate is not None
        assert r.estimate.design_key == "hi-tech"

    def test_20kv_hi_tech(self):
        r = svc.extract_and_respond("20 kv hi-tech")
        assert r.estimate is not None

    def test_area_only_asks_design(self):
        r = svc.extract_and_respond("20 kv xona")
        assert r.clarification is not None
        assert r.clarification.needs_design is True

    def test_design_only_asks_area(self):
        r = svc.extract_and_respond("gulli potolok")
        assert r.clarification is not None
        assert r.clarification.needs_area is True

    def test_invalid_area(self):
        r = svc.extract_and_respond("0.1 kv gulli")
        assert r.clarification is not None

    def test_huge_area(self):
        r = svc.extract_and_respond("999 kv gulli")
        assert r.clarification is not None


class TestResponseSafety:
    def test_taxminiy_in_response(self):
        r = svc.extract_and_respond("20 kv gulli")
        assert "taxminiy" in r.user_text.lower()

    def test_measurement_warning(self):
        r = svc.extract_and_respond("20 kv gulli")
        assert "o'lchov" in r.user_text.lower()

    def test_no_eng_arzon(self):
        r = svc.extract_and_respond("20 kv adnatonniy")
        assert "eng arzon" not in r.user_text.lower()

    def test_no_same_day(self):
        r = svc.extract_and_respond("20 kv gulli")
        assert "bugun qilamiz" not in r.user_text.lower()

    def test_no_token(self):
        r = svc.extract_and_respond("20 kv gulli")
        assert "sk-" not in r.user_text

    def test_no_final_guarantee(self):
        r = svc.extract_and_respond("20 kv gulli")
        assert "aniq narx" not in r.user_text.lower()


class TestMemoryPayload:
    def test_payload_created(self):
        r = svc.extract_and_respond("20 kv gulli")
        assert r.memory_payload is not None
        assert "last_price_area_m2" in r.memory_payload
        assert "last_price_design" in r.memory_payload
        assert "last_price_total" in r.memory_payload

    def test_payload_none_on_clarification(self):
        r = svc.extract_and_respond("salom")
        assert r.memory_payload is None


class TestExistingBehaviorPreserved:
    def test_ai_help_imports(self):
        from apps.bot.handlers.private.ai_states import _AI_HELP_TEXT
        assert "Narx" in _AI_HELP_TEXT

    def test_ai_keyboard(self):
        from apps.bot.handlers.private.ai_states import _ai_keyboard
        kb = _ai_keyboard()
        flat = [btn.text for row in kb.keyboard for btn in row]
        assert len(flat) == 6

    def test_dispatcher(self):
        from apps.bot.main import build_dispatcher
        assert build_dispatcher is not None

    def test_lead_scoring_preserved(self):
        assert "_add_lead_score" in _src()

    def test_stop_before_calculator(self):
        c = _src()
        lines = c.splitlines()
        obj_line = next(
            (i for i, ln in enumerate(lines) if "detect_objection" in ln), 0,
        )
        calc_line = next(
            (i for i, ln in enumerate(lines) if "_try_price_calculator" in ln and "def" not in ln),
            9999,
        )
        assert obj_line < calc_line
