"""
apps.bot.handlers.private.ai_states
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
FSM states, keyboards, and UI text constants for the AI support module.

No dependencies on other ``ai_*`` sibling modules — safe to import anywhere.
"""
from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


# ── FSM states ───────────────────────────────────────────────────────────────

class AiSupportStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_ai_question = State()
    waiting_for_district = State()
    waiting_for_phone = State()
    # Photo funnel: photo -> room -> design + catalog -> area -> district -> phone
    waiting_photo = State()
    waiting_room = State()
    waiting_area_photo = State()


# ── Navigation constants ─────────────────────────────────────────────────────

_EXIT_TEXTS: frozenset[str] = frozenset({"⬅️ Menyu", "🔙 Menyu"})

_CANCEL_PHONE = "❌ Bekor qilish"


# ── Keyboards ────────────────────────────────────────────────────────────────

def _phone_request_keyboard() -> ReplyKeyboardMarkup:
    """Contact-share keyboard shown only during the phone collection step."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Telefonni yuborish", request_contact=True)],
            [KeyboardButton(text=_CANCEL_PHONE)],
        ],
        resize_keyboard=True,
    )


def _ai_keyboard() -> ReplyKeyboardMarkup:
    """Persistent exit button shown throughout the AI chat session."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⬅️ Menyu")]],
        resize_keyboard=True,
    )


# ── Failsafe UI ──────────────────────────────────────────────────────────────

_FAILSAFE_TEXT = (
    "⚠️ Kechirasiz, texnik nosozlik yuz berdi.\n\n"
    "Operatorga murojaat qilishingiz mumkin:"
)
_FAILSAFE_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(
            text="📞 Operator bilan bog'lanish",
            url="https://t.me/ceiling_manager",
        )],
    ]
)

# ── Text constants ───────────────────────────────────────────────────────────

_NEUTRAL_REPLY = (
    "Tushunarli 🙂\n\n"
    "Narx hisoblaymizmi, katalog ko'ramizmi yoki bepul o'lchov kerakmi?"
)

_CATALOG_SOFT_CTA = (
    "Xohlasangiz xonangiz maydoni (m²) va tumanni aytsangiz, "
    "narxni ham aniqroq hisoblab beraman 🙂"
)

_CATALOG_INTRO = "📂 <b>Katalog</b>\n\nBo'limni tanlang:"

_PRICE_ASK_AREA_TEXT = (
    "Xonangiz taxminan necha m²?\n"
    "Masalan: 20 m² yoki 5x3"
)

_PRICE_ASK_DESIGN_TEXT = (
    "Qaysi tur kerak?\n\n"
    "• Adnatonniy\n"
    "• Hi Tech\n"
    "• Mramor\n"
    "• Naqsh\n"
    "• Osmon\n"
    "• Qora UF\n"
    "• Gulli"
)

_UPSELL_SOFT_CTA = (
    "Xohlasangiz ustamiz kelib bepul o'lchov qilib beradi 🙂\n\n"
    "Qaysi tumandasiz?"
)

# ── AI follow-up reminder messages ───────────────────────────────────────────

_AI_FOLLOWUP_MSG_1 = (
    "Yordam kerakmi? 🙂\n\n"
    "Agar xohlasangiz:\n"
    "📏 Xona maydonini yozing\n"
    "yoki\n"
    "📍 Tumaningizni yozing\n\n"
    "Men sizga aniq narxni hisoblab beraman."
)

_AI_FOLLOWUP_MSG_2 = (
    "Agar xohlasangiz bepul o'lchov xizmatimiz ham bor 🙂\n\n"
    "Ustamiz kelib aniq narxni aytib beradi.\n"
    "Zakaz qoldirish uchun telefon raqamingizni yozishingiz mumkin."
)
