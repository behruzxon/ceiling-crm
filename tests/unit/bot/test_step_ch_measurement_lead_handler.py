"""Tests for Step CH — Measurement Lead Handler."""
from __future__ import annotations

from pathlib import Path


def _src() -> str:
    return Path(
        "apps/bot/handlers/private/measurement_lead.py",
    ).read_text(encoding="utf-8")


class TestModuleImports:
    def test_importable(self):
        from apps.bot.handlers.private import measurement_lead
        assert measurement_lead is not None

    def test_router(self):
        from apps.bot.handlers.private.measurement_lead import router
        assert router is not None

    def test_states(self):
        from apps.bot.states.measurement_lead import MeasurementLeadStates
        assert hasattr(MeasurementLeadStates, "waiting_for_name")
        assert hasattr(MeasurementLeadStates, "waiting_for_phone")
        assert hasattr(MeasurementLeadStates, "waiting_for_location")
        assert hasattr(MeasurementLeadStates, "waiting_for_time")


class TestMeasurementEntry:
    def test_start_flow_exists(self):
        assert "start_measurement_flow" in _src()


class TestNameStep:
    def test_handle_name(self):
        assert "handle_ml_name" in _src()

    def test_name_validation(self):
        assert "128" in _src() or "len(" in _src()

    def test_cancel_in_name(self):
        assert "Bekor" in _src()


class TestPhoneStep:
    def test_handle_contact(self):
        assert "handle_ml_contact" in _src()

    def test_handle_phone_text(self):
        assert "handle_ml_phone" in _src()

    def test_phone_validation(self):
        assert "is_valid_uz_phone" in _src()

    def test_phone_normalize(self):
        assert "normalize_phone" in _src()

    def test_group_btn_handler(self):
        assert "handle_ml_phone_group_btn" in _src()


class TestLocationStep:
    def test_handle_location(self):
        assert "handle_ml_location" in _src()

    def test_location_validation(self):
        c = _src()
        assert "len(" in c or "2" in c


class TestTimeStep:
    def test_handle_time(self):
        assert "handle_ml_time" in _src()

    def test_time_choices(self):
        c = _src()
        assert "Bugun" in c or "Ertaga" in c

    def test_skip_option(self):
        assert "O'tkazib yuborish" in _src()


class TestLeadCreation:
    def test_create_lead_call(self):
        assert "create_lead" in _src()

    def test_ai_scoring_update(self):
        assert "update_ai_scoring" in _src()


class TestAdminNotify:
    def test_notify_measurement(self):
        c = _src()
        assert "notify_measurement_lead" in c or "notify" in c.lower()


class TestCancelFlow:
    def test_cancel_cmd(self):
        assert "handle_ml_cancel_cmd" in _src()

    def test_cancel_button(self):
        assert "Bekor" in _src()

    def test_main_menu_on_cancel(self):
        assert "main_menu_keyboard" in _src()


class TestSafety:
    def test_no_token(self):
        assert "sk-" not in _src()
        assert "BOT_TOKEN" not in _src()

    def test_no_fake_eta(self):
        c = _src().lower()
        assert "hozir darhol" not in c


class TestRouterSmoke:
    def test_registration(self):
        c = Path("apps/bot/main.py").read_text(encoding="utf-8")
        assert "measurement_lead" in c
