"""Main menu reply keyboard builder."""
from __future__ import annotations
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_keyboard(locale: str = "uz", is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Build main menu keyboard.

    Args:
        locale: Language code (unused for now, reserved for i18n).
        is_admin: When True, appends the admin-only "📣 Rassilka" button.
    """
    rows = [
        [KeyboardButton(text="🛒 Zakaz berish"), KeyboardButton(text="💰 Narx kalkulyator")],
        [KeyboardButton(text="📂 Katalog"), KeyboardButton(text="🏷️ Tayyor paketlar")],
        [KeyboardButton(text="📦 Buyurtmalarim"), KeyboardButton(text="☎️ Operator")],
        [KeyboardButton(text="🎁 Chegirmalar"), KeyboardButton(text="🤖 AI yordam")],
        [KeyboardButton(text="⭐ Biz haqimizda")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="📣 Rassilka")])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
        one_time_keyboard=False,
    )
