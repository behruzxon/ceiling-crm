"""
shared.utils.telegram_send
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Resilient wrapper for Telegram Bot API sends.

Handles:
- Network errors (aiohttp connectivity)
- Rate limit errors (TelegramRetryAfter — honours Telegram's retry_after)
- Temporary server errors (TelegramServerError)

Usage:
    from shared.utils.telegram_send import safe_send_message

    ok = await safe_send_message(bot, chat_id, text, reply_markup=kb)
"""
from __future__ import annotations

import asyncio
from typing import Any

from shared.logging import get_logger

log = get_logger(__name__)

_MAX_RETRIES = 3
_BASE_DELAY = 1.0


async def safe_send_message(
    bot: Any,
    chat_id: int,
    text: str,
    *,
    max_retries: int = _MAX_RETRIES,
    **kwargs: Any,
) -> bool:
    """Send a message with retry on transient errors. Returns True on success."""
    return await _retry_send(
        bot.send_message, chat_id, text, max_retries=max_retries, **kwargs
    )


async def safe_edit_message_text(
    bot: Any,
    text: str,
    *,
    chat_id: int | None = None,
    message_id: int | None = None,
    max_retries: int = _MAX_RETRIES,
    **kwargs: Any,
) -> bool:
    """Edit a message with retry on transient errors. Returns True on success."""
    return await _retry_send(
        bot.edit_message_text,
        text,
        chat_id=chat_id,
        message_id=message_id,
        max_retries=max_retries,
        **kwargs,
    )


async def safe_send_photo(
    bot: Any,
    chat_id: int,
    photo: Any,
    *,
    max_retries: int = _MAX_RETRIES,
    **kwargs: Any,
) -> bool:
    """Send a photo with retry on transient errors. Returns True on success."""
    return await _retry_send(
        bot.send_photo, chat_id, photo, max_retries=max_retries, **kwargs
    )


async def _retry_send(
    method: Any,
    *args: Any,
    max_retries: int = _MAX_RETRIES,
    **kwargs: Any,
) -> bool:
    """Internal: call a Bot API method with retry logic.

    Handles:
    - TelegramRetryAfter: sleep for the specified duration, then retry
    - Network/server errors: exponential backoff
    - TelegramForbiddenError / TelegramBadRequest: no retry (permanent)
    """
    from aiogram.exceptions import (
        TelegramBadRequest,
        TelegramForbiddenError,
        TelegramNetworkError,
        TelegramRetryAfter,
        TelegramServerError,
    )

    delay = _BASE_DELAY
    method_name = getattr(method, "__name__", "send")

    for attempt in range(1, max_retries + 2):
        try:
            await method(*args, **kwargs)
            return True
        except TelegramRetryAfter as exc:
            # Telegram tells us exactly how long to wait
            wait = exc.retry_after + 1
            if attempt > max_retries:
                log.warning(
                    "telegram_send_rate_limit_exhausted",
                    method=method_name,
                    retry_after=exc.retry_after,
                )
                return False
            log.info(
                "telegram_send_rate_limited",
                method=method_name,
                attempt=attempt,
                retry_after=wait,
            )
            await asyncio.sleep(wait)
        except TelegramForbiddenError:
            # User blocked bot or chat deleted — don't retry
            return False
        except TelegramBadRequest as exc:
            # Malformed request — don't retry
            log.warning("telegram_send_bad_request", method=method_name, error=str(exc))
            return False
        except (TelegramNetworkError, TelegramServerError, OSError) as exc:
            if attempt > max_retries:
                log.warning(
                    "telegram_send_exhausted",
                    method=method_name,
                    attempts=attempt,
                    error=str(exc),
                )
                return False
            log.info(
                "telegram_send_retry",
                method=method_name,
                attempt=attempt,
                delay=delay,
                error=str(exc),
            )
            await asyncio.sleep(delay)
            delay *= 2

    return False
