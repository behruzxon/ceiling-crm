"""
apps.bot.handlers.group.start
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Handles /start and /menu commands in group and supergroup chats.

Sends the persistent reply keyboard so the main menu is always visible
in the group, without requiring users to open the bot in DM.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from apps.bot.keyboards.main_menu import main_menu_keyboard
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="group:start")

_MENU_KB = main_menu_keyboard()


@router.message(Command("start"), F.chat.type.in_({"group", "supergroup"}))
async def group_start(message: Message, **data: object) -> None:
    """Respond to /start in a group with the persistent reply keyboard."""
    log.info("start_group", chat_id=message.chat.id, chat_type=message.chat.type)
    await message.answer("Menyu:", reply_markup=_MENU_KB)


@router.message(Command("menu"), F.chat.type.in_({"group", "supergroup"}))
async def group_menu(message: Message, **data: object) -> None:
    """Show the main menu keyboard in a group chat."""
    log.info("menu_group", chat_id=message.chat.id)
    await message.answer("Menyu:", reply_markup=_MENU_KB)
