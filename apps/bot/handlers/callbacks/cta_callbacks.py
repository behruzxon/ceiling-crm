"""
apps.bot.handlers.callbacks.cta_callbacks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Inline-button callbacks for the ``cta:*`` namespace.

Buttons originate from:
- apps.bot.ui.cta  (cta_keyboard / cta_discount_keyboard / cta_intent_keyboard)
- apps.bot.tasks.inactive_cta  (inactivity reminder)

Callback routing
----------------
  cta:discount  — show promo message + extended keyboard (re-usable discount prompt)
  cta:order     — start the full order FSM (reuses _start_order_flow from order.py)
  cta:pricing   — start the pricing calculator FSM (reuses start_pricing_flow)
  cta:operator  — start the operator contact flow (reuses start_operator_flow)
  cta:catalog   — show catalog section keyboard
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from apps.bot.handlers.private.operator import start_operator_flow
from apps.bot.handlers.private.order import _start_order_flow
from apps.bot.handlers.private.pricing import start_pricing_flow
from apps.bot.keyboards.catalog import catalog_list_keyboard
from apps.bot.ui.cta import cta_discount_keyboard
from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="callbacks:cta")

_CATALOG_INTRO = "📂 <b>Katalog</b>\n\nBo'limni tanlang:"


# ── cta:discount ──────────────────────────────────────────────────────────────


@router.callback_query(F.data == "cta:discount")
async def cb_cta_discount(callback: CallbackQuery, **data: object) -> None:
    """Show the discount promo text + extended keyboard."""
    await callback.answer()
    settings = get_settings()
    if callback.message:
        await callback.message.answer(
            settings.cta.discount_text,
            reply_markup=cta_discount_keyboard(),
        )


# ── cta:order ─────────────────────────────────────────────────────────────────


@router.callback_query(F.data == "cta:order")
async def cb_cta_order(callback: CallbackQuery, state: FSMContext, **data: object) -> None:
    """Start the full order FSM — same flow as tapping '🛒 Zakaz berish'."""
    await callback.answer()
    if not callback.message or not callback.from_user:
        return
    user = callback.from_user
    await _start_order_flow(
        message=callback.message,
        state=state,
        user_id=user.id,
        first_name=user.first_name or "—",
    )


# ── cta:pricing ───────────────────────────────────────────────────────────────


@router.callback_query(F.data == "cta:pricing")
async def cb_cta_pricing(callback: CallbackQuery, state: FSMContext, **data: object) -> None:
    """Start the pricing calculator — same flow as '💰 Narx kalkulyator'."""
    await callback.answer()
    if callback.message:
        await start_pricing_flow(callback.message, state)


# ── cta:operator ──────────────────────────────────────────────────────────────


@router.callback_query(F.data == "cta:operator")
async def cb_cta_operator(callback: CallbackQuery, state: FSMContext, **data: object) -> None:
    """Start the operator contact flow — same as '☎️ Operator'."""
    await callback.answer()
    if callback.message:
        await start_operator_flow(callback.message, state)


# ── cta:catalog ───────────────────────────────────────────────────────────────


@router.callback_query(F.data == "cta:catalog")
async def cb_cta_catalog(callback: CallbackQuery, **data: object) -> None:
    """Show the catalog section inline keyboard."""
    await callback.answer()
    if callback.message:
        await callback.message.answer(
            _CATALOG_INTRO,
            reply_markup=catalog_list_keyboard(),
        )
