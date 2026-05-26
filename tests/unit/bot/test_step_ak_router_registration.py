"""Tests for Step AK — Agent execution callback router registration."""
from __future__ import annotations


class TestRouterRegistration:
    def test_callback_router_importable(self):
        from apps.bot.handlers.callbacks.agent_execution_callbacks import router
        assert router.name == "callbacks:agent_execution"

    def test_callback_imported_in_main(self):
        import apps.bot.main as m
        assert hasattr(m, "agent_execution_callbacks_router")

    def test_bot_main_importable(self):
        import apps.bot.main
        assert apps.bot.main is not None

    def test_non_admin_check_exists(self):
        from apps.bot.handlers.callbacks.agent_execution_callbacks import (
            _is_admin,
        )
        assert callable(_is_admin)

    def test_approve_handler_exists(self):
        from apps.bot.handlers.callbacks.agent_execution_callbacks import (
            cb_approve,
        )
        assert callable(cb_approve)

    def test_reject_handler_exists(self):
        from apps.bot.handlers.callbacks.agent_execution_callbacks import (
            cb_reject,
        )
        assert callable(cb_reject)

    def test_view_handler_exists(self):
        from apps.bot.handlers.callbacks.agent_execution_callbacks import (
            cb_view,
        )
        assert callable(cb_view)

    def test_registration_does_not_enable_execution(self):
        from shared.config.settings import BusinessSettings
        assert BusinessSettings.model_fields[
            "agent_execution_queue_enabled"
        ].default is False
        assert BusinessSettings.model_fields[
            "agent_execution_live_sender_enabled"
        ].default is False
