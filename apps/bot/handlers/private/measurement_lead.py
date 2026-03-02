"""
apps.bot.handlers.private.measurement_lead
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Deterministic FSM for capturing a "bepul o'lchov" (free measurement) lead.

FSM flow
--------
  start_measurement_flow()  ← callable entry point (from ai_support.py)
    └─► waiting_for_name
          └─► waiting_for_phone
                ├─ F.contact (private)    → normalize → waiting_for_location
                ├─ "📲 Nomerni yuborish" (group) → show DM deep link (stay)
                └─ F.text with valid phone → normalize → waiting_for_location
                      └─► waiting_for_location
                            └─► waiting_for_time
                                  └─ time selected → create lead + notify admin → done

Cancel path
-----------
  BTN_CANCEL or /cancel at any state → clear state → main menu
"""
from __future__ import annotations

import asyncio

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from apps.bot.keyboards.main_menu import MAIN_MENU_BUTTONS, main_menu_keyboard
from apps.bot.states.measurement_lead import MeasurementLeadStates
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_lead_notification_service, get_lead_service
from shared.constants.enums import CeilingCategory, LeadSource
from shared.config import get_settings
from shared.logging import get_logger
from shared.utils.phone import is_valid_uz_phone, normalize_phone

log = get_logger(__name__)
router = Router(name="private:measurement_lead")

_BTN_CANCEL = "❌ Bekor qilish"
_BTN_SKIP_TIME = "O'tkazib yuborish"
_TIME_CHOICES = ["Bugun", "Ertaga", "Hafta oxiri", _BTN_SKIP_TIME]


# ─── Keyboards ────────────────────────────────────────────────────────────────

