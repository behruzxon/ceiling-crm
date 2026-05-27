"""Tests for Step CN — Price Knowledge Consistency."""

from __future__ import annotations

from pathlib import Path

from core.services.price_calculator_service import PriceCalculatorService
from shared.constants.pricing import DESIGN_PRICES_CUSTOMER

svc = PriceCalculatorService()


def _uz() -> str:
    return Path("shared/knowledge/uz.md").read_text(encoding="utf-8")


def _prompt() -> str:
    return Path("apps/bot/ai/system_prompt.py").read_text(encoding="utf-8")


class TestCalculatorMatchesCustomerPrices:
    def test_adnatonniy(self):
        assert svc.get_rate("adnatonniy") == DESIGN_PRICES_CUSTOMER["adnatonniy"]

    def test_gulli(self):
        assert svc.get_rate("gulli") == DESIGN_PRICES_CUSTOMER["gulli"]

    def test_hi_tech(self):
        assert svc.get_rate("hi-tech") == DESIGN_PRICES_CUSTOMER["hi-tech"]

    def test_mramor(self):
        assert svc.get_rate("mramor") == DESIGN_PRICES_CUSTOMER["mramor"]

    def test_qora_uf(self):
        assert svc.get_rate("qora uf") == DESIGN_PRICES_CUSTOMER["qora uf"]

    def test_kosmos(self):
        assert svc.get_rate("kosmos") == DESIGN_PRICES_CUSTOMER["kosmos"]

    def test_osmon(self):
        assert svc.get_rate("osmon") == DESIGN_PRICES_CUSTOMER["osmon"]


class TestUzMdMatchesCustomer:
    def test_gulli_130k(self):
        assert "130 000" in _uz()

    def test_odnotonniy_80k(self):
        assert "80 000" in _uz()

    def test_hi_tech_120k(self):
        c = _uz()
        lines = [ln for ln in c.splitlines() if "Hi-tech" in ln]
        assert any("120 000" in ln for ln in lines)

    def test_qora_140k(self):
        assert "140 000" in _uz()


class TestPromptSafety:
    def test_taxminiy_in_prompt(self):
        assert "taxminiy" in _prompt().lower()

    def test_final_after_measurement(self):
        assert "o'lchovdan keyin" in _prompt().lower()

    def test_no_aniq_narx_claim(self):
        c = _prompt().lower()
        assert "aniq narx" in c and "dema" in c

    def test_no_eng_arzon(self):
        c = _prompt().lower()
        assert "eng arzon" in c

    def test_no_internal_leak(self):
        c = _prompt()
        assert "DEFAULT_BASE_PRICES" not in c
        assert "250000" not in c
        assert "300000" not in c


class TestCalculatorResponseSafety:
    def test_estimate_marked(self):
        r = svc.calculate_estimate(20.0, "gulli")
        assert r.is_estimate is True

    def test_response_taxminiy(self):
        r = svc.calculate_estimate(20.0, "gulli")
        text = svc.build_user_response(r)
        assert "taxminiy" in text.lower()

    def test_no_eng_arzon_response(self):
        r = svc.calculate_estimate(20.0, "adnatonniy")
        text = svc.build_user_response(r)
        assert "eng arzon" not in text.lower()

    def test_no_fake_discount(self):
        r = svc.calculate_estimate(15.0, "gulli")
        text = svc.build_user_response(r)
        assert "maxsus chegirma" not in text.lower()

    def test_no_same_day(self):
        r = svc.calculate_estimate(20.0, "gulli")
        text = svc.build_user_response(r)
        assert "bugun qilamiz" not in text.lower()


class TestDocExists:
    def test_price_doc(self):
        p = "docs/AI_AGENT_SYSTEM/100_PRICE_CALCULATOR_SOURCE_OF_TRUTH.md"
        assert Path(p).exists()

    def test_doc_mentions_customer_facing(self):
        p = "docs/AI_AGENT_SYSTEM/100_PRICE_CALCULATOR_SOURCE_OF_TRUTH.md"
        c = Path(p).read_text(encoding="utf-8")
        assert "customer" in c.lower() or "CUSTOMER" in c
