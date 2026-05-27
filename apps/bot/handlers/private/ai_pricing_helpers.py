"""
apps.bot.handlers.private.ai_pricing_helpers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Price display helpers: combo confirmation and upsell flow.
"""
from __future__ import annotations

from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from apps.bot.handlers.private.ai_detection import _build_price_calc, _catalog_link_kb
from apps.bot.handlers.private.ai_states import (
    _UPSELL_SOFT_CTA,
    AiSupportStates,
    _ai_keyboard,
    _phone_request_keyboard,
)


async def _show_combo_confirmation(
    message: Message,
    state: FSMContext,
    area: float,
    district: str,
    design: str | None = None,
) -> None:
    """Show order summary card when area+district are both detected, then ask phone."""
    design_line = f"\n🎨 Dizayn: {design}" if design else ""
    text = (
        f"Zo'r 🙂\n\n"
        f"📏 Maydon: {area:g} m²\n"
        f"📍 Tuman: {district}"
        f"{design_line}\n\n"
        f"Zakazni rasmiylashtirish uchun telefon raqamingizni yuboring 🙂"
    )
    fsm_updates: dict[str, Any] = {"price_area": area, "price_district": district}
    if design:
        fsm_updates["price_design"] = design
    await state.update_data(**fsm_updates)
    await state.set_state(AiSupportStates.waiting_for_phone)
    kb = _phone_request_keyboard() if message.chat.type == "private" else _ai_keyboard()
    await message.answer(text, reply_markup=kb)


async def _show_price_upsell(
    message: Message,
    state: FSMContext,
    area: float,
    *,
    district: str | None = None,
    design: str | None = None,
) -> None:
    """Show price table -> ask district, OR show summary card -> ask phone if district known."""
    await state.update_data(price_area=area)
    if district:
        await _show_combo_confirmation(message, state, area, district, design)
    else:
        await message.answer(_build_price_calc(area), reply_markup=_catalog_link_kb())
        await state.set_state(AiSupportStates.waiting_for_district)
        await message.answer(_UPSELL_SOFT_CTA, reply_markup=_ai_keyboard())
