"""
Lead capture FSM handler.
Collects name, phone, district from interested client.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from apps.bot.keyboards.main_menu import main_menu_keyboard
from apps.bot.states.lead_capture import LeadCaptureStates
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_lead_action_repo, get_lead_service
from shared.constants.enums import CeilingCategory, LeadSource
from shared.logging import get_logger
from shared.utils.phone import is_valid_uz_phone, normalize_phone

log = get_logger(__name__)

router = Router(name="private:lead_capture")


@router.message(Command("order"))
async def cmd_order(message: Message, state: FSMContext, **data: object) -> None:
    """Start lead capture flow — ask for name."""
    await state.clear()
    await state.set_state(LeadCaptureStates.waiting_for_name)
    await message.answer("👤 Ismingizni kiriting:")


@router.message(StateFilter(LeadCaptureStates.waiting_for_name))
async def handle_name(message: Message, state: FSMContext, **data: object) -> None:
    """Collect client name, validate, and ask for phone."""
    name = (message.text or "").strip()
    if len(name) < 2 or len(name) > 128:
        await message.answer("Iltimos, to'g'ri ism kiriting (2-128 belgi):")
        return

    await state.update_data(name=name)
    await state.set_state(LeadCaptureStates.waiting_for_phone)
    await message.answer(
        f"Ism: <b>{name}</b> ✅\n\n"
        "📱 Telefon raqamingizni kiriting (masalan: <code>+998901234567</code>):"
    )


@router.message(StateFilter(LeadCaptureStates.waiting_for_phone))
async def handle_phone(message: Message, state: FSMContext, **data: object) -> None:
    """Collect client phone, validate UZ format, and ask for district."""
    raw_phone = (message.text or "").strip()
    phone = normalize_phone(raw_phone)

    if phone is None or not is_valid_uz_phone(phone):
        await message.answer(
            "❌ Noto'g'ri telefon raqami.\n"
            "Masalan: <code>+998901234567</code>"
        )
        return

    await state.update_data(phone=phone)
    await state.set_state(LeadCaptureStates.waiting_for_district)
    await message.answer(
        f"Telefon: <b>{phone}</b> ✅\n\n"
        "📍 Tumaningizni kiriting (masalan: Yunusobod, Chilonzor):"
    )


@router.message(StateFilter(LeadCaptureStates.waiting_for_district))
async def handle_district(message: Message, state: FSMContext, **data: object) -> None:
    """Collect district, create lead via LeadService, and confirm."""
    district = (message.text or "").strip()
    if len(district) < 2:
        await message.answer("Iltimos, tumaningizni kiriting:")
        return

    fsm_data = await state.get_data()
    name = fsm_data["name"]
    phone = fsm_data["phone"]
    user_id = message.from_user.id  # type: ignore[union-attr]

    _tid = data.get("tenant_id")
    factory = get_session_factory()
    async with factory() as session:
        try:
            lead_service = get_lead_service(session, tenant_id=_tid)
            lead = await lead_service.create_lead(
                user_id=user_id,
                category=CeilingCategory.ODNOTONNY,  # default, can be refined later
                name=name,
                phone=phone,
                district=district,
                source=LeadSource.DEEPLINK,
            )
            await session.commit()

            await state.clear()
            await message.answer(
                "✅ <b>Arizangiz qabul qilindi!</b>\n\n"
                f"📋 Ariza raqami: <code>#{lead.id}</code>\n"
                f"👤 Ism: {name}\n"
                f"📱 Telefon: {phone}\n"
                f"📍 Tuman: {district}\n\n"
                "Operatorimiz tez orada siz bilan bog'lanadi.",
                reply_markup=main_menu_keyboard(),
            )

            log.info("lead_captured_via_bot", lead_id=lead.id, user_id=user_id)

            # Log lead creation event (fire-and-forget, own session)
            try:
                log_factory = get_session_factory()
                async with log_factory() as log_session:
                    await get_lead_action_repo(log_session, tenant_id=_tid).insert(
                        lead.id, user_id, "lead_created"
                    )
                    await log_session.commit()
            except Exception:
                log.exception("lead_created_action_log_error", lead_id=lead.id)

            # Notify admins about new lead (fire-and-forget)
            try:
                from infrastructure.di import get_lead_notification_service
                await get_lead_notification_service().notify_new_lead(lead)
            except Exception:
                log.exception("notify_new_lead_error", lead_id=lead.id)
        except Exception:
            await session.rollback()
            await state.clear()
            await message.answer(
                "❌ Xatolik yuz berdi. Iltimos, qayta urinib ko'ring.",
                reply_markup=main_menu_keyboard(),
            )
            raise
