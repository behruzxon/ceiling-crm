"""
Group message handler.
Handles text messages sent inside category groups.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import Message

from apps.bot.keyboards.main_menu import group_menu_kb_full
from infrastructure.cache.client import get_redis
from infrastructure.cache.keys import CacheKeys, CacheTTL
from shared.logging import get_logger

log = get_logger(__name__)

router = Router(name="group:messages")


@router.message(F.chat.type.in_({"group", "supergroup"}))
async def on_group_message(message: Message, category: str | None, **data) -> None:
    """Send an inline URL menu the first time a human user writes in this group."""
    from_user = message.from_user
    if from_user is None or from_user.is_bot or from_user.id <= 0:
        return

    # Skip commands — /start and /menu handlers take care of those
    text = message.text or ""
    if text.startswith("/"):
        return

    chat_id = message.chat.id
    user_id = from_user.id
    key = CacheKeys.grp_inline_menu_shown(chat_id, user_id)

    try:
        cache = get_redis()
        acquired = await cache.set(key, "1", ttl=CacheTTL.GRP_INLINE_MENU_SHOWN, nx=True)
        if acquired:
            await message.reply("📋 Menyu:", reply_markup=group_menu_kb_full())
            log.info("grp_inline_menu_injected", chat_id=chat_id, user_id=user_id)
    except Exception:
        log.exception("grp_inline_menu_inject_failed", chat_id=chat_id, user_id=user_id)
