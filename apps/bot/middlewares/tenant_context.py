"""
apps.bot.middlewares.tenant_context
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Outer middleware that resolves the tenant from the bot that received
the update and injects ``tenant_id`` + ``tenant_config`` into handler data.

Only active when ``runtime_mode == "multi"``.  In single-bot mode this
middleware is not registered at all.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Update

from core.services.bot_registry import get_bot_registry
from shared.logging import get_logger

log = get_logger(__name__)


class TenantContextMiddleware(BaseMiddleware):
    """
    Resolves tenant from ``event.bot.id`` via BotRegistry.

    Injects into handler data:
    - ``tenant_id: int``           — authoritative tenant identifier
    - ``tenant_config: TenantBotConfig`` — tenant's bot configuration snapshot
    """

    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ) -> Any:
        bot = data.get("bot") or getattr(event, "bot", None)
        if bot is None:
            return await handler(event, data)

        registry = get_bot_registry()
        tenant_id = registry.get_tenant_id(bot.id)

        if tenant_id is not None:
            data["tenant_id"] = tenant_id
            data["tenant_config"] = registry.get_config_by_bot_id(bot.id)

        return await handler(event, data)
