"""Tests for Step CH — Payment Handler."""

from __future__ import annotations

from pathlib import Path


def _src() -> str:
    return Path("apps/bot/handlers/private/payment.py").read_text(encoding="utf-8")


class TestModuleImports:
    def test_importable(self):
        from apps.bot.handlers.private import payment

        assert payment is not None

    def test_router(self):
        from apps.bot.handlers.private.payment import router

        assert router is not None


class TestPaymentEntry:
    def test_entry_handler(self):
        assert "cmd_payment_start" in _src()

    def test_entry_button(self):
        assert "To'lov" in _src()


class TestPaymentFSM:
    def test_fsm_states(self):
        from apps.bot.handlers.private.payment import PaymentSubmitFSM

        assert hasattr(PaymentSubmitFSM, "waiting_amount")
        assert hasattr(PaymentSubmitFSM, "waiting_proof")


class TestAmountStep:
    def test_handle_amount(self):
        assert "handle_payment_amount" in _src()

    def test_amount_validation(self):
        c = _src()
        assert "int(" in c or "isdigit" in c


class TestProofStep:
    def test_photo_handler(self):
        assert "handle_payment_proof_photo" in _src()

    def test_document_handler(self):
        assert "handle_payment_proof_document" in _src()

    def test_fallback_handler(self):
        assert "handle_payment_proof_fallback" in _src()


class TestSaveAndConfirm:
    def test_save_function(self):
        assert "_save_and_confirm" in _src()

    def test_payment_service(self):
        assert "payment_service" in _src() or "create_payment" in _src()


class TestAdminNotify:
    def test_admin_notify(self):
        assert "_notify_admin" in _src()

    def test_approve_callback(self):
        assert "pay:a:" in _src()

    def test_reject_callback(self):
        assert "pay:r:" in _src()


class TestSafety:
    def test_no_card_secret(self):
        c = _src()
        assert "card_number" not in c or "settings" in c

    def test_no_token_leak(self):
        assert "sk-" not in _src()
        assert "BOT_TOKEN" not in _src()

    def test_no_real_payment_call(self):
        c = _src()
        assert "stripe" not in c.lower()
        assert "paypal" not in c.lower()

    def test_main_menu_on_complete(self):
        c = _src()
        assert "my_orders_keyboard" in c or "main_menu" in c


class TestRouterSmoke:
    def test_registration(self):
        c = Path("apps/bot/main.py").read_text(encoding="utf-8")
        assert "payment" in c
