"""Tests for Step CN — Price Calculator Service."""
from __future__ import annotations

from core.schemas.price_calculator import (
    PriceCalculatorResponse,
)
from core.services.price_calculator_service import (
    MAX_AREA,
    MIN_AREA,
    PriceCalculatorService,
)
from shared.constants.pricing import DESIGN_PRICES_CUSTOMER, DISCOUNT_TIERS

svc = PriceCalculatorService()


class TestAreaParsing:
    def test_20_kv(self):
        assert svc.parse_area_from_text("20 kv") == 20.0

    def test_20kv_no_space(self):
        assert svc.parse_area_from_text("20kv") == 20.0

    def test_20_m2(self):
        assert svc.parse_area_from_text("20 m2") == 20.0

    def test_5x4(self):
        assert svc.parse_area_from_text("5x4") == 20.0

    def test_5_x_4(self):
        assert svc.parse_area_from_text("5 x 4") == 20.0

    def test_5_star_4(self):
        assert svc.parse_area_from_text("5*4") == 20.0

    def test_decimal_area(self):
        r = svc.parse_area_from_text("5.5x4 xona")
        assert r is not None
        assert abs(r - 22.0) < 0.01

    def test_reject_too_small(self):
        assert svc.parse_area_from_text("0.5 kv") is None

    def test_reject_too_large(self):
        assert svc.parse_area_from_text("600 kv") is None

    def test_no_area(self):
        assert svc.parse_area_from_text("salom dunyo") is None

    def test_min_area_constant(self):
        assert MIN_AREA == 1.0

    def test_max_area_constant(self):
        assert MAX_AREA == 500.0


class TestDesignParsing:
    def test_oddiy(self):
        assert svc.parse_design_from_text("oddiy potolok") == "adnatonniy"

    def test_matoviy(self):
        assert svc.parse_design_from_text("matoviy kerak") == "adnatonniy"

    def test_satin(self):
        assert svc.parse_design_from_text("satin potolok") == "adnatonniy"

    def test_gulli(self):
        assert svc.parse_design_from_text("gulli dizayn") == "gulli"

    def test_print(self):
        assert svc.parse_design_from_text("print potolok") == "gulli"

    def test_pechat(self):
        assert svc.parse_design_from_text("pechat kerak") == "gulli"

    def test_led(self):
        assert svc.parse_design_from_text("led potolok") == "hi-tech"

    def test_shadow(self):
        assert svc.parse_design_from_text("shadow dizayn") == "hi-tech"

    def test_hi_tech(self):
        assert svc.parse_design_from_text("hi-tech kerak") == "hi-tech"

    def test_hitech(self):
        assert svc.parse_design_from_text("hitech narxi") == "hi-tech"

    def test_mramor(self):
        assert svc.parse_design_from_text("mramor qancha") == "mramor"

    def test_kosmos(self):
        assert svc.parse_design_from_text("kosmos dizayn") == "kosmos"

    def test_osmon(self):
        assert svc.parse_design_from_text("osmon potolok") == "osmon"

    def test_qora(self):
        assert svc.parse_design_from_text("qora uf kerak") == "qora uf"

    def test_unknown(self):
        assert svc.parse_design_from_text("salom dunyo") is None


class TestCalculateEstimate:
    def test_gulli_20m2(self):
        r = svc.calculate_estimate(20.0, "gulli")
        assert r.rate_uzs_per_m2 == 130_000
        assert r.subtotal_uzs == 2_600_000
        assert r.is_estimate is True

    def test_adnatonniy_20m2(self):
        r = svc.calculate_estimate(20.0, "adnatonniy")
        assert r.rate_uzs_per_m2 == 80_000

    def test_hi_tech_rate(self):
        r = svc.calculate_estimate(10.0, "hi-tech")
        assert r.rate_uzs_per_m2 == 120_000

    def test_mramor_rate(self):
        r = svc.calculate_estimate(10.0, "mramor")
        assert r.rate_uzs_per_m2 == 120_000

    def test_qora_rate(self):
        r = svc.calculate_estimate(10.0, "qora uf")
        assert r.rate_uzs_per_m2 == 140_000

    def test_all_rates_match_customer_prices(self):
        for key, expected in DESIGN_PRICES_CUSTOMER.items():
            rate = svc.get_rate(key)
            assert rate == expected, f"{key}: {rate} != {expected}"

    def test_discount_over_20(self):
        r = svc.calculate_estimate(25.0, "gulli")
        assert r.discount_percent == 5.0
        assert r.discount_amount_uzs > 0
        assert r.total_uzs < r.subtotal_uzs

    def test_discount_over_40(self):
        r = svc.calculate_estimate(45.0, "gulli")
        assert r.discount_percent == 10.0

    def test_no_discount_under_20(self):
        r = svc.calculate_estimate(15.0, "gulli")
        assert r.discount_percent == 0.0
        assert r.total_uzs == r.subtotal_uzs

    def test_result_is_estimate(self):
        r = svc.calculate_estimate(20.0, "gulli")
        assert r.is_estimate is True

    def test_result_source(self):
        r = svc.calculate_estimate(20.0, "gulli")
        assert r.source == "customer_facing"

    def test_result_has_warnings(self):
        r = svc.calculate_estimate(20.0, "gulli")
        assert len(r.warnings) >= 2
        assert any("taxminiy" in w.lower() for w in r.warnings)

    def test_result_frozen(self):
        import pytest
        r = svc.calculate_estimate(20.0, "gulli")
        with pytest.raises(AttributeError):
            r.total_uzs = 0

    def test_unknown_design_uses_default(self):
        r = svc.calculate_estimate(20.0, "unknown_xyz")
        assert r.rate_uzs_per_m2 == 100_000


