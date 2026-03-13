"""
apps.bot.handlers.callbacks.sales_closer_callbacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Handles inline-keyboard callbacks from the AI Sales Closer CTA messages.

Callback data patterns:
  closer:book:today    — book measurement for today
  closer:book:tomorrow — book measurement for tomorrow
  closer:call          — start phone collection
  closer:catalog       — show catalog keyboard
  closer:price         — prompt area input for price calculation
  closer:later         — soft dismiss
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from shared.logging import get_logger

log = get_logger(__name__)

router = Router(name="callbacks:sales_closer")


# ── Measurement booking ─────────────────────────────────────────────────────


@router.callback_query(F.data == "closer:book:today")
@router.callback_query(F.data == "closer:book:tomorrow")
async def cb_closer_book(
    callback: CallbackQuery, state: FSMContext, **data: object
) -> None:
    """User wants to book a free measurement."""
    await callback.answer()
    if not callback.message:
        return

    from apps.bot.handlers.private.measurement_lead import start_measurement_flow

    await start_measurement_flow(callback.message, state)
    log.info(
        "closer_action",
        user_id=callback.from_user.id,
        action="book",
        time=callback.data.split(":")[-1] if callback.data else "unknown",
    )


# ── Phone collection ────────────────────────────────────────────────────────


@router.callback_query(F.data == "closer:call")
async def cb_closer_call(
    callback: CallbackQuery, state: FSMContext, **data: object
) -> None:
    """User agrees to share phone for a manager call-back."""
    await callback.answer()
    if not callback.message:
        return

    from apps.bot.handlers.private.ai_support import AiSupportStates

    await state.set_state(AiSupportStates.waiting_for_phone)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="\U0001f4f1 Telefonni yuborish", request_contact=True)],
            [KeyboardButton(text="\u274c Bekor qilish")],
        ],
        resize_keyboard=True,
    )
    await callback.message.answer(
        "Telefon raqamingizni yuboring yoki pastdagi tugmani bosing:",
        reply_markup=kb,
    )
    log.info("closer_action", user_id=callback.from_user.id, action="call")


# ── Catalog ──────────────────────────────────────────────────────────────────


@router.callback_query(F.data == "closer:catalog")
async def cb_closer_catalog(
    callback: CallbackQuery, **data: object
) -> None:
    """Show the visual catalog inline keyboard."""
    await callback.answer()
    if not callback.message:
        return

    from apps.bot.keyboards.catalog import catalog_list_keyboard

    await callback.message.answer(
        "Katalogimizdan o'zingizga yoqqan dizaynni tanlang:",
        reply_markup=catalog_list_keyboard(),
    )
    log.info("closer_action", user_id=callback.from_user.id, action="catalog")


# ── Price calculator ─────────────────────────────────────────────────────────


@router.callback_query(F.data == "closer:price")
async def cb_closer_price(
    callback: CallbackQuery, state: FSMContext, **data: object
) -> None:
    """Prompt user to enter room area so AI can calculate a price."""
    await callback.answer()
    if not callback.message:
        return

    from apps.bot.handlers.private.ai_support import AiSupportStates

    await state.set_state(AiSupportStates.waiting_for_ai_question)
    await callback.message.answer(
        "Xonangiz maydonini yozing (masalan: 20 m2) — narxni hisoblab beraman.",
    )
    log.info("closer_action", user_id=callback.from_user.id, action="price")


# ── Soft dismiss (later) ────────────────────────────────────────────────────


@router.callback_query(F.data == "closer:later")
async def cb_closer_later(
    callback: CallbackQuery, **data: object
) -> None:
    """User taps 'Later' — acknowledge and add +5 to lead score."""
    await callback.answer()
    if not callback.message:
        return

    # Small score bump — they engaged with the CTA even if not ready now
    try:
        from apps.bot.handlers.private.ai_support import _add_lead_score

        await _add_lead_score(callback.from_user.id, 5)
    except Exception:
        pass

    await callback.message.answer(
        "Mayli, tayyor bo'lganda yozing — doim yordam berishga tayyorman!",
    )
    log.info("closer_action", user_id=callback.from_user.id, action="later")
