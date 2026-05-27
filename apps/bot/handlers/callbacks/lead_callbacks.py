"""
Lead card inline keyboard callbacks.
Handles button presses on lead cards sent to admin group.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from infrastructure.database.session import get_session_factory
from infrastructure.di import get_lead_action_repo, get_lead_service, get_user_service
from shared.exceptions.base import NotFoundError
from shared.utils.formatting import bold

router = Router(name="callbacks:leads")


@router.callback_query(F.data.startswith("lead:view:"))
async def cb_view_lead(callback: CallbackQuery, **data: object) -> None:
    """Show full lead details."""
    try:
        lead_id = int(callback.data.split(":")[-1])  # type: ignore[union-attr]
    except (ValueError, IndexError):
        await callback.answer("Noto'g'ri ma'lumot", show_alert=True)
        return

    factory = get_session_factory()
    async with factory() as session:
        lead_service = get_lead_service(session)
        try:
            lead = await lead_service.get_lead(lead_id)
        except NotFoundError:
            await callback.answer("Lid topilmadi", show_alert=True)
            return

        lead_title = f"Lid #{lead.id} \u2014 To'liq ma'lumot"
        text = (
            f"📋 {bold(lead_title)}\n\n"
            f"👤 Ism: {lead.name}\n"
            f"📱 Telefon: {lead.phone}\n"
            f"📍 Tuman: {lead.district}\n"
            f"🏷 Kategoriya: {lead.category.value}\n"
            f"📊 Bosqich: {lead.current_stage.value}\n"
            f"📝 Manba: {lead.source.value}\n"
            f"📅 Yaratildi: {lead.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        )
        if lead.room_area:
            text += f"📐 Maydon: {lead.room_area} m²\n"
        if lead.assigned_manager_id:
            text += f"👔 Manager: #{lead.assigned_manager_id}\n"
        if lead.notes:
            text += f"📝 Izoh: {lead.notes}\n"

        await callback.message.edit_text(text)  # type: ignore[union-attr]
        await callback.answer()


@router.callback_query(F.data.startswith("lead:assign:"))
async def cb_assign_lead(callback: CallbackQuery, **data: object) -> None:
    """Show manager selection keyboard for lead assignment."""
    try:
        lead_id = int(callback.data.split(":")[-1])  # type: ignore[union-attr]
    except (ValueError, IndexError):
        await callback.answer("Noto'g'ri ma'lumot", show_alert=True)
        return

    factory = get_session_factory()
    async with factory() as session:
        user_service = get_user_service(session)
        managers = await user_service.get_managers()

        if not managers:
            await callback.answer("Hech qanday manager topilmadi", show_alert=True)
            return

        buttons = [
            [InlineKeyboardButton(
                text=f"👤 {m.full_name}",
                callback_data=f"lead:do_assign:{lead_id}:{m.id}",
            )]
            for m in managers
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        await callback.message.edit_text(  # type: ignore[union-attr]
            f"👔 Lid #{lead_id} uchun manager tanlang:",
            reply_markup=keyboard,
        )
        await callback.answer()


@router.callback_query(F.data.startswith("lead:do_assign:"))
async def cb_do_assign(callback: CallbackQuery, **data: object) -> None:
    """Execute manager assignment."""
    parts = callback.data.split(":")  # type: ignore[union-attr]
    lead_id = int(parts[2])
    manager_id = int(parts[3])
    actor_id = callback.from_user.id

    factory = get_session_factory()
    async with factory() as session:
        try:
            lead_service = get_lead_service(session)
            lead = await lead_service.assign_manager(lead_id, manager_id, actor_id)
            await get_lead_action_repo(session).insert(
                lead_id, actor_id, "lead_assigned", payload={"manager_id": manager_id}
            )
            await session.commit()

            await callback.message.edit_text(  # type: ignore[union-attr]
                f"✅ Lid #{lead_id} managerga tayinlandi (ID: {manager_id})"
            )
            await callback.answer("Tayinlandi!")
        except NotFoundError:
            await callback.answer("Lid topilmadi", show_alert=True)
        except Exception:
            await session.rollback()
            await callback.answer("Xatolik yuz berdi", show_alert=True)
            raise
