"""
apps.bot.handlers.admin.lead_advice
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
/lead_advice <lead_id> — AI-generated sales advice for a specific lead.

Loads the lead from DB, computes score/classification, fetches AI memory
for recent messages, and calls the AI Sales Advice service.

Access: ADMIN / SUPERADMIN roles.
"""
from __future__ import annotations

from datetime import UTC, datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from apps.bot.filters.role import RoleFilter
from infrastructure.database.repositories.lead_repo import PostgresLeadRepository
from infrastructure.database.session import get_session_factory
from shared.constants.enums import UserRole
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="admin:lead_advice")

_MGMT_ROLES = (UserRole.ADMIN, UserRole.SUPERADMIN)

_STAGE_LABELS: dict[str, str] = {
    "NEW": "Yangi",
    "PACKAGE_SELECTED": "Paket tanlangan",
    "CONTACTED": "Bog'lanilgan",
    "MEASUREMENT": "O'lchov",
    "QUOTE": "Narx yuborilgan",
    "DEAL": "Kelishilgan",
    "INSTALLATION": "O'rnatish",
    "COMPLETED": "Tugallangan",
    "LOST": "Yo'qotilgan",
}


@router.message(Command("lead_advice"), RoleFilter(*_MGMT_ROLES))
async def cmd_lead_advice(message: Message, **data: object) -> None:
    """Generate AI sales advice for a lead."""
    # Parse lead_id from command
    if not message.text:
        await message.answer("\u274c Foydalanish: /lead_advice <lead_id>")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("\u274c Foydalanish: /lead_advice <lead_id>")
        return

    try:
        lead_id = int(parts[1])
    except ValueError:
        await message.answer("\u274c Lead ID raqam bo'lishi kerak.")
        return

    await message.answer("\U0001f9e0 AI maslahat tayyorlanmoqda...")

    try:
        # Load lead from DB
        factory = get_session_factory()
        async with factory() as session:
            repo = PostgresLeadRepository(session)
            lead = await repo.get_by_id(lead_id)

        if lead is None:
            await message.answer(f"\u274c Lid #{lead_id} topilmadi.")
            return

        # Compute classification
        from shared.utils.lead_scoring import compute_lead_score

        now = datetime.now(UTC)
        hours_inactive = (now - lead.updated_at).total_seconds() / 3600

        score_result = compute_lead_score(
            message_count=lead.score or 0,
            has_phone=bool(lead.phone and lead.phone != "\u2014"),
            has_area=lead.room_area is not None,
            has_district=bool(lead.district and lead.district != "Noma'lum"),
            hours_since_last_activity=hours_inactive,
            closing_confidence=lead.closing_confidence,
        )

        # Try to load recent messages from AI memory
        last_messages: list[str] = []
        try:
            from apps.bot.handlers.private.ai_memory import _load_ai_memory
            mem = await _load_ai_memory(lead.user_id)
            if mem and mem.get("last_user_message"):
                last_messages = [mem["last_user_message"]]
        except Exception:
            pass

        # Generate advice
        from core.services.ai_sales_advice import generate_sales_advice

        stage_val = (
            lead.current_stage.value
            if hasattr(lead.current_stage, "value")
            else str(lead.current_stage)
        )

        advice = await generate_sales_advice(
            lead_id=lead.id,
            lead_name=lead.name,
            lead_phone=lead.phone,
            lead_district=lead.district,
            lead_score=score_result.total_score,
            lead_classification=score_result.classification,
            pipeline_stage=stage_val,
            room_area=float(lead.room_area) if lead.room_area else None,
            package_type=lead.package_type,
            closing_confidence=lead.closing_confidence,
            hours_inactive=hours_inactive,
            last_messages=last_messages,
        )

        # Format response
        stage_label = _STAGE_LABELS.get(stage_val, stage_val)
        cached_tag = " (cached)" if advice.cached else ""

        actions_text = "\n".join(
            f"  \u2022 {a}" for a in advice.recommended_actions
        )

        text = (
            f"\U0001f9e0 <b>Lead #{lead.id} Advice</b>{cached_tag}\n\n"
            f"\U0001f4cb {lead.name} | {lead.phone}\n"
            f"\U0001f4cd {lead.district}\n"
            f"\U0001f3af Score: <b>{advice.lead_status}</b> ({score_result.total_score}/100)\n"
            f"\U0001f4c8 Stage: <b>{stage_label}</b>\n"
            f"\u23f0 Oxirgi faollik: {hours_inactive:.0f}h oldin\n\n"
            f"<b>Tavsiya etilgan harakatlar:</b>\n{actions_text}\n\n"
            f"<b>Tavsiya etilgan xabar:</b>\n"
            f"<code>{advice.suggested_message}</code>\n\n"
            f"\U0001f4a1 <i>{advice.reasoning}</i>"
        )

        await message.answer(text)

    except Exception:
        log.exception("lead_advice_command_failed", lead_id=lead_id)
        await message.answer("\u274c AI maslahat xatolik yuz berdi.")
