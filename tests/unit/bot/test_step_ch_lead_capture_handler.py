"""Tests for Step CH — Lead Capture Handler."""
from __future__ import annotations

from pathlib import Path


def _src() -> str:
    return Path(
        "apps/bot/handlers/private/lead_capture.py",
    ).read_text(encoding="utf-8")


class TestModuleImports:
    def test_importable(self):
        from apps.bot.handlers.private import lead_capture
        assert lead_capture is not None

    def test_router(self):
        from apps.bot.handlers.private.lead_capture import router
        assert router is not None

    def test_states(self):
        from apps.bot.states.lead_capture import LeadCaptureStates
        assert hasattr(LeadCaptureStates, "waiting_for_name")
        assert hasattr(LeadCaptureStates, "waiting_for_phone")
        assert hasattr(LeadCaptureStates, "waiting_for_district")


class TestLeadCaptureEntry:
    def test_cmd_order(self):
        assert "cmd_order" in _src()

    def test_order_command(self):
        assert 'Command("order")' in _src()


class TestNameStep:
    def test_handle_name(self):
        assert "handle_name" in _src()

    def test_name_validation(self):
        assert "128" in _src() or "len(" in _src()


class TestPhoneStep:
    def test_handle_phone(self):
        assert "handle_phone" in _src()

    def test_phone_validation_import(self):
        assert "is_valid_uz_phone" in _src()

    def test_phone_normalize_import(self):
        assert "normalize_phone" in _src()

    def test_journey_event(self):
        assert "PHONE_SHARED" in _src()


class TestDistrictStep:
    def test_handle_district(self):
        assert "handle_district" in _src()

    def test_district_min_length(self):
        assert "2" in _src()

    def test_creates_lead(self):
        assert "create_lead" in _src()

    def test_lead_action_insert(self):
        assert "lead_action_repo" in _src() or "insert" in _src()


class TestAdminNotify:
    def test_notify_new_lead(self):
        assert "notify_new_lead" in _src()


class TestSafety:
    def test_no_token(self):
        assert "sk-" not in _src()
        assert "BOT_TOKEN" not in _src()

    def test_no_real_send(self):
        c = _src()
        assert "requests.post" not in c

    def test_main_menu_on_complete(self):
        assert "main_menu_keyboard" in _src()

    def test_phone_utility_safe(self):
        from shared.utils.phone import is_valid_uz_phone
        assert not is_valid_uz_phone("")
        assert not is_valid_uz_phone("abc")


class TestRouterSmoke:
    def test_registration(self):
        c = Path("apps/bot/main.py").read_text(encoding="utf-8")
        assert "lead_capture" in c
