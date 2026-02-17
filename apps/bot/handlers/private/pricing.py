"""
Pricing calculator FSM handler.
Multi-step conversation to collect room dimensions and calculate quote.
"""
from __future__ import annotations
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from apps.bot.states.pricing import PricingStates

router = Router(name="private:pricing")

PRICE_PER_SQM = 120_000  # UZS per m²


@router.message(Command("price"))
async def cmd_pricing_start(message: Message, state: FSMContext, **data) -> None:
    """Start pricing flow — ask for room length."""
    await state.clear()
    await state.set_state(PricingStates.waiting_for_length)
    await message.answer(
        "📐 <b>Narxni hisoblash</b>\n\n"
        "Xona uzunligini metrda kiriting (masalan: <code>5.2</code>):"
    )


@router.message(StateFilter(PricingStates.waiting_for_length))
async def handle_length_input(message: Message, state: FSMContext, **data) -> None:
    """Receive room length, validate, and ask for width."""
    try:
        length = float(message.text.replace(",", "."))
        if length <= 0 or length > 50:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("Iltimos, to'g'ri son kiriting (masalan: <code>5.2</code>):")
        return

    await state.update_data(length=length)
    await state.set_state(PricingStates.waiting_for_width)
    await message.answer(
        f"Uzunlik: <b>{length} m</b> ✅\n\n"
        "Endi xona kengligini metrda kiriting (masalan: <code>4.0</code>):"
    )


@router.message(StateFilter(PricingStates.waiting_for_width))
async def handle_width_input(message: Message, state: FSMContext, **data) -> None:
    """Receive room width, compute area and display quote."""
    try:
        width = float(message.text.replace(",", "."))
        if width <= 0 or width > 50:
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("Iltimos, to'g'ri son kiriting (masalan: <code>4.0</code>):")
        return

    fsm_data = await state.get_data()
    length = fsm_data["length"]
    area = length * width
    total = int(area * PRICE_PER_SQM)

    await state.clear()
    await message.answer(
        f"📊 <b>Hisob-kitob natijasi</b>\n\n"
        f"Uzunlik: {length} m\n"
        f"Kenglik: {width} m\n"
        f"Maydon: <b>{area:.1f} m²</b>\n"
        f"Narx (m²): {PRICE_PER_SQM:,} UZS\n\n"
        f"💰 Jami: <b>{total:,} UZS</b>\n\n"
        "Buyurtma berish uchun /order bosing."
    )


@router.message(StateFilter(PricingStates.waiting_for_addons))
async def handle_addons_input(message: Message, state: FSMContext, **data) -> None:
    """Receive addon selections — redirect to pricing start for now."""
    await state.clear()
    await message.answer(
        "Qo'shimcha xizmatlar hozircha ishlab chiqilmoqda.\n"
        "Narxni qayta hisoblash uchun /price bosing."
    )
