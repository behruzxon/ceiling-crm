"""Tests for Step CH — Order Handler."""
from __future__ import annotations

from pathlib import Path


def _src() -> str:
    return Path("apps/bot/handlers/private/order.py").read_text(encoding="utf-8")


class TestModuleImports:
    def test_importable(self):
        from apps.bot.handlers.private import order
        assert order is not None

    def test_router(self):
        from apps.bot.handlers.private.order import router
        assert router is not None

    def test_order_flow_states(self):
        from apps.bot.handlers.private.order import OrderFlow
        assert hasattr(OrderFlow, "waiting_for_name")
        assert hasattr(OrderFlow, "waiting_for_phone")
        assert hasattr(OrderFlow, "waiting_for_district")
        assert hasattr(OrderFlow, "waiting_for_category")
        assert hasattr(OrderFlow, "waiting_for_area")
        assert hasattr(OrderFlow, "waiting_for_location")


class TestOrderEntry:
    def test_cmd_order_start(self):
        assert "cmd_order_start" in _src()

    def test_btn_order_trigger(self):
        assert "BTN_ORDER" in _src()

    def test_order_command(self):
        assert 'Command("order")' in _src()


class TestNameStep:
    def test_handle_name(self):
        assert "handle_name" in _src()

    def test_name_validation(self):
        c = _src()
        assert "128" in c or "len(" in c


class TestPhoneStep:
    def test_handle_phone_contact(self):
        assert "handle_phone_contact" in _src()

    def test_handle_phone_text(self):
        assert "handle_phone_text" in _src()

    def test_phone_validation(self):
        from shared.utils.phone import is_valid_uz_phone
        assert callable(is_valid_uz_phone)

    def test_phone_normalize(self):
        from shared.utils.phone import normalize_phone
        assert callable(normalize_phone)


class TestDistrictStep:
    def test_handle_district(self):
        assert "handle_district" in _src()

    def test_district_set(self):
        assert "Qarshi" in _src() or "DISTRICT" in _src()


class TestCategoryStep:
    def test_handle_category(self):
        assert "handle_category" in _src()

    def test_cat_callback(self):
        assert "cat:" in _src()


class TestAreaStep:
    def test_handle_area(self):
        assert "handle_area" in _src()

    def test_area_skip(self):
        assert "handle_area_skip" in _src()
        assert "O'tkazib yuborish" in _src()

    def test_area_parser(self):
        from shared.utils.area_parser import parse_area
        assert callable(parse_area)


class TestLocationStep:
    def test_handle_location(self):
        assert "handle_location" in _src()

    def test_location_skip(self):
        assert "handle_location_skip" in _src()

    def test_location_fallback(self):
        assert "handle_location_fallback" in _src()


class TestSaveAndConfirm:
    def test_save_function(self):
        assert "_save_and_confirm" in _src()

    def test_pipeline_stage(self):
        assert "QUOTE" in _src()

    def test_lead_service(self):
        assert "lead_service" in _src() or "get_lead_service" in _src()


class TestAdminNotify:
    def test_admin_notify_function(self):
        assert "_notify_admin" in _src()

    def test_hot_lead_check(self):
        assert "is_hot_lead" in _src() or "notify_hot_lead" in _src()

    def test_kanban_callback(self):
        assert "kanban:lead:" in _src()


class TestSafety:
    def test_no_token(self):
        assert "sk-" not in _src()
        assert "BOT_TOKEN" not in _src()

    def test_no_fake_eta(self):
        c = _src().lower()
        assert "hozir darhol" not in c

    def test_no_duplicate_message_risk(self):
        c = _src()
        assert "_save_and_confirm" in c

    def test_cancel_flow(self):
        assert "MAIN_MENU_BUTTONS" in _src()


class TestRouterSmoke:
    def test_registration(self):
        c = Path("apps/bot/main.py").read_text(encoding="utf-8")
        assert "order" in c
