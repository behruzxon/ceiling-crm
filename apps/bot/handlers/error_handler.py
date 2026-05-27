"""
apps.bot.handlers.error_handler
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Global error handler for the bot dispatcher.
Catches unhandled exceptions from all handlers and persists them
to the system_errors table via the centralized error logger.
"""

from __future__ import annotations

import asyncio
from typing import Any

from aiogram import Dispatcher
from aiogram.types import ErrorEvent

from shared.logging import get_logger

log = get_logger(__name__)


def register_error_handler(dp: Dispatcher) -> None:
    """Register a catch-all error handler on the dispatcher."""

    @dp.errors()
    async def _global_error_handler(event: ErrorEvent, **data: Any) -> bool:
        """Log unhandled handler exceptions to system_errors table."""
        exc = event.exception
        update = event.update

        # Extract useful context for the log
        user_id: int | None = None
        chat_id: int | None = None
        handler_name: str = "unknown"

        if update.message:
            user_id = update.message.from_user.id if update.message.from_user else None
            chat_id = update.message.chat.id
        elif update.callback_query:
            user_id = update.callback_query.from_user.id
            cb_data = update.callback_query.data or ""
            handler_name = f"callback:{cb_data[:30]}"

        log.exception(
            "unhandled_handler_error",
            user_id=user_id,
            chat_id=chat_id,
            handler=handler_name,
            error_type=type(exc).__name__,
        )

        # Persist to system_errors (fire-and-forget)
        asyncio.create_task(_persist_error(exc, user_id, handler_name))

        # Return True to suppress default error propagation
        return True


async def _persist_error(exc: BaseException, user_id: int | None, handler_name: str) -> None:
    """Fire-and-forget: write to system_errors. Never raises."""
    try:
        from infrastructure.error_logger import log_system_error

        msg = f"user={user_id} handler={handler_name}: {exc}"
        await log_system_error("bot", exc, message=msg)
    except Exception:
        pass
