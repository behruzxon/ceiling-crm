"""
apps.bot.handlers.private.order
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Order flow (Zakaz berish) FSM handler.

FSM flow
--------
  "✅ Zakaz berish"  (main-menu button)  /  /order command
    └─► waiting_for_name
          └─► waiting_for_phone   (contact button  OR  +998XXXXXXXXX manual entry)
                └─► waiting_for_district  (reply keyboard — 13 Qashqadaryo districts)
                      └─► waiting_for_category  (inline keyboard — 10 ceiling types)
                            └─► waiting_for_area   (dimensions OR direct m² OR skip)
                                  └─► waiting_for_location  (share-location OR skip)
                                        └─► [save lead → confirmation + CTA + admin alert]

Enum safety
-----------
  category is always resolved from FSM data via CeilingCategory(category_value),
  where category_value is a string the user selected from the inline keyboard.
  The default fallback is CeilingCategory.ODNOTONNY ("odnotonny").
  Using the enum member (not a raw string) guarantees that SQLAlchemy sends
  the correct .value to PostgreSQL — the value the DB enum stores.

Room dimensions
---------------
  create_lead() does not expose room_length / room_width / room_area, but those
  columns exist in LeadModel.  After lead creation the same session is used to
  update the three columns atomically within the same transaction.

  Accepted area input formats:
    "5x4"   "5 x 4"  "5х4"  "5×4"  "5*4"  → length × width
    "5 4"                                   → length × width (space-separated)
    "20m2"  "20 m2"  "20m²"  "20м2"        → direct area value

Admin notifications
-------------------
  After a successful DB write a formatted alert is sent to ADMIN_CHAT_ID.
  If the user shared their location a Google Maps link is appended.
  Admin send failure is non-fatal and never blocks the user confirmation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

import sqlalchemy as sa
from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from apps.bot.keyboards.main_menu import main_menu_keyboard
from infrastructure.database.models.lead import LeadModel
from infrastructure.database.session import get_session_factory
from core.services.lead_notification_service import is_hot_lead
from infrastructure.di import get_lead_notification_service, get_lead_repo, get_lead_service, get_pipeline_repo
from shared.config import get_settings
from shared.constants.enums import CeilingCategory, LeadSource, PipelineStage
from shared.logging import get_logger
from shared.utils.phone import is_valid_uz_phone, normalize_phone

log = get_logger(__name__)
router = Router(name="private:order")

# Stages at or past QUOTE — inserting QUOTE on top of these would be a downgrade.
_QUOTE_OR_BEYOND: frozenset[PipelineStage] = frozenset({
    PipelineStage.QUOTE,
    PipelineStage.DEAL,
    PipelineStage.INSTALLATION,
    PipelineStage.COMPLETED,
    PipelineStage.LOST,
})

# ── Admin DM that receives new-order alerts ───────────────────────────────────
# Uses BOT_ADMIN_USER_ID (private DM). Admin must have started the bot first.


# ─── Districts (Qashqadaryo region) ────────────────────────────────────────────

_DISTRICTS: tuple[str, ...] = (
    "Qarshi",
    "Shahrisabz",
    "Kitob",
    "Yakkabog'",
    "Chiroqchi",
    "G'uzor",
    "Koson",
    "Kasbi",
    "Muborak",
    "Nishon",
    "Dehqonobod",
    "Mirishkor",
    "Qamashi",
)

_DISTRICT_SET: frozenset[str] = frozenset(_DISTRICTS)  # O(1) membership check


# ─── Ceiling categories ─────────────────────────────────────────────────────────
# Each entry: (DB enum value, UI display label)

_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("gulli",         "🌸 Gulli"),
    ("odnotonny",     "🎨 Odnotonny"),
    ("mramor",        "🪨 Mramor"),
    ("qora_naqsh_uf", "🖤 Qora naqsh (UF)"),
    ("hi_tech",       "✨ Hi-tech"),
    ("kosmos",        "🌌 Kosmos"),
    ("osmon",         "☁️ Osmon"),
    ("oshxona",       "🍳 Oshxona"),
    ("naqsh_ramka",   "🖼 Naqsh ramka"),
    ("naqsh_oq",      "💎 Naqsh oq"),
)

_CATEGORY_VALUES: frozenset[str] = frozenset(v for v, _ in _CATEGORIES)


# ─── CTA inline keyboard ────────────────────────────────────────────────────────

_CTA_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="▶️ YouTube",        url="https://www.youtube.com/@vashpotolokuz")],
        [InlineKeyboardButton(text="📸 Instagram",      url="https://www.instagram.com/vashpotolok_uz")],
        [InlineKeyboardButton(text="💬 Telegram guruh", url="https://t.me/vashpotolokuz")],
    ]
)


# ─── Room-area parser ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class _AreaResult:
    """Immutable result of one room-size parse."""
    area: float
    length: float | None = None
    width: float | None = None


# Compiled once at module load — comma→dot normalisation applied before match.
_DIM_X_RE = re.compile(
    # "5x4"  "5 x 4"  "5х4" (Cyrillic)  "5×4"  "5*4"
    r"^(\d+(?:\.\d+)?)\s*[xXхХ×*]\s*(\d+(?:\.\d+)?)$"
)
_DIM_SPACE_RE = re.compile(
    # "5 4"  — two numbers separated by whitespace, no unit suffix
    r"^(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)$"
)
_AREA_ONLY_RE = re.compile(
    # "20m2"  "20 m2"  "20m²"  "20м2"  "20кв"  "20кв.м"
    r"^(\d+(?:\.\d+)?)\s*(?:m2|м2|m²|м²|кв\.?м?)$",
    re.IGNORECASE,
)


def _parse_area(raw: str) -> _AreaResult | None:
    """
    Parse room size from free-form user text.

    Returns None when no valid format is detected or values fall outside the
    allowed range (single dimension: 0–50 m; direct area: 0–500 m²).
    """
    text = raw.strip().replace(",", ".")

    m = _DIM_X_RE.match(text)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        if 0 < a <= 50 and 0 < b <= 50:
            return _AreaResult(area=round(a * b, 2), length=a, width=b)
        return None

    m = _DIM_SPACE_RE.match(text)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        if 0 < a <= 50 and 0 < b <= 50:
            return _AreaResult(area=round(a * b, 2), length=a, width=b)
        return None

    m = _AREA_ONLY_RE.match(text)
    if m:
        area = float(m.group(1))
        if 0 < area <= 500:
            return _AreaResult(area=round(area, 2))
        return None

    return None


# ─── FSM states ─────────────────────────────────────────────────────────────────

class OrderFlow(StatesGroup):
    waiting_for_name     = State()
    waiting_for_phone    = State()
    waiting_for_district = State()
    waiting_for_category = State()  # inline keyboard — ceiling type
    waiting_for_area     = State()
    waiting_for_location = State()


# ─── Keyboards ──────────────────────────────────────────────────────────────────

def _phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Raqamni ulashish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _district_keyboard() -> ReplyKeyboardMarkup:
    """Two-column grid; last row is single-button when district count is odd."""
    pairs = [
        [KeyboardButton(text=_DISTRICTS[i]), KeyboardButton(text=_DISTRICTS[i + 1])]
        for i in range(0, len(_DISTRICTS) - 1, 2)
    ]
    if len(_DISTRICTS) % 2 != 0:
        pairs.append([KeyboardButton(text=_DISTRICTS[-1])])
    return ReplyKeyboardMarkup(keyboard=pairs, resize_keyboard=True, one_time_keyboard=True)


def _category_keyboard() -> InlineKeyboardMarkup:
    """Two-column inline grid of ceiling category buttons."""
    rows: list[list[InlineKeyboardButton]] = []
    cats = list(_CATEGORIES)
    for i in range(0, len(cats), 2):
        row = [InlineKeyboardButton(text=cats[i][1], callback_data=f"cat:{cats[i][0]}")]
        if i + 1 < len(cats):
            row.append(InlineKeyboardButton(text=cats[i + 1][1], callback_data=f"cat:{cats[i + 1][0]}"))
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _area_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="⏭ O'tkazib yuborish")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _location_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Joylashuvni ulashish", request_location=True)],
            [KeyboardButton(text="⏭ O'tkazib yuborish")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# ─── Entry point ─────────────────────────────────────────────────────────────────
# Exact-match both button texts.  The old _ORDER_BTN_RE regex was broken because
# r"\uFE0F" in a raw string is the 6-char literal \uFE0F, not U+FE0F, so the
# effective pattern was "✅uFE0F?\s*Zakaz berish" which never matched the button.

_ORDER_TEXTS: frozenset[str] = frozenset({
    "✅ Zakaz berish",   # legacy emoji (kept for in-flight messages)
    "🛒 Zakaz berish",   # current emoji
    "📦 Buyurtma berish",
})


async def _start_order_flow(
    message: Message,
    state: FSMContext,
    user_id: int,
    first_name: str,
) -> None:
    """Core order-start logic — callable from message handlers AND callbacks.

    Extracted so that ``cta:order`` callback can reuse the exact same flow
    without duplicating DB + notification logic.
    """
    log.debug("order_flow_start", user_id=user_id)
    await state.clear()

    # ── Ensure a CRM lead exists for this user ────────────────────────────────
    # Creates a minimal placeholder if none exists; updates tracking fields
    # on an existing non-closed lead.  The lead_id is stored in FSM so that
    # _save_and_confirm can UPDATE it with real data instead of creating a dupe.
    if user_id:
        try:
            factory = get_session_factory()
            async with factory() as session:
                lead_repo = get_lead_repo(session)
                existing = await lead_repo.get_by_user_id(user_id)

                # Pick the most recent lead that is still open.
                # Exclude by pipeline stage (LOST / COMPLETED) AND by lead_status
                # ('won' / 'lost') so that a kanban-closed lead is never reused.
                _closed_stages = (PipelineStage.LOST.value, PipelineStage.COMPLETED.value)
                _closed_statuses = ("won", "lost")
                active = next(
                    (
                        l for l in existing
                        if l.current_stage.value not in _closed_stages
                        and l.lead_status not in _closed_statuses
                    ),
                    None,
                )

                if active:
                    # Update tracking fields on the existing lead
                    await lead_repo.update_last_action(active.id, "order_start")
                    if not active.lead_status:
                        await lead_repo.update_lead_status(active.id, "contacted")
                    await session.commit()
                    is_new_lead = False
                    tracked_lead_id = active.id
                else:
                    # No active lead — create a minimal placeholder so the
                    # lead appears in the kanban immediately
                    lead = await get_lead_service(session).create_lead(
                        user_id=user_id,
                        category=CeilingCategory.ODNOTONNY,
                        name=first_name,
                        phone="—",
                        district="Noma'lum",
                        source=LeadSource.DEEPLINK,
                        utm_source="order_flow",
                    )
                    await lead_repo.update_lead_status(lead.id, "contacted")
                    await lead_repo.update_last_action(lead.id, "order_start")
                    await session.commit()
                    is_new_lead = True
                    tracked_lead_id = lead.id

                # Re-read after commit so notification has the refreshed state
                notify_lead = await lead_repo.get_by_id(tracked_lead_id)

            await state.update_data(lead_id=tracked_lead_id)

            # Notify admins (fire-and-forget, non-fatal)
            if notify_lead:
                try:
                    notif_svc = get_lead_notification_service()
                    if is_new_lead:
                        await notif_svc.notify_new_lead(notify_lead)
                    if is_hot_lead(notify_lead):
                        await notif_svc.notify_hot_lead(notify_lead.id)
                except Exception:
                    log.exception("order_start_notify_error", lead_id=tracked_lead_id)

        except Exception:
            log.exception("order_start_lead_ensure_error", user_id=user_id)

    await state.set_state(OrderFlow.waiting_for_name)
    await message.answer(
        "📋 <b>Zakaz berish</b>\n\n"
        "Ismingizni kiriting:",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(F.chat.type == "private", F.text.in_(_ORDER_TEXTS))
@router.message(F.chat.type == "private", Command("order"))
async def cmd_order_start(message: Message, state: FSMContext, **data: object) -> None:
    """Clear any active FSM, ensure a lead row exists, begin the order flow."""
    user = message.from_user
    await _start_order_flow(
        message=message,
        state=state,
        user_id=user.id if user else 0,
        first_name=(user.first_name or "—") if user else "—",
    )


# ─── Step 1: Name ────────────────────────────────────────────────────────────────

@router.message(StateFilter(OrderFlow.waiting_for_name), F.text, ~F.text.startswith("/"))
async def handle_name(message: Message, state: FSMContext, **data: object) -> None:
    name = (message.text or "").strip()
    if len(name) < 2 or len(name) > 128:
        await message.answer("Iltimos, to'g'ri ism kiriting (2–128 belgi):")
        return

    await state.update_data(name=name)
    await state.set_state(OrderFlow.waiting_for_phone)
    await message.answer(
        f"✅ Ism: <b>{name}</b>\n\n"
        "📱 Telefon raqamingizni kiriting yoki tugmani bosing:\n"
        "<i>Masalan: <code>+998901234567</code></i>",
        reply_markup=_phone_keyboard(),
    )


# ─── Step 2: Phone ───────────────────────────────────────────────────────────────

@router.message(StateFilter(OrderFlow.waiting_for_phone), F.contact)
async def handle_phone_contact(message: Message, state: FSMContext, **data: object) -> None:
    """Accept a phone number shared via the Telegram contact button."""
    raw = message.contact.phone_number if message.contact else ""
    phone = normalize_phone(raw)
    if not phone or not is_valid_uz_phone(phone):
        await message.answer(
            "❌ Raqam o'qilmadi. Qo'lda kiriting:\n"
            "<i>Masalan: <code>+998901234567</code></i>",
            reply_markup=_phone_keyboard(),
        )
        return
    await _advance_from_phone(message, state, phone)


@router.message(StateFilter(OrderFlow.waiting_for_phone), F.text, ~F.text.startswith("/"))
async def handle_phone_text(message: Message, state: FSMContext, **data: object) -> None:
    """Accept a manually typed phone number."""
    phone = normalize_phone((message.text or "").strip())
    if not phone or not is_valid_uz_phone(phone):
        await message.answer(
            "❌ Noto'g'ri format. +998 bilan boshlanadigan raqam kiriting:\n"
            "<i>Masalan: <code>+998901234567</code></i>",
            reply_markup=_phone_keyboard(),
        )
        return
    await _advance_from_phone(message, state, phone)


async def _advance_from_phone(message: Message, state: FSMContext, phone: str) -> None:
    await state.update_data(phone=phone)
    await state.set_state(OrderFlow.waiting_for_district)
    await message.answer(
        f"✅ Telefon: <b>{phone}</b>\n\n"
        "📍 Tumaningizni tanlang:",
        reply_markup=_district_keyboard(),
    )


# ─── Step 3: District ────────────────────────────────────────────────────────────

@router.message(StateFilter(OrderFlow.waiting_for_district), F.text, ~F.text.startswith("/"))
async def handle_district(message: Message, state: FSMContext, **data: object) -> None:
    district = (message.text or "").strip()
    if district not in _DISTRICT_SET:
        await message.answer(
            "❌ Ro'yxatdan tuman tanlang:",
            reply_markup=_district_keyboard(),
        )
        return

    await state.update_data(district=district)
    await state.set_state(OrderFlow.waiting_for_category)
    # district keyboard is one_time_keyboard=True — it auto-dismisses on tap.
    # Send the category inline keyboard in the next message.
    await message.answer(
        f"✅ Tuman: <b>{district}</b>\n\n"
        "🏷 Shift turini tanlang:",
        reply_markup=_category_keyboard(),
    )


# ─── Step 4: Category ────────────────────────────────────────────────────────────

@router.callback_query(
    StateFilter(OrderFlow.waiting_for_category),
    F.data.startswith("cat:"),
)
async def handle_category(callback: CallbackQuery, state: FSMContext, **data: object) -> None:
    """Handle ceiling category selection from the inline keyboard."""
    value = (callback.data or "").removeprefix("cat:")
    if value not in _CATEGORY_VALUES:
        await callback.answer("❌ Noto'g'ri tanlov.")
        return

    label = next((lbl for v, lbl in _CATEGORIES if v == value), value)
    await state.update_data(category_value=value, category_label=label)
    await callback.answer()

    msg = callback.message
    if msg is None:
        return

    await state.set_state(OrderFlow.waiting_for_area)
    await msg.answer(
        f"✅ Shift turi: <b>{label}</b>\n\n"
        "📐 Xona o'lchamini kiriting:\n\n"
        "  • Uzunlik × Kenglik:  <code>5x4</code>  yoki  <code>5 4</code>\n"
        "  • To'g'ridan maydon:  <code>20m2</code>\n\n"
        "<i>Yoki o'tkazib yuborish uchun tugmani bosing.</i>",
        reply_markup=_area_keyboard(),
    )


# ─── Step 5: Area ────────────────────────────────────────────────────────────────

@router.message(
    StateFilter(OrderFlow.waiting_for_area),
    F.text == "⏭ O'tkazib yuborish",
)
async def handle_area_skip(message: Message, state: FSMContext, **data: object) -> None:
    await state.update_data(room_area=None, room_length=None, room_width=None)
    await state.set_state(OrderFlow.waiting_for_location)
    await message.answer(
        "📍 Manzilingizni ulashing yoki o'tkazib yuboring:",
        reply_markup=_location_keyboard(),
    )


@router.message(StateFilter(OrderFlow.waiting_for_area), F.text, ~F.text.startswith("/"))
async def handle_area(message: Message, state: FSMContext, **data: object) -> None:
    result = _parse_area(message.text or "")
    if result is None:
        await message.answer(
            "❌ O'lchamni to'g'ri kiriting.\n\n"
            "Namunalar:  <code>5x4</code>  •  <code>5 4</code>  •  <code>20m2</code>",
            reply_markup=_area_keyboard(),
        )
        return

    await state.update_data(
        room_area=result.area,
        room_length=result.length,
        room_width=result.width,
    )

    if result.length is not None:
        dim_label = f"{result.length} × {result.width} = <b>{result.area} m²</b>"
    else:
        dim_label = f"<b>{result.area} m²</b>"

    await state.set_state(OrderFlow.waiting_for_location)
    await message.answer(
        f"✅ Maydon: {dim_label}\n\n"
        "📍 Manzilingizni ulashing yoki o'tkazib yuboring:",
        reply_markup=_location_keyboard(),
    )


# ─── Step 6: Location (optional) ────────────────────────────────────────────────

@router.message(StateFilter(OrderFlow.waiting_for_location), F.location)
async def handle_location(message: Message, state: FSMContext, **data: object) -> None:
    loc = message.location
    if loc:
        await state.update_data(location=f"{loc.latitude:.6f},{loc.longitude:.6f}")
    await _save_and_confirm(message, state)


@router.message(
    StateFilter(OrderFlow.waiting_for_location),
    F.text == "⏭ O'tkazib yuborish",
)
async def handle_location_skip(message: Message, state: FSMContext, **data: object) -> None:
    await state.update_data(location=None)
    await _save_and_confirm(message, state)


@router.message(StateFilter(OrderFlow.waiting_for_location))
async def handle_location_fallback(message: Message, state: FSMContext, **data: object) -> None:
    """Reprompt on unexpected input during the location step."""
    await message.answer(
        "📍 Joylashuvni ulashing yoki «O'tkazib yuborish» tugmasini bosing:",
        reply_markup=_location_keyboard(),
    )


# ─── Admin notification ──────────────────────────────────────────────────────────

async def _notify_admin(
    bot: Bot,
    *,
    name: str,
    phone: str,
    district: str,
    category_label: str,
    area: float | None,
    lead_id: int,
    location: str | None,
) -> None:
    """
    Send a formatted new-order alert to the admin DM (BOT_ADMIN_USER_ID).
    Non-fatal: any exception is logged and swallowed so the user's
    confirmation flow is never affected.
    """
    admin_user_id = get_settings().bot.admin_user_id
    if not admin_user_id:
        log.warning("admin_user_id_not_set_skipping_order_notify", lead_id=lead_id)
        return

    area_line = f"📐 Maydon:   <b>{area} m²</b>\n" if area is not None else ""
    location_line = (
        f"🗺 Manzil:   https://maps.google.com/?q={location}\n"
        if location
        else ""
    )
    text = (
        "🔔 <b>Yangi buyurtma!</b>\n\n"
        f"👤 Ism:     <b>{name}</b>\n"
        f"📱 Telefon: <b>{phone}</b>\n"
        f"📍 Tuman:   <b>{district}</b>\n"
        f"🏷 Tur:     <b>{category_label}</b>\n"
        f"{area_line}"
        f"{location_line}"
        f"🔖 Lead ID: <code>#{lead_id}</code>"
    )
    try:
        await bot.send_message(chat_id=admin_user_id, text=text)
        log.info("admin_notified", lead_id=lead_id, admin_user_id=admin_user_id)
    except TelegramForbiddenError:
        log.warning(
            "admin_notify_forbidden_admin_must_start_bot",
            lead_id=lead_id,
            admin_user_id=admin_user_id,
        )
    except Exception:
        log.exception("admin_notify_failed", lead_id=lead_id)


# ─── Persistence + confirmation ──────────────────────────────────────────────────

async def _save_and_confirm(message: Message, state: FSMContext) -> None:
    """Persist the lead and send confirmation + CTA. Non-fatal on DB error."""
    fsm = await state.get_data()
    name: str             = fsm["name"]
    phone: str            = fsm["phone"]
    district: str         = fsm["district"]
    location: str | None  = fsm.get("location")
    room_area: float | None   = fsm.get("room_area")
    room_length: float | None = fsm.get("room_length")
    room_width: float | None  = fsm.get("room_width")

    # Category selected by the user; fall back to ODNOTONNY if FSM data is missing.
    category_value: str = fsm.get("category_value", CeilingCategory.ODNOTONNY.value)
    category_label: str = fsm.get("category_label", "🎨 Odnotonny")

    # Resolve user_id once as a plain int before the try block.
    # message.from_user is None only for channel posts, which private handlers
    # never receive — guarded here for strict type correctness.
    user_id: int = message.from_user.id if message.from_user else 0

    # Build notes from all available data so managers see context immediately.
    notes_parts: list[str] = [f"Zakaz berish orqali | Tur: {category_label}"]
    if room_area is not None:
        if room_length is not None and room_width is not None:
            notes_parts.append(f"Xona: {room_length}×{room_width} = {room_area} m²")
        else:
            notes_parts.append(f"Maydon: {room_area} m²")
    if location:
        notes_parts.append(f"Joylashuv: {location}")
    notes = " | ".join(notes_parts)

    # lead_id from cmd_order_start (stored in FSM). When present, we UPDATE
    # the existing placeholder rather than inserting a duplicate row.
    existing_lead_id: int | None = fsm.get("lead_id")

    lead_id: int | None = None
    try:
        factory = get_session_factory()
        async with factory() as session:
            if existing_lead_id:
                # ── UPDATE placeholder created at cmd_order_start ─────────────
                # Merge all real collected data into the existing row in one shot.
                update_values: dict = {
                    "name": name,
                    "phone": phone,
                    "district": district,
                    "category": CeilingCategory(category_value).value,
                    "notes": notes,
                    "utm_source": "order_flow",
                    "lead_status": "contacted",
                    "last_action": "order_done",
                    "updated_at": datetime.now(timezone.utc),
                }
                if room_area is not None:
                    update_values.update({
                        "room_length": room_length,
                        "room_width": room_width,
                        "room_area": room_area,
                    })
                await session.execute(
                    sa.update(LeadModel)
                    .where(LeadModel.id == existing_lead_id)
                    .values(**update_values)
                )
                pending_lead_id = existing_lead_id
            else:
                # ── Fallback: create a full lead (cmd_order_start did not run) ─
                # CeilingCategory(category_value) resolves the enum member from
                # the DB value string so SQLAlchemy sends the correct .value to PG.
                lead_service = get_lead_service(session)
                lead = await lead_service.create_lead(
                    user_id=user_id,
                    category=CeilingCategory(category_value),
                    name=name,
                    phone=phone,
                    district=district,
                    source=LeadSource.DEEPLINK,
                    utm_source="order_flow",
                    notes=notes,
                )
                # create_lead() does not expose room_* columns; update atomically.
                if room_area is not None:
                    await session.execute(
                        sa.update(LeadModel)
                        .where(LeadModel.id == lead.id)
                        .values(
                            room_length=room_length,
                            room_width=room_width,
                            room_area=room_area,
                        )
                    )
                pending_lead_id = lead.id

            # ── Pipeline stage: advance to QUOTE (idempotent) ─────────────────
            # Insert a QUOTE row unless the lead is already at QUOTE or later.
            # This is what makes the order visible in Kanban and Mening buyurtmalarim.
            pipeline_repo = get_pipeline_repo(session)
            current_stage = await pipeline_repo.get_current_stage(pending_lead_id)
            if current_stage not in _QUOTE_OR_BEYOND:
                await pipeline_repo.insert_stage(
                    lead_id=pending_lead_id,
                    stage=PipelineStage.QUOTE,
                    changed_by=user_id,
                    note="Zakaz berish orqali",
                )

            await session.commit()
            lead_id = pending_lead_id

        log.info("order_lead_saved", lead_id=lead_id, user_id=user_id, area=room_area)

    except Exception:
        # Non-fatal: clear state and send confirmation regardless so the user
        # is never left hanging inside the FSM on a DB failure.
        log.exception("order_lead_save_failed", user_id=user_id)

    await state.clear()

    # ── User-facing confirmation ───────────────────────────────────────────────
    area_line = f"📐 Maydon:   <b>{room_area} m²</b>\n" if room_area is not None else ""
    lead_line = f"\n<i>Buyurtma raqami: #{lead_id}</i>" if lead_id else ""

    confirmation = (
        "✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
        f"👤 Ism:     <b>{name}</b>\n"
        f"📱 Telefon: <b>{phone}</b>\n"
        f"📍 Tuman:   <b>{district}</b>\n"
        f"🏷 Tur:     <b>{category_label}</b>\n"
        f"{area_line}"
        "\nMenejerimiz 24 soat ichida siz bilan bog'lanadi. 🙏"
        f"{lead_line}"
    )

    await message.answer(confirmation, reply_markup=main_menu_keyboard())
    await message.answer("📲 Bizni kuzatib boring:", reply_markup=_CTA_KEYBOARD)

    # ── Admin notification ─────────────────────────────────────────────────────
    # Sent after the user already has their confirmation, so any admin-side
    # failure cannot affect the user experience.
    if lead_id is not None and message.bot is not None:
        await _notify_admin(
            message.bot,
            name=name,
            phone=phone,
            district=district,
            category_label=category_label,
            area=room_area,
            lead_id=lead_id,
            location=location,
        )

    # HOT lead alert after final save (deduped internally — safe to always call)
    if lead_id is not None:
        try:
            await get_lead_notification_service().notify_hot_lead(lead_id)
        except Exception:
            log.exception("order_hot_lead_notify_error", lead_id=lead_id)
