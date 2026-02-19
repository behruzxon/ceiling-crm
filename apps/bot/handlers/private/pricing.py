"""
Pricing calculator FSM handler.

FSM flow
--------
  "💰 Narx" / /price
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
  Discount : area > 40 m² → 10 %
             area > 20 m² →  5 %
             otherwise    →  0 %
  Safe input: dimension > 20 m triggers a one-shot confirmation prompt
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from apps.bot.keyboards.main_menu import main_menu_keyboard
from apps.bot.keyboards.pricing import DESIGN_BY_KEY, after_quote_keyboard, design_keyboard
from apps.bot.states.lead_capture import LeadCaptureStates
from apps.bot.states.pricing import PricingStates
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_lead_service
from shared.constants.enums import CeilingCategory, LeadSource
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="private:pricing")

# Matches "💰 Narx" regardless of VS-16 variation selector (\uFE0F) that
# Telegram keyboards may append to the emoji, and tolerates extra whitespace.
_PRICE_BTN_RE: re.Pattern[str] = re.compile(r"\U0001F4B0\uFE0F?\s*Narx", re.IGNORECASE)

# Matches any main-menu reply-keyboard button (VS-16 tolerant).
# Used to intercept button taps that arrive while a pricing FSM state is active.
_MENU_BTN_RE: re.Pattern[str] = re.compile(
    r"📂\uFE0F?\s*Katalog"
    r"|\U0001F4B0\uFE0F?\s*Narx"
    r"|📋\uFE0F?\s*Buyurtma"
    r"|📞\uFE0F?\s*Operator",
    re.IGNORECASE,
)


# ─── Business logic (pure, no I/O) ───────────────────────────────────────────

_TIERS: tuple[tuple[float, int], ...] = (
    (40.0, 10),  # area > 40 m²  → 10 %
    (20.0,  5),  # area > 20 m²  →  5 %
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
            if self.discount_pct else ""
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
        "Xona <b>uzunligini</b> metrda kiriting:\n"
        "<i>Masalan: <code>5.2</code></i>",
    )


# ─── Entry points ─────────────────────────────────────────────────────────────

@router.message(F.chat.type == "private", F.text.regexp(_PRICE_BTN_RE))
@router.message(F.chat.type == "private", Command("price"))
async def cmd_pricing_start(
    message: Message, state: FSMContext, **data: object
) -> None:
    """Clear any running FSM and begin the pricing flow."""
    log.debug("pricing_start_triggered", user_id=message.from_user and message.from_user.id)
    await start_pricing_flow(message, state)


# ─── Menu-button escape (waiting_for_length / waiting_for_width) ─────────────
# Must be registered BEFORE the numeric handlers so that pressing a main-menu
# button while a pricing state is active clears FSM and routes correctly
# instead of showing "invalid number".

@router.message(
    StateFilter(PricingStates.waiting_for_length, PricingStates.waiting_for_width),
    F.text.regexp(_MENU_BTN_RE),
)
async def handle_pricing_menu_escape(
    message: Message, state: FSMContext, **data: object
) -> None:
    """Clear pricing FSM and handle the tapped main-menu button."""
    await state.clear()
    text = message.text or ""
    if re.search(r"📞", text):
        await message.answer(
            "📞 <b>Operator bilan bog'lanish</b>\n\n"
            "+998 90 886 66 66\n"
            "+998 99 219 12 19",
            reply_markup=main_menu_keyboard(),
        )
    else:
        # For Katalog / Narx / Buyurtma: clear state and let the user
        # re-tap the button — show main menu so they can do so.
        await message.answer(
            "Hisoblash bekor qilindi.",
            reply_markup=main_menu_keyboard(),
        )


# ─── Step 1 : length ─────────────────────────────────────────────────────────

@router.message(StateFilter(PricingStates.waiting_for_length), F.text, ~F.text.startswith("/"))
async def handle_length(
    message: Message, state: FSMContext, **data: object
) -> None:
    """Validate length and advance to the width step.

    If the value exceeds 20 m (likely a typo), a one-shot confirmation prompt
    is shown. Any valid re-entry in the same state is accepted unconditionally.
    """
    fsm = await state.get_data()
    length = _parse_dimension(message.text)
    if length is None:
        await message.answer(
            "Son kiriting (masalan: <code>4.5</code>) yoki /cancel bosing."
        )
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
async def handle_width(
    message: Message, state: FSMContext, **data: object
) -> None:
    """Validate width, compute area, and present the design-selection keyboard.

    If the value exceeds 20 m (likely a typo), a one-shot confirmation prompt
    is shown. Any valid re-entry in the same state is accepted unconditionally.
    """
    fsm = await state.get_data()
    width = _parse_dimension(message.text)
    if width is None:
        await message.answer(
            "Son kiriting (masalan: <code>3.8</code>) yoki /cancel bosing."
        )
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
    F.message.chat.type == "private",
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
                category=CeilingCategory.MATTE_WHITE,
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

    if callback.message is None:
        return  # edge case: inline message already deleted

    # Remove the inline keyboard so the design selection is locked in visually.
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        quote.format_breakdown(),
        reply_markup=after_quote_keyboard(),
    )


# ─── Step 4 : post-quote actions ─────────────────────────────────────────────

@router.message(
    StateFilter(PricingStates.confirming_action),
    F.text == "📦 Buyurtma berish",
)
async def handle_order(
    message: Message, state: FSMContext, **data: object
) -> None:
    """
    Hand off to the lead-capture FSM.
    Pre-fill the calculated area so lead_capture.py can use it.
    """
    fsm = await state.get_data()
    await state.set_state(LeadCaptureStates.waiting_for_name)
    await state.update_data(pre_filled_area=fsm.get("area"))
    await message.answer(
        "📋 <b>Buyurtma rasmiylashtirish</b>\n\n"
        "Ismingizni kiriting:",
    )


@router.message(
    StateFilter(PricingStates.confirming_action),
    F.text == "📞 Operator",
)
async def handle_operator(
    message: Message, state: FSMContext, **data: object
) -> None:
    """Show operator contact details and return user to the main menu."""
    await state.clear()
    await message.answer(
        "📞 <b>Operator bilan bog'lanish</b>\n\n"
        "Menejerimiz tez orada siz bilan bog'lanadi.\n\n"
        "Murojaat uchun: @ceiling_manager",
        reply_markup=main_menu_keyboard(),
    )


@router.message(
    StateFilter(PricingStates.confirming_action),
    F.text == "🔄 Qayta hisoblash",
)
async def handle_recalc(
    message: Message, state: FSMContext, **data: object
) -> None:
    """Restart the pricing flow from scratch."""
    await state.clear()
    await state.set_state(PricingStates.waiting_for_length)
    await message.answer(
        "📐 Xona <b>uzunligini</b> metrda kiriting:\n"
        "<i>Masalan: <code>5.2</code></i>",
    )


@router.message(StateFilter(PricingStates.confirming_action))
async def handle_confirming_fallback(
    message: Message, state: FSMContext, **data: object
) -> None:
    """Catch-all: reprompt if user sends unexpected input after seeing quote."""
    await message.answer(
        "Iltimos, quyidagi tugmalardan birini tanlang:",
        reply_markup=after_quote_keyboard(),
    )
