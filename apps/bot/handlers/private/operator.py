"""
apps.bot.handlers.private.operator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Operator contact-request flow.

FSM flow
--------
  "📞 Operator"  (from any state / no state)
    └─► [show phone numbers]
          └─► waiting_for_confirmation   ← "Ha" / "Yo'q" keyboard
                ├─ "Yo'q" → clear state → main menu
                └─ "Ha"   → waiting_for_contact
                              ├─ F.contact → extract phone → notify admin → confirm
                              └─ F.text    → re-prompt (keep state)

Admin notification
------------------
  Uses settings.bot.admin_group_id (BOT_ADMIN_GROUP_ID env var).
  Non-fatal: any send failure is logged and swallowed so the user
  confirmation is never blocked.

Shared helper
-------------
  start_operator_flow(message, state) is importable by other handlers
  (e.g. pricing.py) that need to hand off to this flow without
  duplicating the entry logic.
"""

from __future__ import annotations

import asyncio

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from apps.bot.keyboards.main_menu import BTN_OPERATOR, MAIN_MENU_BUTTONS, main_menu_keyboard
from core.services.journey_event_service import emit_journey_event
from shared.config import get_settings
from shared.constants.enums import JourneyEventType
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="private:operator")

_OPERATOR_PHONES = "+998 90 886 66 66\n+998 99 219 12 19"


# ─── FSM states ───────────────────────────────────────────────────────────────


class OperatorFlow(StatesGroup):
    waiting_for_confirmation = State()  # "Ha" / "Yo'q"
    waiting_for_contact = State()  # request_contact button


# ─── Keyboards ────────────────────────────────────────────────────────────────


