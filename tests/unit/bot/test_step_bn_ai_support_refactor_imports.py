"""Tests for Step BN — AI Support Handler Refactor imports."""
from __future__ import annotations


class TestModuleImports:
    def test_ai_support_imports(self):
        from apps.bot.handlers.private import ai_support
        assert ai_support is not None

    def test_router_exists(self):
        from apps.bot.handlers.private.ai_support import router
        assert router is not None
        assert router.name == "private:ai_support"

    def test_states_importable(self):
        from apps.bot.handlers.private.ai_support import AiSupportStates
        assert AiSupportStates is not None

    def test_cmd_ai_start_importable(self):
        from apps.bot.handlers.private.ai_support import cmd_ai_start
        assert callable(cmd_ai_start)

    def test_clear_ai_conversation_importable(self):
        from apps.bot.handlers.private.ai_support import clear_ai_conversation
        assert callable(clear_ai_conversation)


class TestAgentModuleImports:
    def test_agent_module_importable(self):
        from apps.bot.handlers.private import ai_support_agent
        assert ai_support_agent is not None

    def test_run_orchestrator(self):
        from apps.bot.handlers.private.ai_support_agent import _run_orchestrator
        assert callable(_run_orchestrator)

    def test_process_lead_signal(self):
        from apps.bot.handlers.private.ai_support_agent import _process_lead_signal
        assert callable(_process_lead_signal)

    def test_re_exported_from_ai_support(self):
        from apps.bot.handlers.private.ai_support import _process_lead_signal, _run_orchestrator
        assert callable(_run_orchestrator)
        assert callable(_process_lead_signal)


class TestAutoReplyModuleImports:
    def test_auto_reply_module_importable(self):
        from apps.bot.handlers.private import ai_support_auto_reply
        assert ai_support_auto_reply is not None

    def test_check_ai_rate_limit(self):
        from apps.bot.handlers.private.ai_support_auto_reply import _check_ai_rate_limit
        assert callable(_check_ai_rate_limit)

    def test_try_auto_reply(self):
        from apps.bot.handlers.private.ai_support_auto_reply import _try_auto_reply
        assert callable(_try_auto_reply)

    def test_detect_simple_intent(self):
        from apps.bot.handlers.private.ai_support_auto_reply import _detect_simple_intent
        assert callable(_detect_simple_intent)

    def test_reset_auto_reply_counter(self):
        from apps.bot.handlers.private.ai_support_auto_reply import _reset_auto_reply_counter
        assert callable(_reset_auto_reply_counter)

    def test_re_exported_from_ai_support(self):
        from apps.bot.handlers.private.ai_support import (
            _check_ai_rate_limit,
            _try_auto_reply,
        )
        assert callable(_check_ai_rate_limit)
        assert callable(_try_auto_reply)


class TestExistingPublicSymbols:
    def test_load_ai_memory(self):
        from apps.bot.handlers.private.ai_support import _load_ai_memory
        assert callable(_load_ai_memory)

    def test_get_lead_score(self):
        from apps.bot.handlers.private.ai_support import _get_lead_score
        assert callable(_get_lead_score)

    def test_add_lead_score(self):
        from apps.bot.handlers.private.ai_support import _add_lead_score
        assert callable(_add_lead_score)


class TestNoCircularImport:
    def test_agent_module_independent(self):
        import importlib
        mod = importlib.import_module("apps.bot.handlers.private.ai_support_agent")
        assert mod is not None

    def test_auto_reply_module_independent(self):
        import importlib
        mod = importlib.import_module("apps.bot.handlers.private.ai_support_auto_reply")
        assert mod is not None


class TestDetectSimpleIntent:
    def test_price(self):
        from apps.bot.handlers.private.ai_support_auto_reply import _detect_simple_intent
        assert _detect_simple_intent("narx qancha") == "price"

    def test_material(self):
        from apps.bot.handlers.private.ai_support_auto_reply import _detect_simple_intent
        assert _detect_simple_intent("qanday dizayn bor") == "material"

    def test_package(self):
        from apps.bot.handlers.private.ai_support_auto_reply import _detect_simple_intent
        assert _detect_simple_intent("tayyor paket bormi") == "package"

    def test_unknown(self):
        from apps.bot.handlers.private.ai_support_auto_reply import _detect_simple_intent
        assert _detect_simple_intent("salom") is None


class TestSmoke:
    def test_scheduler(self):
        import apps.scheduler.main
        assert apps.scheduler.main is not None

    def test_doc_exists(self):
        from pathlib import Path
        assert Path("docs/AI_AGENT_SYSTEM/73_AI_SUPPORT_HANDLER_REFACTOR.md").exists()
