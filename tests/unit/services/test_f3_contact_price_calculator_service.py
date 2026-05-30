"""F3 — Manual price calculator service tests.

The calculator is a read-only wrapper around the existing
PriceCalculatorService. These tests pin its contract: input parsing,
area bounds, design resolution, addon parsing, discounts, no negative
totals, and the taxminiy guarantees.

Zero network / DB access.
"""

from __future__ import annotations

from pathlib import Path

from core.schemas.contact_price_calculator import (
    ContactPriceCalculatorAddonLine,
    ContactPriceCalculatorResult,
)
from core.services.contact_price_calculator_service import (
    available_addons,
    available_designs,
    build_contact_price_estimate,
)

# ── Missing / invalid area ─────────────────────────────────────────────


class TestMissingArea:
    def test_none_area_returns_invalid(self) -> None:
        result = build_contact_price_estimate(area_m2=None, design_key="gulli")
        assert isinstance(result, ContactPriceCalculatorResult)
        assert result.is_valid is False
        assert result.error

    def test_empty_string_area_returns_invalid(self) -> None:
        result = build_contact_price_estimate(area_m2="", design_key="gulli")
        assert result.is_valid is False
        assert result.area_m2 is None

    def test_garbage_area_returns_invalid(self) -> None:
        result = build_contact_price_estimate(area_m2="abc xyz", design_key="gulli")
        assert result.is_valid is False
        assert result.total_uzs == 0

    def test_invalid_keeps_design_for_form_repopulation(self) -> None:
        result = build_contact_price_estimate(area_m2=None, design_key="gulli")
        assert result.design_key == "gulli"


class TestAreaBounds:
    def test_area_below_one_invalid(self) -> None:
        result = build_contact_price_estimate(area_m2=0.5, design_key="gulli")
        assert result.is_valid is False
        assert "kichik" in result.error

    def test_area_above_500_invalid(self) -> None:
        result = build_contact_price_estimate(area_m2=501, design_key="gulli")
        assert result.is_valid is False
        assert "katta" in result.error

    def test_boundary_one_is_valid(self) -> None:
        result = build_contact_price_estimate(area_m2=1, design_key="adnatonniy")
        assert result.is_valid is True

    def test_boundary_500_is_valid(self) -> None:
        result = build_contact_price_estimate(area_m2=500, design_key="adnatonniy")
        assert result.is_valid is True


class TestAreaParsing:
    def test_int_area(self) -> None:
        result = build_contact_price_estimate(area_m2=20, design_key="gulli")
        assert result.area_m2 == 20

    def test_float_area(self) -> None:
        result = build_contact_price_estimate(area_m2=12.5, design_key="gulli")
        assert result.is_valid is True

    def test_string_int_area(self) -> None:
        result = build_contact_price_estimate(area_m2="20", design_key="gulli")
        assert result.area_m2 == 20

    def test_string_decimal_with_comma(self) -> None:
        result = build_contact_price_estimate(area_m2="12,5", design_key="gulli")
        assert result.is_valid is True

    def test_nan_area_rejected(self) -> None:
        result = build_contact_price_estimate(area_m2=float("nan"), design_key="gulli")
        assert result.is_valid is False

    def test_inf_area_rejected(self) -> None:
        result = build_contact_price_estimate(area_m2=float("inf"), design_key="gulli")
        assert result.is_valid is False


# ── Design resolution ──────────────────────────────────────────────────


class TestDesignResolution:
    def test_gulli_estimate_works(self) -> None:
        result = build_contact_price_estimate(area_m2=20, design_key="gulli")
        assert result.is_valid is True
        assert result.design_key == "gulli"
        assert result.base_rate_uzs == 130_000
        assert result.subtotal_uzs == 20 * 130_000

    def test_design_alias_print_to_gulli(self) -> None:
        result = build_contact_price_estimate(area_m2=20, design_key="print")
        assert result.design_key == "gulli"

    def test_design_alias_oddiy_to_adnatonniy(self) -> None:
        result = build_contact_price_estimate(area_m2=10, design_key="oddiy")
        assert result.design_key == "adnatonniy"

    def test_missing_design_falls_back_to_adnatonniy(self) -> None:
        result = build_contact_price_estimate(area_m2=10, design_key=None)
        assert result.design_key == "adnatonniy"

    def test_empty_design_falls_back_to_adnatonniy(self) -> None:
        result = build_contact_price_estimate(area_m2=10, design_key="")
        assert result.design_key == "adnatonniy"

    def test_unknown_design_falls_back_safely(self) -> None:
        result = build_contact_price_estimate(area_m2=10, design_key="nonexistent_design")
        assert result.is_valid is True
        assert result.design_key == "adnatonniy"

    def test_available_designs_returns_pairs(self) -> None:
        designs = available_designs()
        assert designs
        for key, label in designs:
            assert isinstance(key, str)
            assert isinstance(label, str)


# ── Discount tiers ─────────────────────────────────────────────────────


class TestDiscountTiers:
    def test_no_discount_below_20(self) -> None:
        result = build_contact_price_estimate(area_m2=15, design_key="adnatonniy")
        assert result.discount_percent == 0

    def test_discount_5_pct_above_20(self) -> None:
        result = build_contact_price_estimate(area_m2=21, design_key="adnatonniy")
        assert result.discount_percent == 5.0

    def test_discount_10_pct_above_40(self) -> None:
        result = build_contact_price_estimate(area_m2=50, design_key="adnatonniy")
        assert result.discount_percent == 10.0

    def test_discount_reduces_total(self) -> None:
        r_small = build_contact_price_estimate(area_m2=10, design_key="adnatonniy")
        r_big = build_contact_price_estimate(area_m2=50, design_key="adnatonniy")
        assert r_big.discount_amount_uzs > 0
        assert r_small.discount_amount_uzs == 0


