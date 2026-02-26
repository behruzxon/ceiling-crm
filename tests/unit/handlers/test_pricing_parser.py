"""Unit tests for pricing dimension parser and promo helpers.

Tests cover _parse_two_dimensions (fast path), _parse_dimension (single value),
and _led_promo_eligible (LED strip promotion rule).
No I/O or FSM — pure function tests only.
"""
from __future__ import annotations

import pytest

from apps.bot.handlers.private.pricing import (
    LED_PROMO_DESIGN,
    LED_PROMO_THRESHOLD,
    _led_promo_eligible,
    _parse_dimension,
    _parse_two_dimensions,
)


# ─── _parse_two_dimensions ────────────────────────────────────────────────────

class TestParseTwoDimensions:
    def test_ga_separator(self) -> None:
        assert _parse_two_dimensions("5ga4") == (5.0, 4.0)

    def test_asterisk_separator(self) -> None:
        assert _parse_two_dimensions("5*4") == (5.0, 4.0)

    def test_space_separator(self) -> None:
        assert _parse_two_dimensions("5 4") == (5.0, 4.0)

    def test_x_with_spaces(self) -> None:
        assert _parse_two_dimensions("5 x 4") == (5.0, 4.0)

    def test_uppercase_x(self) -> None:
        assert _parse_two_dimensions("5X4") == (5.0, 4.0)

    def test_multiply_symbol(self) -> None:
        assert _parse_two_dimensions("5×4") == (5.0, 4.0)

    def test_comma_decimal(self) -> None:
        result = _parse_two_dimensions("5,2x3,3")
        assert result is not None
        length, width = result
        assert abs(length - 5.2) < 1e-9
        assert abs(width - 3.3) < 1e-9

    def test_dot_decimal_with_spaced_asterisk(self) -> None:
        result = _parse_two_dimensions("5.2 * 3.3")
        assert result is not None
        length, width = result
        assert abs(length - 5.2) < 1e-9
        assert abs(width - 3.3) < 1e-9

    def test_leading_trailing_whitespace(self) -> None:
        assert _parse_two_dimensions("  5 x 4  ") == (5.0, 4.0)

    # Fallback cases — must return None so caller asks for width separately
    def test_single_number_returns_none(self) -> None:
        assert _parse_two_dimensions("5") is None

    def test_plain_text_returns_none(self) -> None:
        assert _parse_two_dimensions("salom") is None

    def test_empty_string_returns_none(self) -> None:
        assert _parse_two_dimensions("") is None

    def test_out_of_range_first_dim_returns_none(self) -> None:
        # 51 > 50 → _parse_dimension returns None → whole pair is None
        assert _parse_two_dimensions("51x4") is None

    def test_out_of_range_second_dim_returns_none(self) -> None:
        assert _parse_two_dimensions("5x51") is None


# ─── Area computation via fast path ──────────────────────────────────────────

class TestAreaFromPair:
    def test_area_5x4(self) -> None:
        result = _parse_two_dimensions("5ga4")
        assert result is not None
        assert round(result[0] * result[1], 2) == 20.0

    def test_area_5_asterisk_4(self) -> None:
        result = _parse_two_dimensions("5*4")
        assert result is not None
        assert round(result[0] * result[1], 2) == 20.0

    def test_area_5_space_4(self) -> None:
        result = _parse_two_dimensions("5 4")
        assert result is not None
        assert round(result[0] * result[1], 2) == 20.0

    def test_area_5point2_x_3point3(self) -> None:
        result = _parse_two_dimensions("5.2x3.3")
        assert result is not None
        assert round(result[0] * result[1], 2) == 17.16


# ─── _parse_dimension (single value) ─────────────────────────────────────────

class TestParseDimension:
    def test_integer(self) -> None:
        assert _parse_dimension("5") == 5.0

    def test_dot_decimal(self) -> None:
        assert _parse_dimension("3.8") == 3.8

    def test_comma_decimal(self) -> None:
        assert _parse_dimension("3,8") == 3.8

    def test_zero_returns_none(self) -> None:
        assert _parse_dimension("0") is None

    def test_negative_returns_none(self) -> None:
        assert _parse_dimension("-1") is None

    def test_too_large_returns_none(self) -> None:
        assert _parse_dimension("51") is None

    def test_boundary_50_accepted(self) -> None:
        assert _parse_dimension("50") == 50.0

    def test_text_returns_none(self) -> None:
        assert _parse_dimension("salom") is None

    def test_none_input(self) -> None:
        assert _parse_dimension(None) is None


# ─── _led_promo_eligible ──────────────────────────────────────────────────────

class TestLedPromoEligible:
    def test_exact_threshold_gulli(self) -> None:
        """area == LED_PROMO_THRESHOLD with gulli design → eligible."""
        assert _led_promo_eligible(LED_PROMO_THRESHOLD, LED_PROMO_DESIGN) is True

    def test_above_threshold_gulli(self) -> None:
        assert _led_promo_eligible(60.0, "gulli") is True

    def test_below_threshold_gulli(self) -> None:
        """area < 50 m² with gulli → not eligible."""
        assert _led_promo_eligible(49.99, "gulli") is False

    def test_threshold_wrong_design(self) -> None:
        """Large area but different design → not eligible."""
        assert _led_promo_eligible(60.0, "odnotonniy") is False

    def test_threshold_wrong_design_mramor(self) -> None:
        assert _led_promo_eligible(55.0, "mramor") is False

    def test_zero_area_gulli(self) -> None:
        assert _led_promo_eligible(0.0, "gulli") is False

    def test_case_sensitivity(self) -> None:
        """Design key comparison is exact (lowercase 'gulli' only)."""
        assert _led_promo_eligible(60.0, "Gulli") is False
        assert _led_promo_eligible(60.0, "GULLI") is False
