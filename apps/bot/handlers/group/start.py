"""
apps.bot.handlers.group.start
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Handles /start in group and supergroup chats.

In groups, ReplyKeyboardMarkup is unreliable (Telegram clients may hide it).
This handler responds with an InlineKeyboardMarkup whose URL buttons open
the bot in DM, so every flow (order, pricing, catalog, packages) works
correctly regardless of group keyboard restrictions.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="group:start")

_GROUP_INLINE_KB = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="🧾 Zakaz berish",     url="https://t.me/potolok_x_bot?start=order"),
        InlineKeyboardButton(text="💰 Narx hisoblash",   url="https://t.me/potolok_x_bot?start=price"),
    ],
    [
        InlineKeyboardButton(text="📂 Katalog",          url="https://t.me/potolok_x_bot?start=catalog"),
        InlineKeyboardButton(text="🏷 Tayyor paketlar",  url="https://t.me/potolok_x_bot?start=packages"),
    ],
])


@router.message(Command("start"), F.chat.type.in_({"group", "supergroup"}))
async def group_start(message: Message, **data: object) -> None:
    """Respond to /start in a group with an inline keyboard pointing to the bot DM."""
    log.info("start_group", chat_id=message.chat.id, chat_type=message.chat.type)
    await message.answer("🔘 Bot bo'limlari:", reply_markup=_GROUP_INLINE_KB)
