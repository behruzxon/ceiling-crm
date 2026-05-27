"""Tests for Step CO — Operator Handoff Bot Wiring."""
from __future__ import annotations

from pathlib import Path

from core.services.crm_operator_handoff_service import (
    build_user_message,
    mask_phone,
    sanitize_message_preview,
)


def _src() -> str:
    return Path(
        "apps/bot/handlers/private/ai_support.py",
    ).read_text(encoding="utf-8")


class TestWiringExists:
    def test_try_operator_handoff_exists(self):
        assert "_try_operator_handoff" in _src()

    def test_handoff_service_import(self):
        assert "build_user_message" in _src()

    def test_queue_enabled_check(self):
        assert "crm_operator_handoff_queue_enabled" in _src()

    def test_fallback_on_error(self):
        c = _src()
        assert "_AI_OPERATOR_PROMPT" in c

    def test_ai_button_handler_wired(self):
        c = _src()
        assert "handle_ai_operator_btn" in c
        assert "_try_operator_handoff" in c


class TestUserMessages:
    def test_phone_missing_asks_phone(self):
        msg = build_user_message(has_phone=False)
        assert "telefon" in msg.lower()

    def test_phone_exists_operator_reviews(self):
        msg = build_user_message(has_phone=True)
        assert "ko'rib chiqadi" in msg

    def test_duplicate_safe(self):
        msg = build_user_message(has_phone=True, is_duplicate=True)
        assert "yuborilgan" in msg


class TestNoFakeETA:
    def test_no_hozir_missing(self):
        msg = build_user_message(has_phone=False)
        assert "hozir" not in msg.lower()

    def test_no_hozir_exists(self):
        msg = build_user_message(has_phone=True)
        assert "hozir" not in msg.lower()

    def test_no_darhol_missing(self):
        msg = build_user_message(has_phone=False)
        assert "darhol" not in msg.lower()

    def test_no_darhol_exists(self):
        msg = build_user_message(has_phone=True)
        assert "darhol" not in msg.lower()

    def test_no_bugun_missing(self):
        msg = build_user_message(has_phone=False)
        assert "bugun" not in msg.lower()

    def test_no_bugun_exists(self):
        msg = build_user_message(has_phone=True)
        assert "bugun" not in msg.lower()

    def test_no_bugun_duplicate(self):
        msg = build_user_message(has_phone=True, is_duplicate=True)
        assert "bugun" not in msg.lower()


class TestPhoneMasking:
    def test_mask(self):
        r = mask_phone("+998901234567")
        assert "****" in r
        assert "+998901234567" != r

    def test_mask_preserves_ends(self):
        r = mask_phone("+998901234567")
        assert r.startswith("+998")
        assert r.endswith("67")


class TestPreviewSanitize:
    def test_token_redacted(self):
        r = sanitize_message_preview("my sk-abc12345678xyz key")
        assert "sk-abc" not in r
        assert "[REDACTED]" in r

    def test_clean_text(self):
        r = sanitize_message_preview("operator kerak")
        assert r == "operator kerak"

    def test_truncated(self):
        r = sanitize_message_preview("a" * 300)
        assert len(r) == 200


class TestStopNotHandoff:
    def test_stop_before_operator(self):
        c = _src()
        lines = c.splitlines()
        obj_idx = next(
            (i for i, ln in enumerate(lines) if "detect_objection" in ln),
            0,
        )
        op_idx = next(
            (i for i, ln in enumerate(lines)
             if "_try_operator_handoff" in ln and "def " not in ln),
            9999,
        )
        assert obj_idx < op_idx


class TestAIKeyboardPreserved:
    def test_keyboard_size(self):
        from apps.bot.handlers.private.ai_states import _ai_keyboard
        kb = _ai_keyboard()
        flat = [btn.text for row in kb.keyboard for btn in row]
        assert len(flat) == 6

    def test_operator_button_still_exists(self):
        from apps.bot.handlers.private.ai_states import BTN_AI_OPERATOR
        assert "Operator" in BTN_AI_OPERATOR


class TestConfigFlags:
    def test_queue_enabled_default(self):
        from shared.config.settings import BusinessSettings
        f = BusinessSettings.model_fields
        assert f["crm_operator_handoff_queue_enabled"].default is True

    def test_admin_notify_disabled(self):
        from shared.config.settings import BusinessSettings
        f = BusinessSettings.model_fields
        assert f["crm_operator_handoff_admin_notify_enabled"].default is False


class TestSmoke:
    def test_dispatcher(self):
        from apps.bot.main import build_dispatcher
        assert build_dispatcher is not None

    def test_ai_support(self):
        from apps.bot.handlers.private import ai_support
        assert ai_support is not None

    def test_scheduler(self):
        import apps.scheduler.main
        assert apps.scheduler.main is not None
