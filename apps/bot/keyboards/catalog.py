"""Keyboards used in the catalog browsing flow."""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from shared.constants.catalog import CATALOG

# Exported so handlers can import the constant without redefining it.
BTN_CATALOG_BACK = "⬅️ Orqaga"


def catalog_list_keyboard() -> InlineKeyboardMarkup:
    """One URL button per section — tapping opens the group directly."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=s.title, url=s.group_url)] for s in CATALOG]
    )


def catalog_design_keyboard() -> ReplyKeyboardMarkup:
    """Reply keyboard with one button per design + a back button."""
    rows: list[list[KeyboardButton]] = [[KeyboardButton(text=s.title)] for s in CATALOG]
    rows.append([KeyboardButton(text=BTN_CATALOG_BACK)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=False)
