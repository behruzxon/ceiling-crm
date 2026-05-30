"""
apps.bot.handlers.callbacks.catalog_confirm_callbacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Callbacks for the catalog fuzzy/Cyrillic confirmation UX.

Buttons originate from ``apps.bot.handlers.private.ai_support``
``_build_catalog_link_kb`` when the resolver returns
``needs_confirmation=True``.

Callback routing
----------------
  catalog_confirm:<key>  → reply with the matched section's URL
  catalog_all            → reply with the generic full-catalog URL

No DB writes, no AI calls, no Telegram broadcasts.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from shared.constants.catalog import CATALOG_BY_KEY
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="callbacks:catalog_confirm")

_GENERIC_URL = "https://t.me/vashpotolokuz"
_GENERIC_TITLE = "📂 To'liq katalogimiz"


def _link_kb(text: str, url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, url=url)]])


@router.callback_query(F.data.startswith("catalog_confirm:"))
async def cb_catalog_confirm(callback: CallbackQuery) -> None:
    """Send the requested design catalog after the user confirms."""
    payload = (callback.data or "").split(":", 1)
    key = payload[1] if len(payload) == 2 else ""
    section = CATALOG_BY_KEY.get(key)

    await callback.answer()
    if callback.message is None:
        return

    if section is None or not section.group_url:
        await callback.message.answer(
            "Bu bo'lim uchun alohida link hali sozlanmagan. Mana to'liq katalogimiz 👇",
            reply_markup=_link_kb(_GENERIC_TITLE, _GENERIC_URL),
        )
        log.info("catalog_confirm_missing", key=key)
        return

    await callback.message.answer(
        f"Albatta, mana {section.title} katalogimiz 👇",
        reply_markup=_link_kb(f"📂 {section.title} katalogi", section.group_url),
    )
    log.info("catalog_confirm_sent", key=key)


@router.callback_query(F.data == "catalog_all")
async def cb_catalog_all(callback: CallbackQuery) -> None:
    """Fallback button: send the generic full catalog link."""
    await callback.answer()
    if callback.message is None:
        return
    await callback.message.answer(
        "Mana to'liq katalogimiz 👇",
        reply_markup=_link_kb(_GENERIC_TITLE, _GENERIC_URL),
    )
    log.info("catalog_confirm_all_sent")


__all__ = ["router"]
