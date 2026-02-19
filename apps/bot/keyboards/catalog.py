"""Inline keyboards used in the catalog browsing flow."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from shared.constants.catalog import CATALOG


def catalog_list_keyboard() -> InlineKeyboardMarkup:
    """One URL button per section — tapping opens the group directly."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=s.title, url=s.group_url)]
            for s in CATALOG
        ]
    )