def _ml_phone_keyboard(is_private: bool = True) -> ReplyKeyboardMarkup:
    """Phone request keyboard.

    In private chats, ``request_contact=True`` prompts Telegram's native
    contact picker.  In groups we fall back to a plain text button and then
    guide the user to DM.
    """
    btn = (
        KeyboardButton(text="📲 Nomerni yuborish", request_contact=True)
        if is_private
        else KeyboardButton(text="📲 Nomerni yuborish")
    )
    return ReplyKeyboardMarkup(
        keyboard=[[btn], [KeyboardButton(text=_BTN_CANCEL)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=_BTN_CANCEL)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _time_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Bugun"), KeyboardButton(text="Ertaga")],
            [KeyboardButton(text="Hafta oxiri"), KeyboardButton(text=_BTN_SKIP_TIME)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# ─── Shared entry helper ──────────────────────────────────────────────────────

async def start_measurement_flow(message: Message, state: FSMContext) -> None:
    """
    Entry point callable from other handlers (e.g. ai_support.py).
    Clears any existing FSM state, then starts the measurement lead FSM.
    """
    await state.clear()
    await state.set_state(MeasurementLeadStates.waiting_for_name)
    await message.answer(
        "📐 <b>Bepul o'lchov</b>\n\n"
        "Ismingizni kiriting:",
        reply_markup=_cancel_keyboard(),
    )


# ─── Step 1 : name ────────────────────────────────────────────────────────────

@router.message(
    StateFilter(MeasurementLeadStates.waiting_for_name),
    F.text,
    ~F.text.in_(MAIN_MENU_BUTTONS),
    ~F.text.startswith("/"),
)
async def handle_ml_name(message: Message, state: FSMContext, **data: object) -> None:
    text = (message.text or "").strip()

    if text == _BTN_CANCEL:
        await _cancel_flow(message, state)
        return

    if len(text) < 2 or len(text) > 128:
        await message.answer(
            "Ism 2 dan 128 gacha belgidan iborat bo'lishi kerak. Qaytadan kiriting:",
            reply_markup=_cancel_keyboard(),
        )
        return

    await state.update_data(name=text)
    await state.set_state(MeasurementLeadStates.waiting_for_phone)
    is_private = message.chat.type == "private"
    await message.answer(
        f"👋 {text}!\n\n"
        "📱 Telefon raqamingizni yuboring yoki kiriting:\n"
        "<i>Namuna: +998 90 123 45 67</i>",
        reply_markup=_ml_phone_keyboard(is_private=is_private),
    )


# ─── Step 2 : phone ───────────────────────────────────────────────────────────

@router.message(
    StateFilter(MeasurementLeadStates.waiting_for_phone),
    F.contact,
)
async def handle_ml_contact(message: Message, state: FSMContext, **data: object) -> None:
    """User shared Telegram contact (private chat only)."""
    contact = message.contact
    if contact is None:
        await message.answer(
            "Iltimos, 📲 tugmani bosib raqamingizni yuboring.",
            reply_markup=_ml_phone_keyboard(is_private=True),
        )
        return

    raw = contact.phone_number or ""
    phone = normalize_phone(raw)
    if not phone or not is_valid_uz_phone(phone):
        await message.answer(
            "Raqam noto'g'ri. Iltimos, O'zbekiston raqamini yuboring (+998...):",
            reply_markup=_ml_phone_keyboard(is_private=True),
        )
        return

    await state.update_data(phone=phone)
    await state.set_state(MeasurementLeadStates.waiting_for_location)
    await message.answer(
        "✅ Raqam qabul qilindi.\n\n"
        "📍 Manzilingizni yozing (tuman, ko'cha yoki orientir):",
        reply_markup=_cancel_keyboard(),
    )


@router.message(
    StateFilter(MeasurementLeadStates.waiting_for_phone),
    F.chat.type.in_({"group", "supergroup"}),
    F.text == "📲 Nomerni yuborish",
)
async def handle_ml_phone_group_btn(
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
    StateFilter(MeasurementLeadStates.waiting_for_phone),
    F.text,
    ~F.text.in_(MAIN_MENU_BUTTONS),
    ~F.text.startswith("/"),
)
async def handle_ml_phone(message: Message, state: FSMContext, **data: object) -> None:
    """User typed their phone number as text."""
    text = (message.text or "").strip()

    if text == _BTN_CANCEL:
        await _cancel_flow(message, state)
        return

    phone = normalize_phone(text)
    if not phone or not is_valid_uz_phone(phone):
        await message.answer(
            "Raqam noto'g'ri. O'zbekiston raqamini kiriting:\n"
            "<i>Namuna: +998 90 123 45 67</i>",
            reply_markup=_ml_phone_keyboard(is_private=(message.chat.type == "private")),
        )
        return

    await state.update_data(phone=phone)
    await state.set_state(MeasurementLeadStates.waiting_for_location)
    await message.answer(
        "✅ Raqam qabul qilindi.\n\n"
        "📍 Manzilingizni yozing (tuman, ko'cha yoki orientir):",
        reply_markup=_cancel_keyboard(),
    )


# ─── Step 3 : location ────────────────────────────────────────────────────────

@router.message(
    StateFilter(MeasurementLeadStates.waiting_for_location),
    F.text,
    ~F.text.in_(MAIN_MENU_BUTTONS),
    ~F.text.startswith("/"),
)
async def handle_ml_location(message: Message, state: FSMContext, **data: object) -> None:
    text = (message.text or "").strip()

    if text == _BTN_CANCEL:
        await _cancel_flow(message, state)
        return

    if len(text) < 2:
        await message.answer(
            "Iltimos, manzilingizni to'liqroq kiriting:",
            reply_markup=_cancel_keyboard(),
        )
        return

    await state.update_data(location=text)
    await state.set_state(MeasurementLeadStates.waiting_for_time)
    await message.answer(
        "🕐 Qaysi vaqt usta kelishi qulay?",
        reply_markup=_time_keyboard(),
    )


# ─── Step 4 : time preference + lead creation ────────────────────────────────

@router.message(
    StateFilter(MeasurementLeadStates.waiting_for_time),
    F.text,
    ~F.text.in_(MAIN_MENU_BUTTONS),
    ~F.text.startswith("/"),
)
async def handle_ml_time(message: Message, state: FSMContext, **data: object) -> None:
    text = (message.text or "").strip()

    if text == _BTN_CANCEL:
        await _cancel_flow(message, state)
        return

    # Accept any text including time_choices and free-form input
    time_pref = None if text == _BTN_SKIP_TIME else text
    fsm_data = await state.get_data()

    name = fsm_data.get("name", "")
    phone = fsm_data.get("phone", "")
    location = fsm_data.get("location", "")
    user_id = message.from_user.id if message.from_user else 0
    username = message.from_user.username if message.from_user else None

    await state.clear()

    # Send confirmation immediately so user doesn't wait on DB
    await message.answer(
        "✅ <b>Rahmat!</b>\n\n"
        "So'rovingiz qabul qilindi. Tez orada usta siz bilan bog'lanadi. 📞",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer("Asosiy menyu:", reply_markup=main_menu_keyboard())

    # Load AI scores and dimensions from DB (non-fatal, fire-and-forget via task)
    asyncio.create_task(
        _create_lead_and_notify(
            user_id=user_id,
            name=name,
            phone=phone,
            location=location,
            time_pref=time_pref,
            username=username,
            chat_type=message.chat.type,
            chat_id=message.chat.id,
        )
    )


async def _create_lead_and_notify(
    *,
    user_id: int,
    name: str,
    phone: str,
    location: str,
    time_pref: str | None,
    username: str | None,
    chat_type: str,
    chat_id: int,
) -> None:
    """Create a lead in DB and send admin notification. Fire-and-forget, never raises."""
    try:
        from infrastructure.database.models.ai_conversation import AiConversationModel
        from infrastructure.database.models.ai_memory import AiMemoryModel

        factory = get_session_factory()

        # Load AI scores + dimensions (non-fatal inner try)
        lead_temperature: str | None = None
        closing_confidence: float | None = None
        dimensions: str | None = None
        try:
            async with factory() as session:
                conv = await session.get(AiConversationModel, user_id)
                mem  = await session.get(AiMemoryModel, user_id)
                if conv:
                    lead_temperature   = conv.lead_temperature
                    closing_confidence = conv.closing_confidence
                if mem and mem.profile:
                    dimensions = mem.profile.get("last_dimensions")
        except Exception:
            log.warning("measurement_lead_ai_score_load_failed", user_id=user_id)

        # Create the lead
        async with factory() as session:
            svc = get_lead_service(session)
            lead = await svc.create_lead(
                user_id=user_id,
                category=CeilingCategory.ODNOTONNY,
                name=name,
                phone=phone,
                district=location,
                source=LeadSource.DEEPLINK,
            )
            await session.commit()

        # Persist AI scoring to the new lead (non-fatal)
        if lead_temperature is not None or closing_confidence is not None:
            try:
                from shared.utils.lead_scoring import compute_next_followup
                from infrastructure.database.repositories.lead_repo import PostgresLeadRepository
                next_fu = compute_next_followup(lead_temperature, closing_confidence)
                async with factory() as session:
                    await PostgresLeadRepository(session).update_ai_scoring(
                        lead.id,
                        lead_temperature=lead_temperature,
                        closing_confidence=closing_confidence,
                        next_follow_up_at=next_fu,
                    )
                    await session.commit()
            except Exception:
                log.warning("measurement_lead_ai_scoring_persist_failed", lead_id=lead.id)

        # Admin notification (fire-and-forget — already in a task)
        notif_svc = get_lead_notification_service()
        await notif_svc.notify_measurement_lead(
            lead=lead,
            time_pref=time_pref,
            dimensions=dimensions,
            lead_temperature=lead_temperature,
            closing_confidence=closing_confidence,
            chat_type=chat_type,
            chat_id=chat_id,
            tg_user_id=user_id,
            username=username,
        )

        log.info(
            "measurement_lead_created",
            lead_id=lead.id,
            user_id=user_id,
            lead_temperature=lead_temperature,
        )

    except Exception:
        log.exception("measurement_lead_creation_failed", user_id=user_id)


# ─── Cancel helper ────────────────────────────────────────────────────────────

async def _cancel_flow(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Bekor qilindi.",
        reply_markup=main_menu_keyboard(),
    )


@router.message(
    StateFilter(
        MeasurementLeadStates.waiting_for_name,
        MeasurementLeadStates.waiting_for_phone,
        MeasurementLeadStates.waiting_for_location,
        MeasurementLeadStates.waiting_for_time,
    ),
    Command("cancel"),
)
async def handle_ml_cancel_cmd(
    message: Message, state: FSMContext, **data: object
) -> None:
    await _cancel_flow(message, state)
