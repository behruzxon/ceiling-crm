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

_MGMT_ROLES = (UserRole.MANAGER, UserRole.ADMIN, UserRole.SUPERADMIN)

_TEMP_EMOJI: dict[str, str] = {"hot": "\U0001f525", "warm": "\U0001f7e1", "cold": "\U0001f9ca"}


@router.message(Command("leads"), RoleFilter(*_MGMT_ROLES))
async def cmd_leads(message: Message, **data: object) -> None:
    """List 10 most recent leads with action buttons."""
    _tid = data.get("tenant_id")
    factory = get_session_factory()
    async with factory() as session:
        lead_repo = get_lead_repo(session, tenant_id=_tid)
        leads = await lead_repo.search(limit=10, offset=0)

        if not leads:
            await message.answer("\U0001f4cb Hozircha lidlar yo'q.")
            return

        for lead in leads:
            temp = _TEMP_EMOJI.get(lead.lead_temperature or "", "")
            score_str = f"\u2b50{lead.score}" if lead.score else ""
            reason = (lead.scoring_reasons or [""])[0]
            reason_line = f"\U0001f4a1 {reason}\n" if reason else ""

            text = (
                f"\U0001f4cb {bold(f'Lid #{lead.id}')} {score_str} {temp}\n"
                f"\U0001f464 {lead.name}\n"
                f"\U0001f4f1 {lead.phone}\n"
                f"\U0001f4cd {lead.district}\n"
                f"\U0001f3f7 {lead.category.value}\n"
                f"\U0001f4ca {lead.current_stage.value}\n"
                f"{reason_line}"
                f"\U0001f4c5 {lead.created_at.strftime('%d.%m.%Y %H:%M')}"
            )
            await message.answer(
                text,
                reply_markup=lead_card_keyboard(lead.id),
            )


@router.message(Command("hot"), RoleFilter(*_MGMT_ROLES))
async def cmd_hot(message: Message, **data: object) -> None:
    """Top hot leads sorted by score."""
    _tid = data.get("tenant_id")
    factory = get_session_factory()
    async with factory() as session:
        lead_repo = get_lead_repo(session, tenant_id=_tid)
        leads = await lead_repo.get_hot_leads(limit=10)

    if not leads:
        await message.answer("\U0001f525 Hozircha issiq lidlar yo'q.")
        return

    lines = [bold("\U0001f525 Issiq lidlar (top 10)"), ""]
    for lead in leads:
        temp = _TEMP_EMOJI.get(lead.lead_temperature or "", "")
        reason = (lead.scoring_reasons or [""])[0]
        phone_icon = "\U0001f4f1" if lead.phone and lead.phone != "\u2014" else ""
        reason_str = f" \u2014 {reason}" if reason else ""
        lines.append(
            f"#{lead.id} {temp} \u2b50{lead.score} {lead.name} "
            f"{phone_icon}{reason_str}"
        )

    await message.answer("\n".join(lines))


@router.message(Command("attention"), RoleFilter(*_MGMT_ROLES))
async def cmd_attention(message: Message, **data: object) -> None:
    """Leads needing immediate operator attention."""
    _tid = data.get("tenant_id")
    factory = get_session_factory()
    async with factory() as session:
        lead_repo = get_lead_repo(session, tenant_id=_tid)
        leads = await lead_repo.get_attention_leads(limit=10)

    if not leads:
        await message.answer("\u2705 Hozircha diqqat talab qiluvchi lidlar yo'q.")
        return

    lines = [bold("\U0001f6a8 Operator diqqati kerak"), ""]
    for lead in leads:
        reasons = " | ".join((lead.scoring_reasons or [])[:2])
        lines.append(
            f"#{lead.id} \u2b50{lead.score} {lead.name} "
            f"\U0001f4f1{lead.phone} \u2014 {reasons}"
        )

    await message.answer("\n".join(lines))
