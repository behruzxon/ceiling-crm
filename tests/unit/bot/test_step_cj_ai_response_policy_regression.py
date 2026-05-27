"""Tests for Step CJ — AI Response Policy Regression."""
from __future__ import annotations


class TestAIHelpUnchanged:
    def test_help_text_imports(self):
        from apps.bot.handlers.private.ai_states import _AI_HELP_TEXT
        assert "Narx" in _AI_HELP_TEXT

    def test_keyboard_unchanged(self):
        from apps.bot.handlers.private.ai_states import _ai_keyboard
        kb = _ai_keyboard()
        flat = [btn.text for row in kb.keyboard for btn in row]
        assert len(flat) == 6


class TestCatalogUnchanged:
    def test_catalog_router(self):
        from apps.bot.handlers.private.catalog import router
        assert router is not None

    def test_catalog_constants(self):
        from shared.constants.catalog import CATALOG
        assert len(CATALOG) >= 5


class TestPriceButtonUnchanged:
    def test_btn_price_constant(self):
        from apps.bot.handlers.private.ai_states import BTN_AI_PRICE
        assert BTN_AI_PRICE == "💰 Narx"


class TestOperatorButtonUnchanged:
    def test_btn_operator_constant(self):
        from apps.bot.handlers.private.ai_states import BTN_AI_OPERATOR
        assert "Operator" in BTN_AI_OPERATOR


class TestResetButtonUnchanged:
    def test_btn_reset_constant(self):
        from apps.bot.handlers.private.ai_states import BTN_AI_RESET
        assert "Reset" in BTN_AI_RESET


class TestHandlerImports:
    def test_ai_support(self):
        from apps.bot.handlers.private import ai_support
        assert ai_support is not None

    def test_cmd_ai_start(self):
        from apps.bot.handlers.private.ai_support import cmd_ai_start
        assert callable(cmd_ai_start)

    def test_cmd_ai_help(self):
        from apps.bot.handlers.private.ai_support import cmd_ai_help
        assert callable(cmd_ai_help)

    def test_cmd_ai_reset(self):
        from apps.bot.handlers.private.ai_support import cmd_ai_reset
        assert callable(cmd_ai_reset)

    def test_clear_conversation(self):
        from apps.bot.handlers.private.ai_support import (
            clear_ai_conversation,
        )
        assert callable(clear_ai_conversation)


class TestDispatcherSmoke:
    def test_build_dispatcher(self):
        from apps.bot.main import build_dispatcher
        assert callable(build_dispatcher)

    def test_bot_commands_count(self):
        from apps.bot.main import BOT_COMMANDS
        assert len(BOT_COMMANDS) >= 10


class TestScoringUnchanged:
    def test_classify_score(self):
        from apps.bot.handlers.private.ai_scoring import classify_score
        assert classify_score(60) == "hot"
        assert classify_score(30) == "warm"
        assert classify_score(0) == "cold"

    def test_detect_objection(self):
        from apps.bot.handlers.private.ai_scoring import detect_objection
        assert detect_objection("qimmat ekan") == "expensive"


class TestDetectionUnchanged:
    def test_price_query(self):
        from apps.bot.handlers.private.ai_detection import _is_price_query
        assert _is_price_query("narx qancha")

    def test_catalog_request(self):
        from apps.bot.handlers.private.ai_detection import (
            _is_catalog_request,
        )
        assert _is_catalog_request("katalog")

    def test_greeting(self):
        from apps.bot.handlers.private.ai_detection import _is_greeting
        assert _is_greeting("salom")


class TestSchedulerUnchanged:
    def test_scheduler_import(self):
        import apps.scheduler.main
        assert apps.scheduler.main is not None


class TestNoNewFlags:
    def test_no_new_enabled_flags(self):
        from shared.config.settings import BusinessSettings
        fields = BusinessSettings.model_fields
        for name in [
            "agent_followups_enabled",
            "agent_execution_live_sender_enabled",
            "crm_campaign_send_enabled",
        ]:
            assert fields[name].default is False