class TestClarification:
    def test_area_missing(self):
        r = svc.build_clarification("gulli potolok")
        assert r.needs_area is True
        assert r.parsed_design == "gulli"

    def test_design_missing(self):
        r = svc.build_clarification("20 kv xona")
        assert r.needs_design is True
        assert r.parsed_area == 20.0

    def test_both_missing(self):
        r = svc.build_clarification("salom")
        assert r.needs_area is True
        assert r.needs_design is True

    def test_both_present(self):
        r = svc.build_clarification("20 kv gulli")
        assert r.needs_area is False
        assert r.needs_design is False
        assert r.parsed_area == 20.0
        assert r.parsed_design == "gulli"

    def test_question_text(self):
        r = svc.build_clarification("gulli")
        assert len(r.question) > 10


class TestUserResponse:
    def test_contains_taxminiy(self):
        est = svc.calculate_estimate(20.0, "gulli")
        text = svc.build_user_response(est)
        assert "taxminiy" in text.lower()

    def test_contains_measurement_warning(self):
        est = svc.calculate_estimate(20.0, "gulli")
        text = svc.build_user_response(est)
        assert "o'lchov" in text.lower()

    def test_no_eng_arzon(self):
        est = svc.calculate_estimate(20.0, "adnatonniy")
        text = svc.build_user_response(est)
        assert "eng arzon" not in text.lower()

    def test_no_same_day(self):
        est = svc.calculate_estimate(20.0, "gulli")
        text = svc.build_user_response(est)
        assert "bugun qilamiz" not in text.lower()

    def test_no_fake_discount(self):
        est = svc.calculate_estimate(10.0, "gulli")
        text = svc.build_user_response(est)
        assert "maxsus chegirma" not in text.lower()

    def test_shows_discount_when_applicable(self):
        est = svc.calculate_estimate(25.0, "gulli")
        text = svc.build_user_response(est)
        assert "5%" in text or "chegirma" in text.lower()


class TestMemoryPayload:
    def test_has_area(self):
        est = svc.calculate_estimate(20.0, "gulli")
        p = svc.build_memory_payload(est)
        assert p["last_price_area_m2"] == 20.0

    def test_has_design(self):
        est = svc.calculate_estimate(20.0, "gulli")
        p = svc.build_memory_payload(est)
        assert p["last_price_design"] == "gulli"

    def test_has_total(self):
        est = svc.calculate_estimate(20.0, "gulli")
        p = svc.build_memory_payload(est)
        assert p["last_price_total"] > 0

    def test_has_source(self):
        est = svc.calculate_estimate(20.0, "gulli")
        p = svc.build_memory_payload(est)
        assert p["last_price_source"] == "customer_facing"


class TestSanitize:
    def test_removes_token(self):
        r = svc.sanitize_price_text("price sk-abc12345678xyz done")
        assert "sk-abc" not in r
        assert "[REDACTED]" in r

    def test_clean_text_unchanged(self):
        r = svc.sanitize_price_text("20 kv gulli qancha")
        assert r == "20 kv gulli qancha"

    def test_no_token_in_response(self):
        est = svc.calculate_estimate(20.0, "gulli")
        text = svc.build_user_response(est)
        assert "sk-" not in text


class TestFormatUZS:
    def test_format(self):
        assert svc.format_uzs(2_600_000) == "2 600 000"

    def test_small(self):
        assert svc.format_uzs(80_000) == "80 000"

    def test_zero(self):
        assert svc.format_uzs(0) == "0"


class TestValidateArea:
    def test_valid(self):
        assert svc.validate_area(20.0) is None

    def test_too_small(self):
        r = svc.validate_area(0.5)
        assert r is not None
        assert "kichik" in r

    def test_too_large(self):
        r = svc.validate_area(600.0)
        assert r is not None
        assert "katta" in r


class TestExtractAndRespond:
    def test_complete_input(self):
        r = svc.extract_and_respond("20 kv gulli")
        assert r.estimate is not None
        assert r.estimate.total_uzs > 0

    def test_area_only(self):
        r = svc.extract_and_respond("20 kv xona")
        assert r.clarification is not None
        assert r.clarification.needs_design is True

    def test_design_only(self):
        r = svc.extract_and_respond("gulli potolok")
        assert r.clarification is not None
        assert r.clarification.needs_area is True

    def test_nothing(self):
        r = svc.extract_and_respond("salom")
        assert r.clarification is not None
        assert r.clarification.needs_area is True
        assert r.clarification.needs_design is True

    def test_response_type(self):
        r = svc.extract_and_respond("20 kv gulli")
        assert isinstance(r, PriceCalculatorResponse)


class TestDiscountTiers:
    def test_tiers_exist(self):
        assert len(DISCOUNT_TIERS) >= 2

    def test_40m2_10pct(self):
        assert DISCOUNT_TIERS[0] == (40.0, 0.10)

    def test_20m2_5pct(self):
        assert DISCOUNT_TIERS[1] == (20.0, 0.05)
