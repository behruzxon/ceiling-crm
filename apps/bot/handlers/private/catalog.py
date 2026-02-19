"""
Catalog browsing handler.

Pressing "📂 Katalog" or /catalog shows an inline keyboard where every
button is a direct URL to the corresponding Telegram group — no intermediate
step, no callbacks.

All handlers are private-chat-only.
"""
from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from apps.bot.keyboards.catalog import catalog_list_keyboard
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="private:catalog")

# Matches both "📂 Katalog" (current) and "📸 Katalog" (legacy keyboards).
_CATALOG_BTN_RE: re.Pattern[str] = re.compile(
    r"[📂📸]\uFE0F?\s*Katalog", re.IGNORECASE
)

_CATALOG_INTRO = "📂 <b>Katalog</b>\n\nBo'limni tanlang:"


@router.message(F.chat.type == "private", F.text.regexp(_CATALOG_BTN_RE))
@router.message(F.chat.type == "private", Command("catalog"))
async def cmd_catalog(message: Message, **data: object) -> None:
    """Show the catalog section list with direct group URL buttons."""
    await message.answer(_CATALOG_INTRO, reply_markup=catalog_list_keyboard())
