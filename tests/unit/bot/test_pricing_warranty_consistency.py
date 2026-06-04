"""Regression: customer-facing PRICE and WARRANTY must stay consistent.

Closes the P1 deploy-readiness gaps:

* Price — the FSM calculator keyboard (``DESIGN_BY_KEY``), the AI knowledge
  base actually loaded by the system prompt (``apps/bot/ai/knowledge/uz.md``),
  and the system prompt itself disagreed with the documented source of truth
  ``DESIGN_PRICES_CUSTOMER`` for Gulli (130k) and Hi-tech (120k). They were
  swapped in the calculator/KB.
* Warranty — the Standard & Premium package cards advertised "10 yil kafolat"
  while every other surface (KB, prompt, detectors) promises "15 yil".

Source of truth:
  - Prices  → shared.constants.pricing.DESIGN_PRICES_CUSTOMER
  - Warranty → "15 yil" (flat)

Offline: constant + file-content introspection only — no DB/Redis/Telegram/OpenAI.
"""

from __future__ import annotations

from pathlib import Path

from apps.bot.handlers.private.ai_detection import _build_price_calc
from apps.bot.keyboards.pricing import DESIGN_BY_KEY
from core.services.price_calculator_service import PriceCalculatorService
from shared.constants.pricing import DESIGN_PRICES_CUSTOMER

# Map each calculator design key → its canonical key in DESIGN_PRICES_CUSTOMER.
_CALC_TO_CUSTOMER = {
    "gulli": "gulli",
    "odnotonniy": "adnatonniy",
    "mramor": "mramor",
    "qora_naqsh_uf": "qora uf",
    "hi_tech": "hi-tech",
    "kosmos_osmon": "kosmos",
}

_LOADED_KB = "apps/bot/ai/knowledge/uz.md"
_PROMPT = "apps/bot/ai/system_prompt.py"
_PACKAGES = "apps/bot/handlers/private/packages.py"
_ABOUT = "apps/bot/handlers/private/about.py"
_PROMOTIONS = "apps/bot/handlers/private/promotions.py"


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


# ── PRICE: calculator keyboard matches the customer-facing source of truth ────


class TestCalculatorMatchesSourceOfTruth:
    def test_every_calculator_design_matches_customer_price(self):
        for calc_key, customer_key in _CALC_TO_CUSTOMER.items():
            assert (
                DESIGN_BY_KEY[calc_key].price_per_sqm == DESIGN_PRICES_CUSTOMER[customer_key]
            ), f"{calc_key}: calculator {DESIGN_BY_KEY[calc_key].price_per_sqm} != truth {DESIGN_PRICES_CUSTOMER[customer_key]}"

    def test_gulli_is_130k_everywhere(self):
        assert DESIGN_PRICES_CUSTOMER["gulli"] == 130_000
        assert DESIGN_BY_KEY["gulli"].price_per_sqm == 130_000
        assert PriceCalculatorService.get_rate("gulli") == 130_000

    def test_hi_tech_is_120k_everywhere(self):
        assert DESIGN_PRICES_CUSTOMER["hi-tech"] == 120_000
        assert DESIGN_BY_KEY["hi_tech"].price_per_sqm == 120_000
        assert PriceCalculatorService.get_rate("hi-tech") == 120_000


# ── PRICE: the LOADED knowledge base (the one the prompt actually reads) ───────


class TestLoadedKnowledgeBasePrices:
    def test_gulli_line_is_130k(self):
        lines = [ln for ln in _read(_LOADED_KB).splitlines() if "Gulli" in ln]
        assert lines, "no Gulli row in loaded KB"
        assert any("130 000" in ln for ln in lines)
        assert all("120 000" not in ln for ln in lines)

    def test_hi_tech_line_is_120k(self):
        lines = [ln for ln in _read(_LOADED_KB).splitlines() if "Hi-tech" in ln]
        assert lines, "no Hi-tech row in loaded KB"
        assert any("120 000" in ln for ln in lines)
        assert all("130 000" not in ln for ln in lines)


# ── PRICE: system prompt Gulli line is the flat source-of-truth value ─────────


class TestSystemPromptGulli:
    def test_gulli_flat_130k(self):
        src = _read(_PROMPT)
        assert "Gulli: 130 000" in src
        assert "120 000–140 000" not in src  # the old inconsistent range is gone


# ── PRICE: the _build_price_calc() table sent directly to the user ────────────


class TestPriceCalcRenderer:
    def test_gulli_is_flat_130k_not_a_range(self):
        # area=1 → per-m² rate appears verbatim in the rendered table.
        table = _build_price_calc(1.0)
        gulli_line = next(ln for ln in table.splitlines() if "Gulli" in ln)
        assert "130 000" in gulli_line
        # the old swapped range must not reappear
        assert "–" not in gulli_line
        assert "120 000" not in gulli_line

    def test_other_design_rows_unchanged(self):
        table = _build_price_calc(1.0)
        assert "80 000" in table  # Adnatonniy
        assert "120 000" in table  # Hi Tech / Mramor / Naqsh / Kosmos / Osmon
        assert "140 000" in table  # Qora UF


# ── WARRANTY: a single flat "15 yil" everywhere customer-facing ───────────────


class TestWarrantyConsistency:
    def test_packages_no_ten_year_warranty(self):
        src = _read(_PACKAGES)
        assert "10 yil kafolat" not in src
        # all three tiers now advertise 15 yil
        assert src.count("15 yil kafolat") >= 3

    def test_about_uses_flat_15_yil(self):
        src = _read(_ABOUT)
        assert "yilgacha" not in src
        assert "15 yil rasmiy kafolat" in src

    def test_promotions_uses_flat_15_yil(self):
        src = _read(_PROMOTIONS)
        assert "yilgacha" not in src
        assert "15 yil rasmiy kafolat" in src

    def test_no_customer_handler_promises_10_yil(self):
        for path in (_PACKAGES, _ABOUT, _PROMOTIONS):
            assert "10 yil kafolat" not in _read(path), f"{path}: stale 10-year warranty"