# ── Addons parsing ─────────────────────────────────────────────────────


class TestAddonParsing:
    def test_no_addons_returns_zero_lines(self) -> None:
        result = build_contact_price_estimate(area_m2=20, design_key="gulli", addons=None)
        assert result.addon_lines == ()
        assert result.addons_total_uzs == 0

    def test_single_addon_from_string(self) -> None:
        result = build_contact_price_estimate(area_m2=20, design_key="gulli", addons="led_strip")
        assert len(result.addon_lines) == 1
        assert result.addon_lines[0].key == "led_strip"

    def test_comma_separated_addons(self) -> None:
        result = build_contact_price_estimate(
            area_m2=20, design_key="gulli", addons="led_strip,cornice,spot_holes"
        )
        keys = [line.key for line in result.addon_lines]
        assert keys == ["led_strip", "cornice", "spot_holes"]

    def test_addons_from_list(self) -> None:
        result = build_contact_price_estimate(
            area_m2=20, design_key="gulli", addons=["led_strip", "cornice"]
        )
        assert len(result.addon_lines) == 2

    def test_unknown_addon_silently_dropped(self) -> None:
        result = build_contact_price_estimate(
            area_m2=20, design_key="gulli", addons="led_strip,bogus,cornice"
        )
        keys = [line.key for line in result.addon_lines]
        assert "bogus" not in keys
        assert keys == ["led_strip", "cornice"]

    def test_duplicate_addons_deduped(self) -> None:
        result = build_contact_price_estimate(
            area_m2=20, design_key="gulli", addons="led_strip,led_strip,led_strip"
        )
        assert len(result.addon_lines) == 1

    def test_addon_quantity_uses_perimeter_for_per_meter(self) -> None:
        result = build_contact_price_estimate(
            area_m2=25, design_key="adnatonniy", addons="led_strip"
        )
        # perimeter = 4 * sqrt(25) = 20m
        line = result.addon_lines[0]
        assert abs(line.quantity - 20.0) < 0.01

    def test_addon_quantity_one_for_holes(self) -> None:
        result = build_contact_price_estimate(
            area_m2=20, design_key="adnatonniy", addons="spot_holes"
        )
        assert result.addon_lines[0].quantity == 1.0

    def test_addon_total_added_to_grand_total(self) -> None:
        no_addons = build_contact_price_estimate(area_m2=20, design_key="adnatonniy")
        with_addon = build_contact_price_estimate(
            area_m2=20, design_key="adnatonniy", addons="led_strip"
        )
        assert with_addon.total_uzs > no_addons.total_uzs

    def test_available_addons_lists_catalog(self) -> None:
        addons = available_addons()
        keys = [k for k, _ in addons]
        assert "led_strip" in keys
        assert "cornice" in keys


# ── Result invariants ──────────────────────────────────────────────────


class TestResultInvariants:
    def test_total_is_never_negative(self) -> None:
        result = build_contact_price_estimate(area_m2=20, design_key="gulli")
        assert result.total_uzs >= 0

    def test_is_estimate_is_true_when_valid(self) -> None:
        result = build_contact_price_estimate(area_m2=20, design_key="gulli")
        assert result.is_estimate is True

    def test_warning_mentions_measurement(self) -> None:
        result = build_contact_price_estimate(area_m2=20, design_key="gulli")
        assert "o'lchov" in result.warning.lower()

    def test_warning_does_not_promise_final_price(self) -> None:
        result = build_contact_price_estimate(area_m2=20, design_key="gulli")
        forbidden = ("kafolat", "yakuniy narx shu", "darhol", "100%")
        for word in forbidden:
            assert word not in result.warning.lower()

    def test_taxminiy_word_in_warning(self) -> None:
        result = build_contact_price_estimate(area_m2=20, design_key="gulli")
        assert "taxminiy" in result.warning.lower()

    def test_formatted_total_present_when_valid(self) -> None:
        result = build_contact_price_estimate(area_m2=20, design_key="gulli")
        assert result.formatted_total
        assert " " in result.formatted_total  # thousand separator

    def test_formatted_rate_present_when_valid(self) -> None:
        result = build_contact_price_estimate(area_m2=20, design_key="gulli")
        assert result.formatted_rate


# ── No internal-pricing leakage ────────────────────────────────────────


class TestNoInternalPricingLeakage:
    def test_service_module_does_not_import_default_base_prices(self) -> None:
        source = Path("core/services/contact_price_calculator_service.py").read_text(
            encoding="utf-8"
        )
        assert "DEFAULT_BASE_PRICES" not in source

    def test_result_repr_does_not_mention_default_base_prices(self) -> None:
        result = build_contact_price_estimate(area_m2=20, design_key="gulli")
        assert "DEFAULT_BASE_PRICES" not in repr(result)
        assert "default_base_prices" not in repr(result).lower()


# ── Frozen dataclass ───────────────────────────────────────────────────


class TestFrozenDataclasses:
    def test_result_is_frozen(self) -> None:
        result = ContactPriceCalculatorResult(is_valid=True)
        try:
            result.is_valid = False  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("ContactPriceCalculatorResult should be frozen")

    def test_addon_line_is_frozen(self) -> None:
        line = ContactPriceCalculatorAddonLine(key="x", label="X")
        try:
            line.label = "Y"  # type: ignore[misc]
        except Exception:
            return
        raise AssertionError("ContactPriceCalculatorAddonLine should be frozen")
