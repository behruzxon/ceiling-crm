"""Main menu reply keyboard builder."""
from __future__ import annotations
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_keyboard(locale: str = "uz") -> ReplyKeyboardMarkup:
    """Build main menu keyboard. TODO: add translations."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📸 Katalog"), KeyboardButton(text="💰 Narx")],
            [KeyboardButton(text="📋 Buyurtma"), KeyboardButton(text="📞 Operator")],
        ],
        resize_keyboard=True,
    )
