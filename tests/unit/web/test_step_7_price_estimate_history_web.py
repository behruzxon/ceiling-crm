"""Tests for price estimate history in contact detail template — Step 7."""

from __future__ import annotations

from pathlib import Path

TEMPLATE_PATH = Path("apps/web/templates/crm_contact_detail.html")


def _read_template() -> str:
    assert TEMPLATE_PATH.exists()
    return TEMPLATE_PATH.read_text(encoding="utf-8")


class TestPriceEstimateSection:
    def test_template_exists(self) -> None:
        assert TEMPLATE_PATH.exists()

    def test_has_price_estimate_history_title(self) -> None:
        assert "Price Estimate History" in _read_template()

    def test_has_price_estimate_card(self) -> None:
        assert "priceEstimateHistory" in _read_template()

    def test_has_latest_estimate_section(self) -> None:
        assert "priceEstLatest" in _read_template()

    def test_has_latest_total(self) -> None:
        assert "priceEstLatestTotal" in _read_template()

    def test_has_items_list(self) -> None:
        assert "priceEstItems" in _read_template()

    def test_has_empty_state(self) -> None:
        content = _read_template()
        assert "priceEstEmpty" in content
        assert "narx hisoblari" in content.lower()

    def test_has_estimate_count(self) -> None:
        assert "priceEstCount" in _read_template()


class TestPriceEstimateFields:
    def test_area_field(self) -> None:
        assert "area_m2" in _read_template() or "m²" in _read_template()

    def test_design_field(self) -> None:
        assert "design_title" in _read_template()

    def test_total_field(self) -> None:
        assert "total_uzs" in _read_template()

    def test_rate_field(self) -> None:
        assert "rate_uzs_per_m2" in _read_template()

    def test_taxminiy_badge(self) -> None:
        assert "taxminiy" in _read_template().lower()

    def test_discount_display(self) -> None:
        assert "discount_percent" in _read_template()

    def test_handoff_indicator(self) -> None:
        assert "handoff_after_estimate" in _read_template()

    def test_source_field(self) -> None:
        assert "source" in _read_template()


class TestPriceEstimateSummary:
    def test_summary_badges(self) -> None:
        assert "priceEstSummaryBadges" in _read_template()

    def test_latest_detail(self) -> None:
        assert "priceEstLatestDetail" in _read_template()

    def test_taxminiy_warning_footer(self) -> None:
        content = _read_template()
        assert "priceEstTaxminiy" in content
        assert "yakuniy narx" in content.lower() or "Yakuniy narx" in content


class TestPriceEstimateCSS:
    def test_price_est_list(self) -> None:
        assert ".price-est-list" in _read_template()

    def test_price_est_item(self) -> None:
        assert ".price-est-item" in _read_template()

    def test_price_est_item_total(self) -> None:
        assert ".price-est-item-total" in _read_template()

    def test_price_est_item_discount(self) -> None:
        assert ".price-est-item-discount" in _read_template()

    def test_price_est_item_handoff(self) -> None:
        assert ".price-est-item-handoff" in _read_template()

    def test_price_est_item_time(self) -> None:
        assert ".price-est-item-time" in _read_template()


class TestPriceEstimateJS:
    def test_load_function(self) -> None:
        assert "loadPriceEstimates" in _read_template()

    def test_render_function(self) -> None:
        assert "renderPriceEstimates" in _read_template()

    def test_format_uzs_function(self) -> None:
        assert "fmtUzs" in _read_template()

    def test_fetches_api(self) -> None:
        assert "/price-estimates" in _read_template()


class TestPriceEstimateSecurity:
    def test_no_final_guarantee(self) -> None:
        content = _read_template()
        assert "garantiya" not in content.lower() or "kafolat" not in content.lower()

    def test_no_token(self) -> None:
        content = _read_template()
        assert "sk-" not in content
        assert "BOT_TOKEN" not in content

    def test_no_openai_key(self) -> None:
        assert "OPENAI_API_KEY" not in _read_template()

    def test_no_database_url(self) -> None:
        assert "postgresql://" not in _read_template()

    def test_uses_vp_card(self) -> None:
        assert "vp-card" in _read_template()

    def test_uses_vp_badge(self) -> None:
        assert "vp-badge" in _read_template()


class TestPriceEstimateResponsive:
    def test_mobile_breakpoint(self) -> None:
        assert "768px" in _read_template()

    def test_price_before_ai_trace(self) -> None:
        content = _read_template()
        price_pos = content.find("priceEstimateHistory")
        ai_pos = content.find("aiTraceSection")
        assert price_pos < ai_pos
