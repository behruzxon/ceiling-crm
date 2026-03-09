"""Tests that core.services.ai_engine exports the expected symbols and that
apps.bot.handlers.private.ai_openai re-exports them (same function objects).
"""
from __future__ import annotations


class TestAiEngineImports:
    def test_check_ai_rate_limit_importable(self) -> None:
        from core.services.ai_engine import check_ai_rate_limit
        import asyncio
        assert callable(check_ai_rate_limit)

    def test_call_ai_importable(self) -> None:
        from core.services.ai_engine import _call_ai
        assert callable(_call_ai)

    def test_load_context_importable(self) -> None:
        from core.services.ai_engine import _load_context
        assert callable(_load_context)

    def test_persist_exchange_importable(self) -> None:
        from core.services.ai_engine import _persist_exchange
        assert callable(_persist_exchange)

    def test_build_context_block_importable(self) -> None:
        from core.services.ai_engine import _build_context_block
        assert callable(_build_context_block)

    def test_clear_ai_conversation_importable(self) -> None:
        from core.services.ai_engine import clear_ai_conversation
        assert callable(clear_ai_conversation)

    def test_store_user_message_only_importable(self) -> None:
        from core.services.ai_engine import _store_user_message_only
        assert callable(_store_user_message_only)

    def test_constants_present(self) -> None:
        from core.services.ai_engine import (
            _MAX_MESSAGES,
            _HISTORY_TO_SEND,
            _SUMMARY_EVERY_N_TURNS,
        )
        assert isinstance(_MAX_MESSAGES, int)
        assert isinstance(_HISTORY_TO_SEND, int)
        assert isinstance(_SUMMARY_EVERY_N_TURNS, int)


class TestAiOpenaiReexports:
    """Verify that apps.bot re-exports resolve to the exact same objects."""

    def test_check_ai_rate_limit_same_object(self) -> None:
        from core.services.ai_engine import check_ai_rate_limit as engine_fn
        from apps.bot.handlers.private.ai_openai import check_ai_rate_limit as bot_fn
        assert engine_fn is bot_fn

    def test_call_ai_same_object(self) -> None:
        from core.services.ai_engine import _call_ai as engine_fn
        from apps.bot.handlers.private.ai_openai import _call_ai as bot_fn
        assert engine_fn is bot_fn

    def test_load_context_same_object(self) -> None:
        from core.services.ai_engine import _load_context as engine_fn
        from apps.bot.handlers.private.ai_openai import _load_context as bot_fn
        assert engine_fn is bot_fn

    def test_persist_exchange_same_object(self) -> None:
        from core.services.ai_engine import _persist_exchange as engine_fn
        from apps.bot.handlers.private.ai_openai import _persist_exchange as bot_fn
        assert engine_fn is bot_fn

    def test_clear_ai_conversation_same_object(self) -> None:
        from core.services.ai_engine import clear_ai_conversation as engine_fn
        from apps.bot.handlers.private.ai_openai import clear_ai_conversation as bot_fn
        assert engine_fn is bot_fn
