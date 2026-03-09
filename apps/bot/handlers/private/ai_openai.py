"""
apps.bot.handlers.private.ai_openai
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Re-exports the channel-agnostic AI engine from ``core.services.ai_engine``.

All Telegram bot handlers continue to import from this module unchanged.
The actual implementation lives in ``core/services/ai_engine.py``.
"""
from __future__ import annotations

# Re-export everything the bot (and tests) import from this module.
from core.services.ai_engine import (  # noqa: F401
    _MAX_MESSAGES,
    _HISTORY_TO_SEND,
    _SUMMARY_EVERY_N_TURNS,
    _SAFETY_SUFFIX,
    _get_client,
    check_ai_rate_limit,
    _build_context_block,
    _load_context,
    _regenerate_summary,
    _persist_exchange,
    clear_ai_conversation,
    _store_user_message_only,
    _call_ai,
)
