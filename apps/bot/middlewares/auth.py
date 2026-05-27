"""
Auth middleware.
Injects db_user and role into handler data for every update.
Creates user record if first interaction.
"""
from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from core.domain.user import User
from infrastructure.cache.client import get_redis
from infrastructure.cache.keys import CacheKeys
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_user_repo
from shared.logging import bind_request_context, get_logger

log = get_logger(__name__)


class AuthMiddleware(BaseMiddleware):
    """
    Injects authenticated user into handler data dict.

    For every incoming update:
    1. Extracts telegram user from event
    2. Opens a DB session
    3. Upserts user via repository (creates on first contact)
    4. Injects db_user, user_role, and db_session into data
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")

        # Bind per-request tracing context (request_id + user_id)
        uid = tg_user.id if tg_user and not tg_user.is_bot else None
        bind_request_context(user_id=uid)

        # Skip upsert for missing users, bots, or any non-positive ID.
        # Negative IDs belong to Telegram groups/channels/service entities
        # (e.g. anonymous admin posts use GroupAnonymousBot id=1087968824 which
        # is positive but is_bot=True; supergroup/channel linked-chat events can
        # surface negative IDs).  Only real human private users have id > 0 and
        # is_bot == False — those are the only records we want in `users`.
        if tg_user is None or tg_user.is_bot or tg_user.id <= 0:
            data["db_user"] = None
            data["user_role"] = None
            return await handler(event, data)

        factory = get_session_factory()
        async with factory() as session:
            try:
                user_repo = get_user_repo(session)

                domain_user = User(
                    id=tg_user.id,
                    username=tg_user.username,
                    first_name=tg_user.first_name or "Unknown",
                    last_name=tg_user.last_name,
                    language_code=tg_user.language_code or "uz",
                )
                db_user = await user_repo.upsert(domain_user)
                await session.commit()

                data["db_user"] = db_user
                data["user_role"] = db_user.role
                data["db_session"] = session

                # Track last private-chat activity for CTA inactivity feature.
                # Only record for real human users in private chats; non-fatal.
                if isinstance(event, (Message, CallbackQuery)):
                    _chat = (
                        event.chat
                        if isinstance(event, Message)
                        else (event.message.chat if event.message else None)
                    )
                    if _chat and _chat.type == "private":
                        try:
                            await get_redis().zadd(
                                CacheKeys.cta_user_activity(),
                                {str(tg_user.id): float(int(time.time()))},
                            )
                        except Exception:
                            pass  # activity tracking must never break auth

                return await handler(event, data)
            except Exception:
                await session.rollback()
                raise
