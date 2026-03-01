"""
apps.bot.handlers.private.promotions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Promotions & special offers handler.

Triggered by "🎉 Chegirmalar" main-menu button.
Displays current discounts and promotional offers with three CTA buttons:
  - 🧮 Narx kalkulyator → starts pricing FSM
  - ✅ Zakaz berish     → starts order FSM
  - 📞 Operator         → starts operator contact flow
"""
from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from apps.bot.handlers.private.operator import start_operator_flow
from apps.bot.handlers.private.order import OrderFlow
from apps.bot.handlers.private.pricing import start_pricing_flow
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="private:promotions")

# VS-16 tolerant match for the "🎉 Chegirmalar" main-menu button.
_PROMO_BTN_RE: re.Pattern[str] = re.compile(
    r"\U0001F389\uFE0F?\s*Chegirmalar", re.IGNORECASE
)

_PROMO_TEXT: str = (
    "🎁 AKSIYALAR VA MAXSUS TAKLIFLAR\n\n"
    "🏷 20 m² dan oshsa — 5% CHEGIRMA\n"
    "   Katta maydon buyurtma qilsangiz, avtomatik chegirma qo'llanadi.\n\n"
    "💎 50 m² dan oshsa (faqat GULLI dizayn)\n"
    "   LED lenta BEPUL 🎁\n"
    "   Interyerga premium yoritish — qo'shimcha to'lovsiz.\n\n"
    "📏 O'lchov va maslahat — 100% bepul\n"
    "   Mutaxassis joyiga borib aniq hisoblab beradi.\n\n"
    "🛡 Faqat sertifikatlangan materiallar\n"
    "🛠 Professional montaj brigada\n"
    "⏱ 24 soat ichida qayta aloqa\n"
    "📄 15 yilgacha rasmiy kafolat\n\n"
    "⏳ Aksiyalar cheklangan muddatga amal qiladi.\n\n"
    "🔥 Xona o'lchamini hoziroq yuboring —\n"
    "narxni 1 daqiqada hisoblab beramiz!"
)


def _promo_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧮 Narx kalkulyator", callback_data="open_pricing")],
            [InlineKeyboardButton(text="✅ Zakaz berish",     callback_data="order_start")],
            [InlineKeyboardButton(text="📞 Operator",         callback_data="contact_operator")],
        ]
    )


# ─── Entry handler ────────────────────────────────────────────────────────────

@router.message(F.chat.type == "private", F.text.regexp(_PROMO_BTN_RE))
async def cmd_promotions(message: Message, **data: object) -> None:
    """Show the promotions page with CTA inline keyboard."""
    log.debug("promotions_opened", user_id=message.from_user and message.from_user.id)
    await message.answer(_PROMO_TEXT, reply_markup=_promo_keyboard())


# ─── CTA callbacks ────────────────────────────────────────────────────────────

@router.callback_query(F.message.chat.type == "private", F.data == "open_pricing")
async def cb_open_pricing(
    callback: CallbackQuery, state: FSMContext, **data: object
) -> None:
    """Start the pricing calculator flow."""
    await callback.answer()
    msg = callback.message
    if not isinstance(msg, Message):
        return
    await start_pricing_flow(msg, state)


@router.callback_query(F.message.chat.type == "private", F.data == "order_start")
async def cb_order_start(
    callback: CallbackQuery, state: FSMContext, **data: object
) -> None:
    """Start the order (Zakaz berish) flow."""
    await callback.answer()
    msg = callback.message
    if not isinstance(msg, Message):
        return
    await state.clear()
    await state.set_state(OrderFlow.waiting_for_name)
    await msg.answer(
        "📋 <b>Zakaz berish</b>\n\n"
        "Ismingizni kiriting:",
    )


@router.callback_query(F.message.chat.type == "private", F.data == "contact_operator")
async def cb_contact_operator(
    callback: CallbackQuery, state: FSMContext, **data: object
) -> None:
    """Start the operator contact-request flow."""
    await callback.answer()
    msg = callback.message
    if not isinstance(msg, Message):
        return
    await start_operator_flow(msg, state)
