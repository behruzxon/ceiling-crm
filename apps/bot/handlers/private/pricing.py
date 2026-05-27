"""
Pricing calculator FSM handler.

FSM flow
--------
  "🧮 Narx kalkulyator" / /price
    └─► waiting_for_length
          └─► waiting_for_width
                └─► choosing_design          ← inline keyboard (6 designs)
                      └─► [calculate + save draft lead + show breakdown]
                            └─► confirming_action
                                  ├─ "📦 Buyurtma berish" → LeadCaptureStates.waiting_for_name
                                  ├─ "📞 Operator"        → show contact + main menu
                                  └─ "🔄 Qayta hisoblash" → restart flow

Business rules (isolated in _calculate, not in handlers)
---------------------------------------------------------
  Pricing  : per-design price_per_sqm (see keyboards/pricing.py → DESIGN_BY_KEY)
  Discount : area > 40 m²              → 10 %
             area > DISCOUNT_THRESHOLD →  5 %
             otherwise                 →  0 %
  Promo    : area >= LED_PROMO_THRESHOLD AND design == LED_PROMO_DESIGN
             → informational LED strip promo message (price unchanged)
  Safe input: dimension > 20 m triggers a one-shot confirmation prompt
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from apps.bot.handlers.private.operator import start_operator_flow
from apps.bot.keyboards.main_menu import (
    BTN_OPERATOR,
    BTN_PRICE,
    MAIN_MENU_BUTTONS,
    main_menu_keyboard,
)
from apps.bot.keyboards.pricing import DESIGN_BY_KEY, after_quote_keyboard, design_keyboard
from apps.bot.states.lead_capture import LeadCaptureStates
from apps.bot.states.pricing import PricingStates
from core.services.journey_event_service import emit_journey_event
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_lead_service
from shared.constants.enums import CeilingCategory, JourneyEventType, LeadSource
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="private:pricing")

# Matches "LENGTHxWIDTH" (or *, ×, ga, spaces) with optional decimal commas/dots.
# Group 1 = length, Group 2 = width.
# Examples: "5ga4", "5*4", "5 x 4", "5 4", "5,2x3,3", "5.2 * 3.3"
_TWO_DIMS_RE: re.Pattern[str] = re.compile(
    r"^\s*([0-9]+(?:[.,][0-9]+)?)"  # first number
    r"(?:\s*(?:x|×|\*|ga)\s*|\s+)"  # separator: keyword/symbol OR whitespace
    r"([0-9]+(?:[.,][0-9]+)?)\s*$",  # second number
    re.IGNORECASE,
)


# ─── Promotion / discount constants ──────────────────────────────────────────

# Minimum area (m²) that qualifies for the 5 % volume discount.
DISCOUNT_THRESHOLD: float = 20.0

# Minimum area (m²) required for the LED strip promotional offer.
LED_PROMO_THRESHOLD: float = 50.0

# Design key that triggers the LED promo (must match DESIGN_BY_KEY in keyboards/pricing.py).
LED_PROMO_DESIGN: str = "gulli"


# ─── Business logic (pure, no I/O) ───────────────────────────────────────────

_TIERS: tuple[tuple[float, int], ...] = (
    (40.0, 10),  # area > 40 m²             → 10 %
    (DISCOUNT_THRESHOLD, 5),  # area > DISCOUNT_THRESHOLD →  5 %
)


@dataclass(frozen=True)
class _Quote:
    """Immutable result of one pricing calculation."""

    length: float
    width: float
    area: float
    design_name: str
    price_per_sqm: int
    gross_amount: int
    discount_pct: int
    discount_amount: int
    final_total: int

    def format_breakdown(self) -> str:
        """Return HTML-formatted price breakdown for Telegram."""
        discount_line = (
            f"\n🎁 Chegirma ({self.discount_pct}%): −{self.discount_amount:,} UZS"
            if self.discount_pct
            else ""
        )
        return (
            "📊 <b>Hisob-kitob natijasi</b>\n\n"
            f"📐 Uzunlik:   {self.length} m\n"
            f"📐 Kenglik:   {self.width} m\n"
            f"📐 Maydon:    <b>{self.area:.2f} m²</b>\n\n"
            f"🎨 Dizayn:    <b>{self.design_name}</b>\n"
            f"💵 Narx (m²): {self.price_per_sqm:,} UZS\n"
            f"💵 Umumiy:    {self.gross_amount:,} UZS"
            f"{discount_line}\n\n"
            f"💰 Jami: <b>{self.final_total:,} UZS</b>"
        )


def _calculate(
    length: float,
    width: float,
    price_per_sqm: int,
    design_name: str,
) -> _Quote:
    """Apply tiered discount and return a fully-populated quote."""
    area = round(length * width, 2)

    discount_pct = 0
    for threshold, pct in _TIERS:
        if area > threshold:
            discount_pct = pct
            break

    gross = int(area * price_per_sqm)
    discount_amount = int(gross * discount_pct / 100)
    final_total = gross - discount_amount

    return _Quote(
        length=length,
        width=width,
        area=area,
        design_name=design_name,
        price_per_sqm=price_per_sqm,
        gross_amount=gross,
        discount_pct=discount_pct,
        discount_amount=discount_amount,
        final_total=final_total,
    )


def _parse_dimension(text: str | None) -> float | None:
    """
    Parse a user-supplied room dimension.
    Accepts comma or dot decimal separator.
    Returns None if the value is not a positive float in (0, 50].
    """
    try:
        v = float((text or "").replace(",", ".").strip())
    except ValueError:
        return None
    return v if 0 < v <= 50 else None


def _parse_two_dimensions(text: str) -> tuple[float, float] | None:
    """Try to extract two dimensions from a single message.

    Returns ``(length, width)`` as floats, or ``None`` if fewer than two
    valid dimensions are found (caller should fall back to the step-by-step flow).
    """
    m = _TWO_DIMS_RE.match(text)
    if m is None:
        return None
    a = _parse_dimension(m.group(1))
    b = _parse_dimension(m.group(2))
    if a is None or b is None:
        return None
    return a, b


def _led_promo_eligible(area: float, design_key: str) -> bool:
    """Return True when the LED strip promo applies (informational only, no price change)."""
    return area >= LED_PROMO_THRESHOLD and design_key == LED_PROMO_DESIGN


# ─── Shared entry-point helper ────────────────────────────────────────────────


async def start_pricing_flow(reply_to: Message, state: FSMContext) -> None:
    """Reset FSM and send the length prompt.

    Public so the catalog handler can reuse it for the
    '💰 Narxni hisoblash' shortcut without duplicating logic.
    """
    await state.clear()
    await state.set_state(PricingStates.waiting_for_length)
    await reply_to.answer(
        "📐 <b>Narxni hisoblash</b>\n\n"
        "Uzunlik va kenglikni yuboring:\n"
        "<i>Masalan: <code>5x4</code> yoki <code>5 4</code></i>",
    )


# ─── Entry points ─────────────────────────────────────────────────────────────


@router.message(F.chat.type.in_({"private", "group", "supergroup"}), F.text == BTN_PRICE)
@router.message(F.chat.type.in_({"private", "group", "supergroup"}), Command("price"))
async def cmd_pricing_start(message: Message, state: FSMContext, **data: object) -> None:
    """Clear any running FSM and begin the pricing flow."""
    uid = message.from_user.id if message.from_user else 0
    log.debug("pricing_start_triggered", user_id=uid)
    await start_pricing_flow(message, state)
    asyncio.create_task(
        emit_journey_event(
            user_id=uid,
            event_type=JourneyEventType.USED_PRICE_CALCULATOR,
            source_handler="pricing:cmd_pricing_start",
        )
    )


# ─── Menu-button escape (waiting_for_length / waiting_for_width) ─────────────
# Must be registered BEFORE the numeric handlers so that pressing a main-menu
# button while a pricing state is active clears FSM and routes correctly
# instead of showing "invalid number".


@router.message(
    StateFilter(PricingStates.waiting_for_length, PricingStates.waiting_for_width),
    F.text.in_(MAIN_MENU_BUTTONS),
)
async def handle_pricing_menu_escape(message: Message, state: FSMContext, **data: object) -> None:
    """Clear pricing FSM and handle the tapped main-menu button."""
    await state.clear()
    if message.text == BTN_OPERATOR:
        # Hand off to the operator flow (start_operator_flow clears + sets state).
        await start_operator_flow(message, state)
    else:
        # For any other main-menu button: clear state and show the menu so
        # the user can tap again.
        await message.answer(
            "Hisoblash bekor qilindi.",
            reply_markup=main_menu_keyboard(),
        )


# ─── Step 1 : length ─────────────────────────────────────────────────────────


@router.message(StateFilter(PricingStates.waiting_for_length), F.text, ~F.text.startswith("/"))
async def handle_length(message: Message, state: FSMContext, **data: object) -> None:
    """Parse length (and optionally width) from the user's message.

    Fast path: if the text contains two valid dimensions (e.g. "5x4", "5 4",
    "5.2*3.3"), both are stored and the flow jumps straight to design selection.

    Slow path (fallback): a single number is treated as length only, then the
    bot asks for width in the next step (original step-by-step behaviour).

    If the input is unparseable, a short hint is shown and the state stays.
    """
    text = (message.text or "").strip()
    fsm = await state.get_data()

    # ── Fast path: two dimensions in one message ──────────────────────────
    pair = _parse_two_dimensions(text)
    if pair is not None:
        length, width = pair
        if (length > 20 or width > 20) and not fsm.get("_warned_pair"):
            await state.update_data(_warned_pair=True)
            await message.answer(
                f"⚠️ <b>{length} × {width} m</b> — bu juda katta ko'rinadi.\n"
                "Rostdan ham shundaymi? Tasdiqlash uchun qaytadan kiriting:"
            )
            return
        area = round(length * width, 2)
        await state.update_data(length=length, width=width, area=area)
        await state.set_state(PricingStates.choosing_design)
        await message.answer(
            f"✅ {length} × {width} m  |  Maydon: <b>{area:.2f} m²</b>\n\n"
            "Qaysi tur/dizaynni tanlaysiz?",
            reply_markup=design_keyboard(),
        )
        return

    # ── Slow path: single dimension (original step-by-step flow) ─────────
    length = _parse_dimension(text)
    if length is None:
        await message.answer("Masalan: <code>5x4</code> yoki <code>5 4</code>")
        return

    if length > 20 and not fsm.get("_warned_length"):
        await state.update_data(_warned_length=True)
        await message.answer(
            f"⚠️ <b>{length} m</b> — bu juda katta ko'rinadi (ehtimol xato).\n"
            "Rostdan ham shundaymi? Tasdiqlash uchun qaytadan kiriting:"
        )
        return

    await state.update_data(length=length)
    await state.set_state(PricingStates.waiting_for_width)
    await message.answer(
        f"✅ Uzunlik: <b>{length} m</b>\n\n"
        "Xona <b>kengligini</b> metrda kiriting:\n"
        "<i>Masalan: <code>3.8</code></i>",
    )


# ─── Step 2 : width → compute area → ask design ──────────────────────────────


@router.message(StateFilter(PricingStates.waiting_for_width), F.text, ~F.text.startswith("/"))
async def handle_width(message: Message, state: FSMContext, **data: object) -> None:
    """Validate width, compute area, and present the design-selection keyboard.

    If the value exceeds 20 m (likely a typo), a one-shot confirmation prompt
    is shown. Any valid re-entry in the same state is accepted unconditionally.
    """
    fsm = await state.get_data()
    width = _parse_dimension(message.text)
    if width is None:
        await message.answer("Son kiriting (masalan: <code>3.8</code>) yoki /cancel bosing.")
        return

    if width > 20 and not fsm.get("_warned_width"):
        await state.update_data(_warned_width=True)
        await message.answer(
            f"⚠️ <b>{width} m</b> — bu juda katta ko'rinadi (ehtimol xato).\n"
            "Rostdan ham shundaymi? Tasdiqlash uchun qaytadan kiriting:"
        )
        return

    length: float = fsm["length"]
    area = round(length * width, 2)

    await state.update_data(width=width, area=area)
    await state.set_state(PricingStates.choosing_design)
    await message.answer(
        f"✅ Kenglik: <b>{width} m</b>  |  Maydon: <b>{area:.2f} m²</b>\n\n"
        "Qaysi tur/dizaynni tanlaysiz?",
        reply_markup=design_keyboard(),
    )


# ─── Step 3 : design selected → calculate → persist → display ─────────────────


@router.callback_query(
    StateFilter(PricingStates.choosing_design),
    F.data.startswith("design:"),
)
async def handle_design_callback(
    callback: CallbackQuery, state: FSMContext, **data: object
) -> None:
    """Receive design selection, run full calculation, persist draft lead,
    and display the price breakdown with the action keyboard.
    """
    key = (callback.data or "").split(":", 1)[1]
    design = DESIGN_BY_KEY.get(key)
    if design is None:
        await callback.answer("Noma'lum dizayn.", show_alert=True)
        return

    await callback.answer()  # acknowledge — removes the Telegram loading indicator

    fsm = await state.get_data()
    length: float = fsm["length"]
    width: float = fsm["width"]
    area: float = fsm["area"]
    quote = _calculate(length, width, design.price_per_sqm, design.label)

    # ── Persist as a draft lead (non-fatal if DB is unavailable) ──────────
    user = callback.from_user
    placeholder_phone = f"TG:{user.id}"

    lead_id: int | None = None
    try:
        factory = get_session_factory()
        async with factory() as session:
            lead_service = get_lead_service(session)
            lead = await lead_service.create_lead(
                user_id=user.id,
                category=CeilingCategory.ODNOTONNY,
                name=user.full_name or user.first_name,
                phone=placeholder_phone,
                district="–",
                source=LeadSource.DEEPLINK,
                utm_source="price_calculator",
                notes=(
                    f"{design.label}: {area:.2f} m² "
                    f"× {design.price_per_sqm:,} UZS"
                    + (f" −{quote.discount_pct}%" if quote.discount_pct else "")
                    + f" = {quote.final_total:,} UZS"
                ),
            )
            await session.commit()
        lead_id = lead.id
        log.info(
            "price_lead_saved",
            lead_id=lead_id,
            user_id=user.id,
            design=key,
            area=area,
            total=quote.final_total,
        )
    except Exception:
        # Non-fatal: show the quote regardless of DB write outcome.
        log.exception("price_lead_save_failed", user_id=user.id)

    await state.update_data(
        design_key=key,
        design_name=design.label,
        price_per_sqm=design.price_per_sqm,
        final_total=quote.final_total,
        lead_id=lead_id,
    )
    await state.set_state(PricingStates.confirming_action)

    asyncio.create_task(
        emit_journey_event(
            user_id=user.id,
            event_type=JourneyEventType.PRICE_CALCULATED,
            event_data={
                "area_m2": area,
                "design": key,
                "price": quote.final_total,
                "currency": "UZS",
            },
            source_handler="pricing:handle_design_callback",
        )
    )

    if callback.message is None:
        return  # edge case: inline message already deleted

    # Remove the inline keyboard so the design selection is locked in visually.
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        quote.format_breakdown(),
        reply_markup=after_quote_keyboard(),
    )

    if _led_promo_eligible(area, key):
        await callback.message.answer(
            "🎁 Siz 50 m² dan oshganingiz uchun GULLI dizaynga "
            "LED lenta bepul aksiyasiga tushdingiz!"
        )


# ─── Step 4 : post-quote actions ─────────────────────────────────────────────


@router.message(
    StateFilter(PricingStates.confirming_action),
    F.text == "📦 Buyurtma berish",
)
async def handle_order(message: Message, state: FSMContext, **data: object) -> None:
    """
    Hand off to the lead-capture FSM.
    Pre-fill the calculated area so lead_capture.py can use it.
    """
    fsm = await state.get_data()
    await state.set_state(LeadCaptureStates.waiting_for_name)
    await state.update_data(pre_filled_area=fsm.get("area"))
    await message.answer(
        "📋 <b>Buyurtma rasmiylashtirish</b>\n\n" "Ismingizni kiriting:",
    )


@router.message(
    StateFilter(PricingStates.confirming_action),
    F.text == "☎️ Operator",
)
async def handle_operator(message: Message, state: FSMContext, **data: object) -> None:
    """Hand off to the operator contact-request flow."""
    await start_operator_flow(message, state)


@router.message(
    StateFilter(PricingStates.confirming_action),
    F.text == "🔄 Qayta hisoblash",
)
async def handle_recalc(message: Message, state: FSMContext, **data: object) -> None:
    """Restart the pricing flow from scratch."""
    await state.clear()
    await state.set_state(PricingStates.waiting_for_length)
    await message.answer(
        "📐 Xona <b>uzunligini</b> metrda kiriting:\n" "<i>Masalan: <code>5.2</code></i>",
    )


@router.message(StateFilter(PricingStates.confirming_action))
async def handle_confirming_fallback(message: Message, state: FSMContext, **data: object) -> None:
    """Catch-all: reprompt if user sends unexpected input after seeing quote."""
    await message.answer(
        "Iltimos, quyidagi tugmalardan birini tanlang:",
        reply_markup=after_quote_keyboard(),
    )
