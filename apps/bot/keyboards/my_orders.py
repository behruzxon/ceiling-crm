"""Buyurtmalarim submenu reply keyboard."""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def my_orders_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Mening buyurtmalarim"),
                KeyboardButton(text="📦 Buyurtma holati"),
            ],
            [
                KeyboardButton(text="🧾 Hisob-kitob tarixi"),
                KeyboardButton(text="🛠 Kafolat ma'lumoti"),
            ],
            [KeyboardButton(text="💳 To'lov qilish")],
            [KeyboardButton(text="⬅️ Orqaga")],
        ],
        resize_keyboard=True,
    )
