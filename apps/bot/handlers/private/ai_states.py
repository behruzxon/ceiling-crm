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
    """AI mode keyboard with quick actions."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Narx"), KeyboardButton(text="📂 Katalog")],
            [KeyboardButton(text="👨‍💼 Operator"), KeyboardButton(text="🔄 Reset")],
            [KeyboardButton(text="❓ Yordam"), KeyboardButton(text="⬅️ Menyu")],
        ],
        resize_keyboard=True,
    )


# ── Quick button text constants ─────────────────────────────────────────────

BTN_AI_PRICE = "💰 Narx"
BTN_AI_CATALOG = "📂 Katalog"
BTN_AI_OPERATOR = "👨‍💼 Operator"
BTN_AI_RESET = "🔄 Reset"
BTN_AI_HELP = "❓ Yordam"

_AI_QUICK_BUTTONS: frozenset[str] = frozenset(
    {
        BTN_AI_PRICE,
        BTN_AI_CATALOG,
        BTN_AI_OPERATOR,
        BTN_AI_RESET,
        BTN_AI_HELP,
    }
)


# ── Failsafe UI ──────────────────────────────────────────────────────────────

_FAILSAFE_TEXT = (
    "⚠️ Kechirasiz, texnik nosozlik yuz berdi.\n\n" "Operatorga murojaat qilishingiz mumkin:"
)
_FAILSAFE_KB = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📞 Operator bilan bog'lanish",
                url="https://t.me/ceiling_manager",
            )
        ],
    ]
)

# ── Text constants ───────────────────────────────────────────────────────────

_NEUTRAL_REPLY = (
    "Tushunarli 🙂\n\n" "Narx hisoblaymizmi, katalog ko'ramizmi yoki bepul o'lchov kerakmi?"
)

_CATALOG_SOFT_CTA = (
    "Xohlasangiz xonangiz maydoni (m²) va tumanni aytsangiz, "
    "narxni ham aniqroq hisoblab beraman 🙂"
)

_CATALOG_INTRO = "📂 <b>Katalog</b>\n\nBo'limni tanlang:"

_PRICE_ASK_AREA_TEXT = "Xonangiz taxminan necha m²?\n" "Masalan: 20 m² yoki 5x3"

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

_UPSELL_SOFT_CTA = "Xohlasangiz ustamiz kelib bepul o'lchov qilib beradi 🙂\n\n" "Qaysi tumandasiz?"

# ── AI mode entry / status ──────────────────────────────────────────────────

_AI_MODE_STATUS = (
    "🤖 <b>AI yordam rejimi yoqildi</b>\n\n"
    "Menga xonangiz razmeri, potolok turi yoki savolingizni yozing.\n\n"
    "Masalan:\n"
    '• "20 kv qancha?"\n'
    '• "5x4 mehmonxona gulli"\n'
    '• "Katalog ko\'rsat"\n'
    '• "Operator kerak"'
)

_AI_HELP_TEXT = (
    "🤖 <b>AI yordam — imkoniyatlar</b>\n\n"
    "Men sizga quyidagilar bo'yicha yordam bera olaman:\n\n"
    "💰 <b>Narx hisoblash</b> — xona razmeri bo'yicha taxminiy narx\n"
    "🎨 <b>Dizayn maslahat</b> — potolok turi bo'yicha tavsiya\n"
    "📂 <b>Katalog</b> — dizayn variantlarini ko'rish\n"
    "👨‍💼 <b>Operator</b> — mutaxassis bilan bog'lanish\n"
    "🧠 <b>Xotira</b> — savollaringizni eslab davom ettirish\n\n"
    "Misollar:\n"
    '• "5x4 xona narx"\n'
    '• "20 kv gulli qancha"\n'
    '• "Mehmonxona uchun tavsiya"\n'
    '• "Operator kerak"\n\n'
    "⚠️ Aniq narx o'lchovdan keyin tasdiqlanadi."
)

_AI_RESET_SUCCESS = "✅ AI suhbat xotirasi tozalandi.\n" "Yangi savol yozishingiz mumkin."

_AI_PRICE_PROMPT = (
    "💰 Narx hisoblash uchun xonangiz razmerini yozing.\n\n" "Masalan: <b>5x4</b> yoki <b>20 kv</b>"
)

_AI_OPERATOR_PROMPT = (
    "👨‍💼 Operator bilan bog'lanishga yordam beraman.\n\n"
    "Telefon raqamingizni yuboring yoki savolingizni "
    "shu yerga yozing — operator ko'rib chiqadi."
)

_AI_ROOM_ADVICE_PROMPT = (
    "🏠 Xona bo'yicha maslahat uchun razmerini yozing.\n\n"
    "Masalan: <b>mehmonxona 5x4</b>\n"
    "Men mos potolok turini tavsiya qilaman."
)

_AI_RATE_LIMIT_TEXT = (
    "⏳ Kunlik AI so'rovlar limiti tugadi.\n"
    "Ertaga yana urinib ko'ring yoki operator bilan bog'laning."
)

_AI_UNAVAILABLE_TEXT = (
    "⚠️ Hozir AI javob berishda qiynalyapti.\n\n"
    "Savolingizni yozib qoldiring — operator ko'rib chiqadi."
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
