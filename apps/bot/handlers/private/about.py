"""
apps.bot.handlers.private.about
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"⭐ Biz haqimizda" (About Us) section handler.

Triggered by the main-menu button "⭐ Biz haqimizda".
Displays company info with a four-button CTA inline keyboard:
  - 📂 Katalog          → open_catalog   (handled here)
  - 🧮 Narx kalkulyator → open_pricing   (handled by promotions.py)
  - 📞 Operator         → contact_operator (handled by promotions.py)
  - ✅ Zakaz berish     → order_start    (handled by promotions.py)
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from apps.bot.keyboards.catalog import catalog_list_keyboard
from apps.bot.keyboards.main_menu import BTN_ABOUT
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="private:about")

_ABOUT_TEXT: str = (
    "⭐ BIZ HAQIMIZDA\n\n"
    "VASHPOTOLOK kompaniyasi 6 yildan beri Qashqadaryoda faoliyat yuritib kelmoqda.\n\n"
    "🏗 10 000+ muvaffaqiyatli topshirilgan obyekt\n"
    "👥 Ijtimoiy tarmoqlarda 200 000+ kuzatuvchi\n"
    "🤖 Sun'iy intellekt orqali tezkor mijozlarga xizmat\n"
    "🛡 15 yilgacha rasmiy kafolat\n"
    "📏 Bepul o'lchov va aniq hisob-kitob\n"
    "👷 Tajribali montaj brigada\n"
    "💎 Sertifikatlangan va sifatli materiallar\n\n"
    "Biz zamonaviy texnologiyalar va AI yordamida\n"
    "mijozlarga 24/7 tezkor javob va aniq hisob-kitob taqdim etamiz.\n\n"
    "📍 Qashqadaryo bo'ylab xizmat ko'rsatamiz\n"
    "⏱ 24 soat ichida qayta aloqa\n\n"
    "👇 Savolingiz bormi yoki buyurtma bermoqchimisiz?"
)

_CATALOG_INTRO: str = "📂 <b>Katalog</b>\n\nBo'limni tanlang:"


def _about_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📂 Katalog",           callback_data="open_catalog")],
            [InlineKeyboardButton(text="🧮 Narx kalkulyator",  callback_data="open_pricing")],
            [InlineKeyboardButton(text="📞 Operator",          callback_data="contact_operator")],
            [InlineKeyboardButton(text="✅ Zakaz berish",      callback_data="order_start")],
        ]
    )


# ─── Entry handler ────────────────────────────────────────────────────────────

@router.message(F.chat.type.in_({"private", "group", "supergroup"}), F.text == BTN_ABOUT)
async def cmd_about(message: Message, **data: object) -> None:
    """Display the About Us page with CTA inline keyboard."""
    log.debug("about_opened", user_id=message.from_user and message.from_user.id)
    await message.answer(_ABOUT_TEXT, reply_markup=_about_keyboard())


# ─── CTA callback ─────────────────────────────────────────────────────────────
# open_pricing / order_start / contact_operator are registered in promotions.py
# and will be matched there first (promotions_router is included before about_router).

@router.callback_query(F.data == "open_catalog")
async def cb_open_catalog(callback: CallbackQuery, **data: object) -> None:
    """Open the ceiling catalog inline keyboard."""
    await callback.answer()
    msg = callback.message
    if not isinstance(msg, Message):
        return
    await msg.answer(_CATALOG_INTRO, reply_markup=catalog_list_keyboard())
