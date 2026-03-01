"""
Catalog browsing handler.

Pressing "📂 Katalog" or /catalog shows an inline keyboard where every
button is a direct URL to the corresponding Telegram group — no intermediate
step, no callbacks.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from apps.bot.keyboards.catalog import catalog_list_keyboard
from apps.bot.keyboards.main_menu import BTN_CATALOG
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="private:catalog")

_CHAT_TYPES = {"private", "group", "supergroup"}
_CATALOG_INTRO = "📂 <b>Katalog</b>\n\nBo'limni tanlang:"


@router.message(F.chat.type.in_(_CHAT_TYPES), F.text == BTN_CATALOG)
@router.message(F.chat.type.in_(_CHAT_TYPES), Command("catalog"))
async def cmd_catalog(message: Message, **data: object) -> None:
    """Show the catalog section list with direct group URL buttons."""
    await message.answer(_CATALOG_INTRO, reply_markup=catalog_list_keyboard())
