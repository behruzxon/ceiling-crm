"""
apps.bot.middlewares.group_menu_injector
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Injects a selective ReplyKeyboard into group/supergroup chats the first time
a real human user sends a message — at most once per user per 24 hours.

WHY selective?
--------------
ReplyKeyboard in groups is per-user: only the user who triggered the command
sees it.  By using `selective=True` + `message.reply()` the keyboard is
delivered specifically to the replying-to user, avoiding confusion for other
members.

DEDUP strategy
--------------
A Redis key  `grp:menu:{chat_id}:{user_id}`  (TTL 24 h) tracks whether we
already showed the keyboard to this user today.  On every BTN_* tap the TTL
is refreshed so active users never see a "flash" re-show after 24 h.

Registration
------------
Registered as `dp.message.outer_middleware()` — runs only for Message updates,
AFTER the 5 dp.update outer middlewares (so `locale` is already in `data`).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message

from apps.bot.keyboards.main_menu import MAIN_MENU_BUTTONS, main_menu_keyboard
from infrastructure.cache.client import get_redis
from infrastructure.cache.keys import CacheKeys, CacheTTL
from shared.logging import get_logger

log = get_logger(__name__)


class GroupMenuInjectorMiddleware(BaseMiddleware):
    """Send a selective ReplyKeyboard to first-time group message senders."""

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        # ── Guard 1: groups only ──────────────────────────────────────────
        if event.chat.type not in ("group", "supergroup"):
            return await handler(event, data)

        # ── Guard 2: real human sender ────────────────────────────────────
        from_user = event.from_user
        if from_user is None or from_user.is_bot or from_user.id <= 0:
            return await handler(event, data)

        # ── Guard 3: skip commands (handled by /start and /menu handlers) ─
        text = event.text or ""
        if text.startswith("/"):
            return await handler(event, data)

        chat_id = event.chat.id
        user_id = from_user.id
        _bot_id = event.bot.id if event.bot else None
        key = CacheKeys.grp_menu_shown(chat_id, user_id, bot_id=_bot_id)
        ttl = CacheTTL.GRP_MENU_SHOWN
        cache = get_redis()

        try:
            already_shown = await cache.exists(key)

            if not already_shown:
                # Atomic set-if-not-exists to guard against concurrent messages
                locale: str = data.get("locale", "uz")
                kb = main_menu_keyboard(locale=locale, selective=True)
                acquired = await cache.set(key, "1", ttl=ttl, nx=True)
                if acquired:
                    await event.reply("📋 Menyu:", reply_markup=kb)
                    log.info(
                        "grp_menu_injected",
                        chat_id=chat_id,
                        user_id=user_id,
                    )
            elif text in MAIN_MENU_BUTTONS:
                # User is actively tapping menu buttons — refresh dedup TTL
                await cache.expire(key, ttl)

        except Exception:
            log.exception("grp_menu_inject_failed", chat_id=chat_id, user_id=user_id)

        # Always propagate the update to the actual handlers
        return await handler(event, data)
