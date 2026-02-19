"""Inline keyboards used in the catalog browsing flow."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from shared.constants.catalog import CATALOG, CatalogSection


def catalog_list_keyboard() -> InlineKeyboardMarkup:
    """One button per section; callback_data='cat:<key>'."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=s.title, callback_data=f"cat:{s.key}")]
            for s in CATALOG
        ]
    )


def catalog_section_keyboard(section: CatalogSection) -> InlineKeyboardMarkup:
    """Action buttons shown under a section detail view."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📲 Guruhga kirish",     url=section.group_url)],
            [InlineKeyboardButton(text="💰 Narxni hisoblash",   callback_data="cat:price")],
            [InlineKeyboardButton(text="⬅️ Ortga",             callback_data="cat:back")],
        ]
    )
