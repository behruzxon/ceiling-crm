"""Tests for Step CF — AI Pricing Intelligence."""

from __future__ import annotations

from apps.bot.handlers.private.ai_detection import (
    _detect_catalog_context,
    _is_catalog_request,
    _is_measurement_request,
    _is_price_query,
)
from apps.bot.handlers.private.ai_scoring import (
    classify_score,
)


class TestPriceQueryDetection:
    def test_20_kv_narx(self):
        assert _is_price_query("20 kv narx")

    def test_5x4_narx(self):
        assert _is_price_query("5x4 xonaga narx")

    def test_gulli_qancha(self):
        assert _is_price_query("gulli qancha")

    def test_hisoblab_ber(self):
        assert _is_price_query("hisoblab ber")

    def test_cyrillic_narx(self):
        assert _is_price_query("нарх қанча")

    def test_russian_skolko(self):
        assert _is_price_query("сколько стоит")

    def test_kv_narx(self):
        assert _is_price_query("kv narx")

    def test_m2_narx(self):
        assert _is_price_query("m2 narx qancha")

    def test_non_price_text(self):
        assert not _is_price_query("salom")

    def test_non_price_generic(self):
        assert not _is_price_query("qanday hollar")


class TestAreaParsing:
    def test_parse_area_5x4(self):
        from shared.utils.area_parser import parse_area

        result = parse_area("5x4 xona")
        assert result is not None
        assert abs(result - 20.0) < 0.01

    def test_parse_area_20(self):
        from shared.utils.area_parser import parse_area

        result = parse_area("20 m2 xona")
        assert result is not None
        assert abs(result - 20.0) < 0.01

    def test_parse_area_invalid(self):
        from shared.utils.area_parser import parse_area

        result = parse_area("salom dunyo")
        assert result is None or result == 0

    def test_parse_area_decimal(self):
        from shared.utils.area_parser import parse_area

        result = parse_area("5.5x4 mehmonxona")
        assert result is not None
        assert abs(result - 22.0) < 0.01


class TestDesignDetection:
    def test_gulli(self):
        _, design = _detect_catalog_context("gulli potolok kerak")
        assert design == "Gulli"

    def test_hi_tech(self):
        _, design = _detect_catalog_context("hi tech dizayn")
        assert design == "Hi Tech"

    def test_mramor(self):
        _, design = _detect_catalog_context("mramor qancha")
        assert design == "Mramor"

    def test_no_design(self):
        _, design = _detect_catalog_context("salom dunyo")
        assert design is None


class TestCatalogDetection:
    def test_katalog(self):
        assert _is_catalog_request("katalog bormi")

    def test_dizayn(self):
        assert _is_catalog_request("dizaynlar ko'rsat")

    def test_room_name(self):
        assert _is_catalog_request("mehmonxona uchun")

    def test_cyrillic_katalog(self):
        assert _is_catalog_request("каталог кўрсат")

    def test_non_catalog(self):
        assert not _is_catalog_request("narx qancha")


class TestMeasurementDetection:
    def test_zakaz(self):
        assert _is_measurement_request("zakaz qilmoqchiman")

    def test_bepul_olchov(self):
        assert _is_measurement_request("bepul o'lchov kerak")

    def test_usta_kerak(self):
        assert _is_measurement_request("usta kerak")

    def test_cyrillic_zakas(self):
        assert _is_measurement_request("заказ олинг")

    def test_non_measurement(self):
        assert not _is_measurement_request("salom")


class TestScoreClassification:
    def test_hot(self):
        assert classify_score(60) == "hot"

    def test_hot_high(self):
        assert classify_score(100) == "hot"

    def test_warm(self):
        assert classify_score(30) == "warm"

    def test_warm_mid(self):
        assert classify_score(45) == "warm"

    def test_cold(self):
        assert classify_score(0) == "cold"

    def test_cold_low(self):
        assert classify_score(29) == "cold"
