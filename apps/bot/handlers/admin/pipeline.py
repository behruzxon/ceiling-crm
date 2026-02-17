"""
Admin pipeline management handler.
Stage transitions, assignment, history view.
"""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from apps.bot.filters.role import RoleFilter
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_lead_repo
from shared.constants.enums import PipelineStage, UserRole
from shared.utils.formatting import bold

router = Router(name="admin:pipeline")

STAGE_EMOJI = {
    PipelineStage.NEW: "🔵",
    PipelineStage.CONTACTED: "📞",
    PipelineStage.MEASUREMENT: "📐",
    PipelineStage.QUOTE: "💰",
    PipelineStage.DEAL: "🤝",
    PipelineStage.INSTALLATION: "🔧",
    PipelineStage.COMPLETED: "✅",
    PipelineStage.LOST: "❌",
}


@router.message(Command("pipeline"), RoleFilter(UserRole.MANAGER, UserRole.ADMIN, UserRole.SUPERADMIN))
async def cmd_pipeline(message: Message, **data: object) -> None:
    """Show pipeline kanban summary with stage counts."""
    factory = get_session_factory()
    async with factory() as session:
        lead_repo = get_lead_repo(session)
        counts = await lead_repo.get_pipeline_counts()

        total = sum(counts.values())
        lines = [f"📊 {bold('Pipeline Kanban')}\n"]
        lines.append(f"Jami lidlar: {total}\n")
        lines.append(f"{'─' * 28}")

        for stage in PipelineStage:
            count = counts.get(stage, 0)
            emoji = STAGE_EMOJI.get(stage, "▪️")
            bar = "█" * min(count, 20)
            lines.append(f"{emoji} {stage.value}: {bold(str(count))} {bar}")

        await message.answer("\n".join(lines))
