"""
apps.bot.handlers.group.start
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Handles /start and /menu commands in group and supergroup chats, plus all
``grpmenu:*`` inline-button callbacks (kept for backward compatibility with
any existing messages that still have the old inline buttons).

Menu strategy for groups
------------------------
We send a selective ReplyKeyboardMarkup (``selective=True``) via
``message.reply()``.  This makes the keyboard appear only for the specific
user, not for all group members, and the bot only needs to reply once per
user per 24 h (dedup handled by GroupMenuInjectorMiddleware + Redis).

The /start and /menu commands force-show the keyboard to the caller and
reset the 24-h Redis dedup key.

Callback namespace
------------------
``grpmenu:`` — kept so old inline-button messages remain interactive.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from apps.bot.handlers.private.about import _ABOUT_TEXT, _about_keyboard
from apps.bot.handlers.private.operator import start_operator_flow
from apps.bot.handlers.private.order import _start_order_flow
from apps.bot.handlers.private.packages import show_packages_list
from apps.bot.handlers.private.pricing import start_pricing_flow
from apps.bot.handlers.private.promotions import _PROMO_TEXT
from apps.bot.keyboards.catalog import catalog_list_keyboard
from apps.bot.keyboards.main_menu import (
    group_menu_inline_keyboard,
    main_menu_keyboard,
)
from infrastructure.cache.client import get_redis
from infrastructure.cache.keys import CacheKeys, CacheTTL
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="group:start")

_GROUP_INLINE_KB = group_menu_inline_keyboard()
_CATALOG_INTRO = "📂 <b>Katalog</b>\n\nBo'limni tanlang:"

# Popup alerts for actions that only work in private DM
_DM_ONLY_ALERTS: dict[str, str] = {
    "my_orders": "📦 Buyurtmalarni ko'rish uchun botni shaxsiy chatda oching.",
    "ai": "🤖 AI yordam faqat shaxsiy chatda ishlaydi. Botni DM da oching.",
}


# ─── /start and /menu ─────────────────────────────────────────────────────────


@router.message(Command("start"), F.chat.type.in_({"group", "supergroup"}))
async def group_start(message: Message, **data: object) -> None:
    """Show the ReplyKeyboard to the command sender and reset the dedup key."""
    log.info("start_group", chat_id=message.chat.id, chat_type=message.chat.type)
    if not message.from_user:
        return
    locale: str = data.get("locale", "uz")  # type: ignore[assignment]
    kb = main_menu_keyboard(locale=locale, selective=True)
    await message.reply("📋 Menyu:", reply_markup=kb)
    # Set Redis key so GroupMenuInjectorMiddleware won't double-inject
    cache = get_redis()
    key = CacheKeys.grp_menu_shown(message.chat.id, message.from_user.id)
    await cache.set(key, "1", ttl=CacheTTL.GRP_MENU_SHOWN)


@router.message(Command("menu"), F.chat.type.in_({"group", "supergroup"}))
async def group_menu_cmd(message: Message, **data: object) -> None:
    """Re-show the ReplyKeyboard on demand and reset the dedup key."""
    log.info("menu_group", chat_id=message.chat.id)
    if not message.from_user:
        return
    locale: str = data.get("locale", "uz")  # type: ignore[assignment]
    kb = main_menu_keyboard(locale=locale, selective=True)
    await message.reply("📋 Menyu:", reply_markup=kb)
    cache = get_redis()
    key = CacheKeys.grp_menu_shown(message.chat.id, message.from_user.id)
    await cache.set(key, "1", ttl=CacheTTL.GRP_MENU_SHOWN)


# ─── grpmenu:* callback dispatcher (backward compat) ──────────────────────────


@router.callback_query(F.data.startswith("grpmenu:"))
async def handle_group_menu(cb: CallbackQuery, state: FSMContext, **data: object) -> None:
    """Dispatch all group inline-menu button taps (from old messages).

    Always calls cb.answer() first so Telegram clears the loading spinner,
    then routes to the appropriate flow.
    """
    action = (cb.data or "").removeprefix("grpmenu:")
    log.info(
        "grpmenu_callback",
        action=action,
        chat_id=cb.message.chat.id if cb.message else None,
        user_id=cb.from_user.id if cb.from_user else None,
    )

    # DM-only actions: show an alert popup, no further processing
    if action in _DM_ONLY_ALERTS:
        await cb.answer(_DM_ONLY_ALERTS[action], show_alert=True)
        return

    await cb.answer()  # clear the Telegram spinner

    if not cb.message:
        return
    msg = cb.message

    if action == "order":
        if cb.from_user:
            await _start_order_flow(
                message=msg,
                state=state,
                user_id=cb.from_user.id,
                first_name=cb.from_user.first_name or "—",
            )

    elif action == "price":
        await start_pricing_flow(msg, state)

    elif action == "catalog":
        await msg.answer(_CATALOG_INTRO, reply_markup=catalog_list_keyboard())

    elif action == "packages":
        await show_packages_list(msg)

    elif action == "operator":
        await start_operator_flow(msg, state)

    elif action == "promos":
        await msg.answer(_PROMO_TEXT, reply_markup=_GROUP_INLINE_KB)

    elif action == "about":
        await msg.answer(_ABOUT_TEXT, reply_markup=_about_keyboard())

    else:
        log.warning("grpmenu_unknown_action", action=action)
