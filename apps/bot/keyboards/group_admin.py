"""Inline keyboard for the group /admin settings panel."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.domain.group_settings import GroupSettings

# Callback data prefix — all toggles share this prefix.
# Format: "gs:toggle:{field}"
_PREFIX = "gs:toggle:"


def _btn(label: str, field: str, value: bool) -> InlineKeyboardButton:
    state = "✅" if value else "❌"
    return InlineKeyboardButton(
        text=f"{state} {label}",
        callback_data=f"{_PREFIX}{field}",
    )


def group_admin_keyboard(settings: GroupSettings) -> InlineKeyboardMarkup:
    """Build the settings panel keyboard reflecting current toggle states."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_btn("Xush kelibsiz xabari", "welcome_enabled", settings.welcome_enabled)],
            [_btn("Captcha", "captcha_enabled", settings.captcha_enabled)],
            [_btn("Havola bloklash", "link_block_enabled", settings.link_block_enabled)],
            [_btn("Flood himoya", "flood_enabled", settings.flood_enabled)],
            [_btn("Loglar", "logs_enabled", settings.logs_enabled)],
            [InlineKeyboardButton(text="❌ Yopish", callback_data="gs:close")],
        ]
    )
