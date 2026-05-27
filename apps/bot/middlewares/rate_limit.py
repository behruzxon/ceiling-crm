"""
Rate limit middleware.
Prevents abuse using Redis sliding window counter.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from infrastructure.cache.client import get_redis
from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """
    Per-user rate limiting using Redis sliding window counter.
    Throttled users receive a polite message instead of processing.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)

        settings = get_settings()
        cache = get_redis()
        user_id = tg_user.id

        is_allowed, remaining = await cache.rate_limit_check(
            identifier=f"user:{user_id}",
            window_seconds=settings.rate_limit.window_seconds,
            max_requests=settings.rate_limit.max_requests,
        )

        if not is_allowed:
            log.warning("rate_limited", user_id=user_id, remaining=remaining)
            # Try to send throttle message if the event has a reply method
            if hasattr(event, "answer"):
                await event.answer(  # type: ignore[attr-defined]
                    f"⏳ Iltimos, {settings.rate_limit.window_seconds} "
                    "soniyadan so'ng qayta urinib ko'ring."
                )
            return None

        return await handler(event, data)
