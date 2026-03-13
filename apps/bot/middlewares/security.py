"""
apps.bot.middlewares.security
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Guards against abuse: burst spam, oversized messages, and suspicious callback data.

Runs AFTER AuthMiddleware (needs user_id) and BEFORE RateLimitMiddleware
(catches fast-burst before the sliding window does).
"""
from __future__ import annotations

import re
import time
from collections import defaultdict
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from shared.logging import get_logger

log = get_logger(__name__)

# ── Tuneable constants ───────────────────────────────────────────────────────

_BURST_WINDOW = 3          # seconds
_BURST_MAX = 5             # max messages within burst window
_MAX_TEXT_LENGTH = 4096    # Telegram limit
_MAX_CALLBACK_LENGTH = 64  # callback_data max in Telegram is 64 bytes

# Only allow safe characters in callback data (alphanumeric, :, _, -, .)
_CALLBACK_SAFE_RE = re.compile(r"^[a-zA-Z0-9:_.\-]+$")

# ── In-memory burst tracker ──────────────────────────────────────────────────
# Dict of user_id → list of timestamps.  Cleaned lazily.
_burst_tracker: dict[int, list[float]] = defaultdict(list)


def _is_burst(user_id: int) -> bool:
    """Check if user is sending messages in a fast burst."""
    now = time.monotonic()
    timestamps = _burst_tracker[user_id]

    # Prune old entries
    cutoff = now - _BURST_WINDOW
    timestamps[:] = [t for t in timestamps if t > cutoff]

    timestamps.append(now)
    return len(timestamps) > _BURST_MAX


class SecurityMiddleware(BaseMiddleware):
    """Anti-abuse middleware: burst detection, size limits, callback sanitisation."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        user_id = tg_user.id if tg_user else None

        # ── 1. Burst protection ──────────────────────────────────────────
        if user_id and _is_burst(user_id):
            log.warning("security_burst_blocked", user_id=user_id)
            return None  # silently drop

        # ── 2. Message size limit ────────────────────────────────────────
        if isinstance(event, Message) and event.text:
            if len(event.text) > _MAX_TEXT_LENGTH:
                log.warning(
                    "security_oversized_message",
                    user_id=user_id,
                    length=len(event.text),
                )
                return None

        # ── 3. Callback data sanitisation ────────────────────────────────
        if isinstance(event, CallbackQuery) and event.data:
            cb_data = event.data
            if len(cb_data) > _MAX_CALLBACK_LENGTH:
                log.warning(
                    "security_callback_too_long",
                    user_id=user_id,
                    length=len(cb_data),
                )
                await event.answer("⚠️ Noto'g'ri so'rov", show_alert=False)
                return None

            if not _CALLBACK_SAFE_RE.match(cb_data):
                log.warning(
                    "security_callback_suspicious",
                    user_id=user_id,
                    callback_data=cb_data[:30],
                )
                await event.answer("⚠️ Noto'g'ri so'rov", show_alert=False)
                return None

        return await handler(event, data)
