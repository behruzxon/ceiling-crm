"""
Admin lead management handler.
View and manage all leads from admin group.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from apps.bot.filters.role import RoleFilter
from apps.bot.keyboards.inline_lead import lead_card_keyboard
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_lead_repo
from shared.constants.enums import UserRole
from shared.utils.formatting import bold

router = Router(name="admin:leads")


@router.message(Command("leads"), RoleFilter(UserRole.MANAGER, UserRole.ADMIN, UserRole.SUPERADMIN))
async def cmd_leads(message: Message, **data: object) -> None:
    """List 10 most recent leads with action buttons."""
    factory = get_session_factory()
    async with factory() as session:
        lead_repo = get_lead_repo(session)
        leads = await lead_repo.search(limit=10, offset=0)

        if not leads:
            await message.answer("📋 Hozircha lidlar yo'q.")
            return

        for lead in leads:
            text = (
                f"📋 {bold(f'Lid #{lead.id}')}\n"
                f"👤 {lead.name}\n"
                f"📱 {lead.phone}\n"
                f"📍 {lead.district}\n"
                f"🏷 {lead.category.value}\n"
                f"📊 {lead.current_stage.value}\n"
                f"📅 {lead.created_at.strftime('%d.%m.%Y %H:%M')}"
            )
            await message.answer(
                text,
                reply_markup=lead_card_keyboard(lead.id),
            )
