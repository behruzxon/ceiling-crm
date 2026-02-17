"""
Group context middleware.
Resolves which ceiling category group the update came from.
Injects data["category"] and data["group_db"] for all handlers.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from infrastructure.cache.client import get_redis
from infrastructure.database.models.group import GroupModel
from infrastructure.database.session import get_session_factory
from shared.logging import get_logger

log = get_logger(__name__)


class GroupContextMiddleware(BaseMiddleware):
    """
    For group updates: resolves CeilingCategory from chat_id via DB/cache.
    For private updates: injects None defaults.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        chat = getattr(event, "chat", None)
        is_group = chat is not None and chat.type in ("group", "supergroup")

        if not is_group:
            data["category"] = None
            data["group_db"] = None
            data["is_group_chat"] = False
            return await handler(event, data)

        data["is_group_chat"] = True
        chat_id = chat.id

        # Try cache first
        cache = get_redis()
        cached = await cache.get_json(f"group:{chat_id}")

        if cached:
            data["category"] = cached.get("category")
            data["group_db"] = cached
            return await handler(event, data)

        # Fallback to DB
        from sqlalchemy import select

        factory = get_session_factory()
        async with factory() as session:
            stmt = select(GroupModel).where(GroupModel.id == chat_id)
            result = await session.execute(stmt)
            group = result.scalar_one_or_none()

            if group:
                group_data = {
                    "id": group.id,
                    "category": group.category,
                    "title": group.title,
                    "is_active": group.is_active,
                }
                # Cache for 10 minutes
                await cache.set_json(f"group:{chat_id}", group_data, ttl=600)
                data["category"] = group.category
                data["group_db"] = group_data
            else:
                data["category"] = None
                data["group_db"] = None

        return await handler(event, data)
