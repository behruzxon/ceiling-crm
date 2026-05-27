"""Inline keyboard builder for lead cards sent to admin group."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def lead_card_keyboard(lead_id: int) -> InlineKeyboardMarkup:
    """Keyboard for admin lead card: view, assign, advance, lose."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👁 Ko'rish", callback_data=f"lead:view:{lead_id}"),
                InlineKeyboardButton(text="👤 Tayinlash", callback_data=f"lead:assign:{lead_id}"),
            ],
            [
                InlineKeyboardButton(
                    text="✅ Navbatga", callback_data=f"pipeline:advance:{lead_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Yo'qotildi", callback_data=f"pipeline:lost:{lead_id}"
                ),
            ],
        ]
    )
