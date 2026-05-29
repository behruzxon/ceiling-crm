"""F3 — Manual price calculator template tests.

Inspects the rendered Jinja2 template source for the new sidebar
calculator card. No server, no API calls.
"""

from __future__ import annotations

from pathlib import Path

_TEMPLATE_PATH = Path("apps/web/templates/crm_contact_detail.html")
_TEMPLATE = _TEMPLATE_PATH.read_text(encoding="utf-8")


def _new_section() -> str:
    start = _TEMPLATE.find("Manual Price Calculator")
    end = _TEMPLATE.find("AI Trace Viewer", start + 1)
    assert start >= 0, "calculator comment not found"
    assert end > start, "AI Trace Viewer not found after calculator"
    return _TEMPLATE[start:end]


_PANEL = _new_section()


class TestPanelExists:
    def test_panel_title_present(self) -> None:
        assert "Manual Price Calculator" in _PANEL

    def test_panel_container_id(self) -> None:
        assert "manualPriceCalculatorPanel" in _PANEL

    def test_panel_uses_vp_card(self) -> None:
        assert "vp-card" in _PANEL

    def test_taxminiy_badge_present(self) -> None:
        assert "taxminiy" in _PANEL.lower()


class TestGetForm:
    def test_form_exists(self) -> None:
        assert "manualPriceCalculatorForm" in _PANEL

    def test_form_uses_get_method(self) -> None:
        assert 'method="get"' in _PANEL.lower()

    def test_form_is_not_post(self) -> None:
        assert 'method="post"' not in _PANEL.lower()
        assert "method='post'" not in _PANEL.lower()

    def test_form_submits_to_contact_url(self) -> None:
        assert 'action="/crm/' in _PANEL


class TestFormFields:
    def test_area_input_exists(self) -> None:
        assert 'name="calc_area"' in _PANEL

    def test_area_input_has_id(self) -> None:
        assert "calcAreaInput" in _PANEL

    def test_area_input_has_min_max(self) -> None:
        assert 'min="1"' in _PANEL
        assert 'max="500"' in _PANEL

    def test_design_select_exists(self) -> None:
        assert 'name="calc_design"' in _PANEL

    def test_design_select_has_id(self) -> None:
        assert "calcDesignSelect" in _PANEL

    def test_design_select_loops_over_designs(self) -> None:
        assert "for d_key, d_label in (calculator_designs or [])" in _PANEL

    def test_addons_input_exists(self) -> None:
        assert 'name="calc_addons"' in _PANEL

    def test_addons_input_has_id(self) -> None:
        assert "calcAddonsInput" in _PANEL

    def test_addons_hint_shows_catalog(self) -> None:
        assert "calculator_addons" in _PANEL

    def test_calculate_button_exists(self) -> None:
        assert "calcSubmitBtn" in _PANEL

    def test_calculate_button_is_submit(self) -> None:
        assert 'type="submit"' in _PANEL


class TestResultRendering:
    def test_total_rendered(self) -> None:
        assert "cr.formatted_total" in _PANEL

    def test_design_title_rendered(self) -> None:
        assert "cr.design_title" in _PANEL

    def test_rate_rendered(self) -> None:
        assert "cr.formatted_rate" in _PANEL

    def test_discount_conditional(self) -> None:
        assert "cr.discount_percent" in _PANEL

    def test_addon_lines_loop(self) -> None:
        assert "for line in cr.addon_lines" in _PANEL

    def test_warning_rendered(self) -> None:
        assert "cr.warning" in _PANEL

    def test_error_renders_when_invalid(self) -> None:
        assert "calcError" in _PANEL

    def test_empty_state_when_no_result(self) -> None:
        assert "calcEmpty" in _PANEL


class TestTaxminiyAndMeasurementWarning:
    def test_taxminiy_banner_in_result(self) -> None:
        assert "TAXMINIY HISOB" in _PANEL

    def test_warning_anchor_present(self) -> None:
        assert "calcWarning" in _PANEL


class TestSafetyNoSendNoSave:
    def test_no_send_button(self) -> None:
        for word in ("Yuborish", "Send live", "Send message", "Send Telegram"):
            assert word not in _PANEL

    def test_no_save_button(self) -> None:
        for word in ("Saqlash", "Save", "Persist"):
            assert word not in _PANEL

    def test_no_post_in_calculator(self) -> None:
        assert 'method="post"' not in _PANEL.lower()
        assert "fetch(" not in _PANEL
        assert "XMLHttpRequest" not in _PANEL

    def test_no_telegram_send_text(self) -> None:
        assert "api.telegram.org" not in _PANEL
        assert "sendMessage" not in _PANEL

    def test_no_openai_text(self) -> None:
        assert "openai.com" not in _PANEL
        assert "api.openai.com" not in _PANEL

    def test_no_db_write_js(self) -> None:
        for needle in (
            "INSERT INTO",
            "UPDATE ",
            "/api/v1/admin/crm/price-estimates",
        ):
            assert needle not in _PANEL


class TestNoInternalPricingLeak:
    def test_no_default_base_prices_text(self) -> None:
        assert "DEFAULT_BASE_PRICES" not in _PANEL
        assert "default_base_prices" not in _PANEL.lower()

    def test_no_ceiling_category_enum_text(self) -> None:
        assert "CeilingCategory" not in _PANEL


class TestNoSecretsInPanel:
    def test_no_api_key_text(self) -> None:
        assert "api_key" not in _PANEL

    def test_no_bot_token_text(self) -> None:
        assert "bot_token" not in _PANEL

    def test_no_db_url_text(self) -> None:
        assert "postgres://" not in _PANEL

    def test_no_session_hash_text(self) -> None:
        assert "session_hash" not in _PANEL


class TestStylingClasses:
    def test_uses_vp_input(self) -> None:
        assert "vp-input" in _PANEL

    def test_uses_vp_select(self) -> None:
        assert "vp-select" in _PANEL

    def test_uses_vp_btn_primary(self) -> None:
        assert "vp-btn-primary" in _PANEL

    def test_uses_vp_badge(self) -> None:
        assert "vp-badge" in _PANEL

    def test_uses_vp_empty_state(self) -> None:
        assert "vp-empty-state" in _PANEL


class TestRouteWiring:
    def test_route_imports_builder(self) -> None:
        main_text = Path("apps/web/main.py").read_text(encoding="utf-8")
        assert "build_contact_price_estimate" in main_text

    def test_route_accepts_calc_params(self) -> None:
        main_text = Path("apps/web/main.py").read_text(encoding="utf-8")
        assert "calc_area" in main_text
        assert "calc_design" in main_text
        assert "calc_addons" in main_text

    def test_route_passes_calculator_result(self) -> None:
        main_text = Path("apps/web/main.py").read_text(encoding="utf-8")
        assert '"calculator_result"' in main_text
        assert '"calculator_designs"' in main_text
        assert '"calculator_addons"' in main_text
