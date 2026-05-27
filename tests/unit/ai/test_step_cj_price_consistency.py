"""Tests for Step CJ — Price Consistency Across Sources."""
from __future__ import annotations

from pathlib import Path

from shared.constants.pricing import DESIGN_PRICES_CUSTOMER, DISCOUNT_TIERS


def _uz() -> str:
    return Path("shared/knowledge/uz.md").read_text(encoding="utf-8")


def _prompt() -> str:
    return Path("apps/bot/ai/system_prompt.py").read_text(encoding="utf-8")


class TestCustomerPriceSource:
    def test_adnatonniy_80k(self):
        assert DESIGN_PRICES_CUSTOMER["adnatonniy"] == 80_000

    def test_hi_tech_120k(self):
        assert DESIGN_PRICES_CUSTOMER["hi-tech"] == 120_000

    def test_mramor_120k(self):
        assert DESIGN_PRICES_CUSTOMER["mramor"] == 120_000

    def test_gulli_130k(self):
        assert DESIGN_PRICES_CUSTOMER["gulli"] == 130_000

    def test_qora_uf_140k(self):
        assert DESIGN_PRICES_CUSTOMER["qora uf"] == 140_000

    def test_kosmos_120k(self):
        assert DESIGN_PRICES_CUSTOMER["kosmos"] == 120_000

    def test_osmon_120k(self):
        assert DESIGN_PRICES_CUSTOMER["osmon"] == 120_000

    def test_naqsh_120k(self):
        assert DESIGN_PRICES_CUSTOMER["naqsh"] == 120_000


class TestUzMdMatchesCustomer:
    def test_gulli_130k_in_uzmd(self):
        assert "130 000" in _uz() or "130,000" in _uz()

    def test_odnotonniy_80k_in_uzmd(self):
        assert "80 000" in _uz()

    def test_hi_tech_120k_in_uzmd(self):
        c = _uz()
        lines = [ln for ln in c.splitlines() if "Hi-tech" in ln]
        assert any("120 000" in ln for ln in lines)

    def test_qora_140k_in_uzmd(self):
        assert "140 000" in _uz()

    def test_mramor_120k_in_uzmd(self):
        c = _uz()
        lines = [ln for ln in c.splitlines() if "Mramor" in ln]
        assert any("120 000" in ln for ln in lines)


class TestPromptMatchesCustomer:
    def test_adnatonniy_80k_in_prompt(self):
        assert "80 000" in _prompt() or "80_000" in _prompt()

    def test_hi_tech_120k_in_prompt(self):
        assert "120 000" in _prompt() or "120_000" in _prompt()

    def test_qora_140k_in_prompt(self):
        assert "140 000" in _prompt() or "140_000" in _prompt()


class TestPriceLabeling:
    def test_prompt_says_taxminiy(self):
        c = _prompt().lower()
        assert "taxminiy" in c

    def test_uzmd_says_taxminiy(self):
        assert "TAXMINIY" in _uz() or "taxminiy" in _uz().lower()

    def test_no_aniq_narx_claim(self):
        c = _prompt().lower()
        assert "aniq narx" in c and "dema" in c

    def test_no_final_narx_claim(self):
        c = _prompt().lower()
        assert "final narx" in c and "dema" in c


class TestDiscountConsistency:
    def test_discount_20m2_5pct(self):
        assert DISCOUNT_TIERS[1] == (20.0, 0.05)

    def test_discount_40m2_10pct(self):
        assert DISCOUNT_TIERS[0] == (40.0, 0.10)

    def test_uzmd_discount_20m2(self):
        assert "20 m" in _uz() and "5" in _uz()

    def test_uzmd_discount_40m2(self):
        assert "40 m" in _uz() and "10" in _uz()

    def test_no_impossible_free_discount(self):
        c = _uz().lower()
        assert "100%" not in c.split("chegirma")[0] if "chegirma" in c else True
