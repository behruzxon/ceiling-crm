"""
Catalog browsing handler.

Callback routing
----------------
  cat:<key>   — section detail view (10 sections defined in shared/constants/catalog.py)
  cat:back    — return to section list (edits the current message in-place)
  cat:price   — hand off to pricing flow (reuses start_pricing_flow from pricing.py)

All handlers are private-chat-only.
"""
from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from apps.bot.handlers.private.pricing import start_pricing_flow
from apps.bot.keyboards.catalog import catalog_list_keyboard, catalog_section_keyboard
from shared.constants.catalog import CATALOG_BY_KEY
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="private:catalog")

# Matches both "📂 Katalog" (new) and "📸 Katalog" (old, for backward compat
# with keyboards already rendered in active chats before the emoji update).
_CATALOG_BTN_RE: re.Pattern[str] = re.compile(
    r"[📂📸]\uFE0F?\s*Katalog", re.IGNORECASE
)

_CATALOG_INTRO = "📂 <b>Katalog</b>\n\nBo'limni tanlang:"


# ─── Entry points ─────────────────────────────────────────────────────────────

@router.message(F.chat.type == "private", F.text.regexp(_CATALOG_BTN_RE))
@router.message(F.chat.type == "private", Command("catalog"))
async def cmd_catalog(message: Message, **data: object) -> None:
    """Show the catalog section list."""
    await message.answer(_CATALOG_INTRO, reply_markup=catalog_list_keyboard())


# ─── Callback router (single handler, dispatch by action) ─────────────────────

@router.callback_query(
    F.message.chat.type == "private",
    F.data.startswith("cat:"),
)
async def handle_catalog_callback(
    callback: CallbackQuery, state: FSMContext, **data: object
) -> None:
    """Route cat:* callbacks from the catalog inline keyboard."""
    action = (callback.data or "").split(":", 1)[1]

    # ── "⬅️ Ortga" — edit current message back to section list ───────────
    if action == "back":
        await callback.answer()
        if callback.message:
            await callback.message.edit_text(
                _CATALOG_INTRO, reply_markup=catalog_list_keyboard()
            )
        return

    # ── "💰 Narxni hisoblash" — start pricing flow ────────────────────────
    if action == "price":
        await callback.answer()
        if callback.message:
            await callback.message.edit_reply_markup(reply_markup=None)
            await start_pricing_flow(callback.message, state)
        return

    # ── Section key — show detail view ────────────────────────────────────
    section = CATALOG_BY_KEY.get(action)
    if section is None:
        await callback.answer("Noma'lum bo'lim.", show_alert=True)
        return

    await callback.answer()
    text = f"📂 <b>{section.title}</b>"
    if section.short_description:
        text += f"\n\n{section.short_description}"

    if callback.message:
        await callback.message.edit_text(
            text, reply_markup=catalog_section_keyboard(section)
        )

    log.debug("catalog_section_viewed", section=action)