def _confirm_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Ha"), KeyboardButton(text="Yo'q")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _contact_keyboard(is_private: bool = True) -> ReplyKeyboardMarkup:
    """Contact-request keyboard.

    ``request_contact=True`` is only valid in private chats.  In groups we
    fall back to a plain text button — a group handler then shows a DM deep link.
    """
    btn = (
        KeyboardButton(text="📲 Nomerni yuborish", request_contact=True)
        if is_private
        else KeyboardButton(text="📲 Nomerni yuborish")
    )
    return ReplyKeyboardMarkup(
        keyboard=[[btn]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# ─── Shared entry helper ──────────────────────────────────────────────────────


async def start_operator_flow(message: Message, state: FSMContext) -> None:
    """
    Show operator phone numbers and ask for callback confirmation.

    Importable by other handlers (e.g. pricing.py) so they can hand off
    to this flow without repeating the entry logic.  Clears any existing
    FSM state before setting the new one.
    """
    await state.clear()
    await state.set_state(OperatorFlow.waiting_for_confirmation)
    await message.answer(
        "📞 <b>Operator raqamlari:</b>\n\n"
        f"{_OPERATOR_PHONES}\n\n"
        "Operator sizga o'zi telefon qiladi. Nomeringizni qoldirasizmi?",
        reply_markup=_confirm_keyboard(),
    )


# ─── Entry point ──────────────────────────────────────────────────────────────


@router.message(F.chat.type.in_({"private", "group", "supergroup"}), F.text == BTN_OPERATOR)
async def handle_operator_entry(message: Message, state: FSMContext, **data: object) -> None:
    """Catch the main-menu «📞 Operator» button tap from any FSM state."""
    await start_operator_flow(message, state)
    asyncio.create_task(
        emit_journey_event(
            user_id=message.from_user.id if message.from_user else 0,
            event_type=JourneyEventType.OPERATOR_REQUESTED,
            source_handler="operator:handle_operator_entry",
        )
    )


# ─── Step 1 : confirmation ────────────────────────────────────────────────────


@router.message(StateFilter(OperatorFlow.waiting_for_confirmation), F.text == "Ha")
async def handle_confirm_yes(message: Message, state: FSMContext, **data: object) -> None:
    """User agreed to leave their number — request Telegram contact."""
    await state.set_state(OperatorFlow.waiting_for_contact)
    await message.answer(
        "📲 Quyidagi tugmani bosib raqamingizni yuboring.\n\n" "<i>Namuna: +998 90 123 45 67</i>",
        reply_markup=_contact_keyboard(is_private=(message.chat.type == "private")),
    )


@router.message(StateFilter(OperatorFlow.waiting_for_confirmation), F.text == "Yo'q")
async def handle_confirm_no(message: Message, state: FSMContext, **data: object) -> None:
    """User declined — clear state and return to main menu."""
    await state.clear()
    await message.answer(
        "Tushunarli. Kerak bo'lsa murojaat qilishingiz mumkin.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(
    StateFilter(OperatorFlow.waiting_for_confirmation),
    F.text,
    ~F.text.in_(MAIN_MENU_BUTTONS),  # let menu buttons fall through to their own handlers
)
async def handle_confirmation_fallback(message: Message, state: FSMContext, **data: object) -> None:
    """Reprompt on unexpected input during the confirmation step."""
    await message.answer(
        "Iltimos, «Ha» yoki «Yo'q» tugmasini bosing.",
        reply_markup=_confirm_keyboard(),
    )


# ─── Step 2 : contact received ────────────────────────────────────────────────


@router.message(StateFilter(OperatorFlow.waiting_for_contact), F.contact)
async def handle_contact(message: Message, state: FSMContext, **data: object) -> None:
    """User shared their Telegram contact — notify admin and confirm."""
    contact = message.contact
    if contact is None:
        await message.answer(
            "Iltimos, pastdagi 📲 tugma orqali nomerni yuboring.",
            reply_markup=_contact_keyboard(),
        )
        return

    phone = contact.phone_number
    user = message.from_user
    full_name = user.full_name if user else "Noma'lum"
    user_id = user.id if user else 0
    username = f"@{user.username}" if user and user.username else "—"

    await state.clear()

    # Admin notification first — non-fatal.
    if message.bot is not None:
        await _notify_admin(
            message.bot,
            phone=phone,
            full_name=full_name,
            user_id=user_id,
            username=username,
        )

    # User-facing confirmation.
    await message.answer(
        "Rahmat! ✅ Nomeringiz qabul qilindi. Operator tez orada bog'lanadi.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer(
        "Asosiy menyu:",
        reply_markup=main_menu_keyboard(),
    )


@router.message(
    StateFilter(OperatorFlow.waiting_for_contact),
    F.chat.type.in_({"group", "supergroup"}),
    F.text == "📲 Nomerni yuborish",
)
async def handle_operator_contact_group_btn(
    message: Message, state: FSMContext, **data: object
) -> None:
    """User tapped the contact button in a group — guide them to DM."""
    settings = get_settings()
    url = f"https://t.me/{settings.bot.username}?start=share_phone"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📩 Botni DM da ochish", url=url)]]
    )
    await message.reply(
        "📩 Raqam yuborish faqat shaxsiy chatda ishlaydi. Botni oching:",
        reply_markup=kb,
    )


@router.message(
    StateFilter(OperatorFlow.waiting_for_contact),
    F.text,
    ~F.text.in_(MAIN_MENU_BUTTONS),  # let menu buttons fall through to their own handlers
)
async def handle_contact_text_fallback(message: Message, state: FSMContext, **data: object) -> None:
    """Reprompt when user types something other than the contact button or a menu button."""
    await message.answer(
        "Raqam yuborish uchun faqat 📲 Nomerni yuborish tugmasini bosing.",
        reply_markup=_contact_keyboard(is_private=(message.chat.type == "private")),
    )


# ─── Admin notification helper ────────────────────────────────────────────────


async def _notify_admin(
    bot: Bot,
    *,
    phone: str,
    full_name: str,
    user_id: int,
    username: str,
) -> None:
    """
    Send an operator-callback request to the admin user's DM.
    Uses BOT_ADMIN_USER_ID from settings.
    Non-fatal: logs an error and returns without raising.
    """
    settings = get_settings()
    admin_user_id = settings.bot.admin_user_id
    if admin_user_id is None:
        log.error(
            "operator_admin_user_id_missing",
            detail="Set BOT_ADMIN_USER_ID in .env to receive operator notifications",
        )
        return
    try:
        text = (
            "📞 <b>Operator so'rovi!</b>\n\n"
            f"👤 Ism:      <b>{full_name}</b>\n"
            f"📱 Telefon:  <b>{phone}</b>\n"
            f"🆔 User ID:  <code>{user_id}</code>\n"
            f"🔗 Username: {username}"
        )
        await bot.send_message(chat_id=admin_user_id, text=text)
        log.info("operator_admin_notified", user_id=user_id, admin_user_id=admin_user_id)
    except Exception:
        log.exception("operator_admin_notify_failed", user_id=user_id)
