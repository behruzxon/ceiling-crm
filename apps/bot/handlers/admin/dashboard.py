"""
Admin dashboard handler.
Shows CRM summary stats in the admin group.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from apps.bot.filters.role import RoleFilter
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_lead_repo, get_user_repo
from shared.constants.enums import PipelineStage, UserRole
from shared.utils.formatting import bold, fmt_currency

router = Router(name="admin:dashboard")


@router.message(Command("dashboard"), RoleFilter(UserRole.ADMIN, UserRole.SUPERADMIN))
async def cmd_dashboard(message: Message, **data: object) -> None:
    """Show admin dashboard with CRM summary stats."""
    factory = get_session_factory()
    async with factory() as session:
        lead_repo = get_lead_repo(session)
        user_repo = get_user_repo(session)

        pipeline_counts = await lead_repo.get_pipeline_counts()
        active_users = await user_repo.count_active()

        total_leads = sum(pipeline_counts.values())
        new_count = pipeline_counts.get(PipelineStage.NEW, 0)
        contacted = pipeline_counts.get(PipelineStage.CONTACTED, 0)
        measurement = pipeline_counts.get(PipelineStage.MEASUREMENT, 0)
        quote = pipeline_counts.get(PipelineStage.QUOTE, 0)
        deal = pipeline_counts.get(PipelineStage.DEAL, 0)
        installation = pipeline_counts.get(PipelineStage.INSTALLATION, 0)
        completed = pipeline_counts.get(PipelineStage.COMPLETED, 0)
        lost = pipeline_counts.get(PipelineStage.LOST, 0)

        conversion_rate = (
            f"{(completed / total_leads * 100):.1f}%" if total_leads > 0 else "—"
        )

        text = (
            f"📊 {bold('CRM Dashboard')}\n\n"
            f"👥 Foydalanuvchilar: {active_users}\n"
            f"📋 Jami lidlar: {total_leads}\n"
            f"📈 Konversiya: {conversion_rate}\n\n"
            f"{'─' * 28}\n"
            f"🔵 Yangi: {new_count}\n"
            f"📞 Bog'lanildi: {contacted}\n"
            f"📐 O'lchov: {measurement}\n"
            f"💰 Narxlash: {quote}\n"
            f"🤝 Kelishuv: {deal}\n"
            f"🔧 O'rnatish: {installation}\n"
            f"✅ Tugallangan: {completed}\n"
            f"❌ Yo'qotilgan: {lost}\n"
        )

        await message.answer(text)
