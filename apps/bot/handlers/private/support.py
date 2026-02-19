"""
AI support handler.
Routes ceiling-related questions to OpenAI with guardrails.
"""
from __future__ import annotations
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from apps.bot.keyboards.main_menu import main_menu_keyboard

router = Router(name="private:support")

HELP_TEXT = (
    "🏠 <b>Ceiling CRM Bot</b>\n\n"
    "Mavjud buyruqlar:\n"
    "/start — Botni ishga tushirish\n"
    "/catalog — Shiftlar katalogi\n"
    "/price — Narxni hisoblash\n"
    "/order — Buyurtma berish\n"
    "/help — Yordam\n"
    "/cancel — Amalni bekor qilish\n\n"
    "Savolingiz bo'lsa, shunchaki yozing — biz yordam beramiz!"
)


@router.message(Command("start"))
async def cmd_start(message: Message, **data) -> None:
    """Greet user and show main menu keyboard."""
    await message.answer(
        "Assalomu alaykum! 👋\n"
        "Shift o'rnatish bo'yicha CRM botga xush kelibsiz.\n\n"
        "Quyidagi tugmalardan birini tanlang:",
        reply_markup=main_menu_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message, **data) -> None:
    """Show help menu with available commands."""
    await message.answer(HELP_TEXT)
