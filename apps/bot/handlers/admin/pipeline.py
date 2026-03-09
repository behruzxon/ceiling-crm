"""
Admin pipeline management handler.
/pipeline [days]   — kanban summary + conversion % for the given period
/stage STAGE [pg]  — list latest leads in that stage, paginated
/lead ID           — lead card + last 20 timeline actions
lead_N / /lead_N   — shortcut alias for /lead N
"""
from __future__ import annotations

import re
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from apps.bot.filters.role import RoleFilter
from core.domain.lead import Lead
from core.services.pipeline_service import KANBAN_DISPLAY, KANBAN_STAGES
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_lead_action_repo, get_lead_repo, get_pipeline_service
from shared.constants.enums import PipelineStage, UserRole
from shared.utils.formatting import bold

router = Router(name="admin:pipeline")

_MGMT_ROLES = (UserRole.MANAGER, UserRole.ADMIN, UserRole.SUPERADMIN)

_TZ = ZoneInfo("Asia/Tashkent")

STAGE_EMOJI: dict[PipelineStage, str] = {
    PipelineStage.NEW: "🔵",
    PipelineStage.PACKAGE_SELECTED: "📦",
    PipelineStage.CONTACTED: "📞",
    PipelineStage.MEASUREMENT: "📐",
    PipelineStage.QUOTE: "💰",
    PipelineStage.DEAL: "🤝",
    PipelineStage.INSTALLATION: "🔧",
    PipelineStage.COMPLETED: "✅",
    PipelineStage.LOST: "❌",
}

ACTION_EMOJI: dict[str, str] = {
    "hot": "🔥",
    "warm": "🟡",
    "cold": "❄️",
    "phone": "📞",
    "measurement_set": "📅",
    "note": "📝",
    "block": "⛔",
    "lead_created": "🆕",
    "status_changed": "🔁",
    "order_done": "✅",
    "lead_assigned": "👤",
}

# Accept "DONE" as an alias for "COMPLETED" in /stage command
_STAGE_ALIASES: dict[str, PipelineStage] = {"DONE": PipelineStage.COMPLETED}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _summarize_payload(payload: dict) -> str:  # type: ignore[type-arg]
    """One-line summary of an action payload for the timeline."""
    if "new" in payload and "old" in payload:
        return f"{payload['old']} → {payload['new']}"
    if "new" in payload:
        return f"→ {payload['new']}"
    if "reason" in payload:
        return str(payload["reason"])[:50]
    if "manager_id" in payload:
        return f"manager #{payload['manager_id']}"
    if "source" in payload:
        return f"src={payload['source']}"
    return str(payload)[:50]


def _format_lead_card(lead: Lead) -> str:
    """HTML card for a single lead (no timeline)."""
    status_tag = f" [{lead.lead_status}]" if lead.lead_status else ""
    pkg_tag = f" | 📦 {lead.package_type}" if lead.package_type else ""
    score_tag = f" ⭐{lead.score}" if lead.score else ""
    stage_str = bold(lead.current_stage.value)
    area_line = f"📐 {lead.room_area} m²\n" if lead.room_area else ""
    mgr_line = f"👔 Manager: #{lead.assigned_manager_id}\n" if lead.assigned_manager_id else ""
    notes_line = f"📝 {lead.notes}\n" if lead.notes else ""
    return (
        f"📋 {bold(f'Lid #{lead.id}')}\n"
        f"👤 {lead.name}\n"
        f"📱 {lead.phone}\n"
        f"📍 {lead.district}\n"
        f"🏷 {lead.category.value}\n"
        f"📊 Bosqich: {stage_str}{status_tag}{score_tag}{pkg_tag}\n"
        f"📅 Yaratildi: {lead.created_at.astimezone(_TZ).strftime('%d.%m.%Y %H:%M')}\n"
        f"{area_line}{mgr_line}{notes_line}"
    )


def build_pipeline_keyboard(lead_id: int) -> InlineKeyboardMarkup:
    """4-button action keyboard attached to a lead card."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="➡️ Keyingi bosqich",
                callback_data=f"pipeline:next:{lead_id}",
            ),
            InlineKeyboardButton(
                text="⬅️ Oldingi bosqich",
                callback_data=f"pipeline:prev:{lead_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="❌ Yo'qotildi",
                callback_data=f"pipeline:lost:{lead_id}",
            ),
            InlineKeyboardButton(
                text="🕓 Timeline",
                callback_data=f"timeline:{lead_id}",
            ),
        ],
    ])


# ── /pipeline [days] ──────────────────────────────────────────────────────────

@router.message(Command("pipeline"), RoleFilter(*_MGMT_ROLES))
async def cmd_pipeline(message: Message, **data: object) -> None:
    """Show the kanban board as an inline keyboard with live stage counts."""
    _tid = data.get("tenant_id")
    factory = get_session_factory()
    async with factory() as session:
        pipeline_svc = get_pipeline_service(session, tenant_id=_tid)
        counts = await pipeline_svc.get_stage_counts()

    total = sum(counts.values())

    buttons: list[list[InlineKeyboardButton]] = []
    for kanban_stage in KANBAN_STAGES:
        label = KANBAN_DISPLAY[kanban_stage]
        cnt = counts.get(kanban_stage, 0)
        buttons.append([
            InlineKeyboardButton(
                text=f"{label} ({cnt})",
                callback_data=f"kanban:stage:{kanban_stage}",
            )
        ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(
        f"📊 {bold('Pipeline Kanban')}\n"
        f"Jami lidlar: {bold(str(total))}\n\n"
        "Bosqichni tanlang 👇",
        reply_markup=keyboard,
    )


# ── /stage STAGE [page] ───────────────────────────────────────────────────────

@router.message(Command("stage"), RoleFilter(*_MGMT_ROLES))
async def cmd_stage(message: Message, command: CommandObject, **data: object) -> None:
    """List leads in a pipeline stage with inline pagination (10 per page)."""
    if not command.args:
        valid = " | ".join(s.value for s in PipelineStage)
        await message.answer(
            f"Bosqich kiriting:\n/stage NEW|MEASUREMENT|DEAL|DONE|LOST\n\n"
            f"Barcha bosqichlar: {valid}"
        )
        return

    parts = command.args.strip().upper().split()
    stage_str = parts[0]

    # Alias resolution
    stage = _STAGE_ALIASES.get(stage_str)
    if stage is None:
        try:
            stage = PipelineStage(stage_str)
        except ValueError:
            valid = " | ".join(s.value for s in PipelineStage)
            await message.answer(f"Noto'g'ri bosqich.\nMavjudlar: {valid}")
            return

    page = 0
    if len(parts) > 1:
        try:
            page = max(0, int(parts[1]) - 1)
        except ValueError:
            pass

    _tid = data.get("tenant_id")
    await _send_stage_page(message, stage, page, tenant_id=_tid)


async def _send_stage_page(
    target: Message,
    stage: PipelineStage,
    page: int,
    edit: bool = False,
    *,
    tenant_id: int | None = None,
) -> None:
    """Fetch a page of leads for *stage* and send/edit the message."""
    page_size = 10
    factory = get_session_factory()
    async with factory() as session:
        lead_repo = get_lead_repo(session, tenant_id=tenant_id)
        leads = await lead_repo.search(
            stage=stage,
            limit=page_size + 1,
            offset=page * page_size,
        )

    has_more = len(leads) > page_size
    leads = leads[:page_size]

    if not leads:
        text = f"📭 {stage.value} bosqichida lid topilmadi (sahifa {page + 1})"
        if edit:
            await target.edit_text(text)
        else:
            await target.answer(text)
        return

    emoji = STAGE_EMOJI.get(stage, "▪️")
    lines = [f"{emoji} {bold(stage.value)} — sahifa {page + 1}\n"]
    for i, lead in enumerate(leads, start=page * page_size + 1):
        status_tag = f" [{lead.lead_status}]" if lead.lead_status else ""
        dt = lead.created_at.astimezone(_TZ).strftime("%d.%m %H:%M")
        lines.append(
            f"{i}. {bold(f'#{lead.id}')} {lead.name} · {lead.district}{status_tag}\n"
            f"   📱 {lead.phone} · {dt} · /lead_{lead.id}"
        )

    # Pagination keyboard
    row = []
    if page > 0:
        row.append(InlineKeyboardButton(
            text="◀️ Oldingi",
            callback_data=f"stage_page:{stage.value}:{page - 1}",
        ))
    if has_more:
        row.append(InlineKeyboardButton(
            text="▶️ Keyingi",
            callback_data=f"stage_page:{stage.value}:{page + 1}",
        ))
    keyboard = InlineKeyboardMarkup(inline_keyboard=[row]) if row else None

    text = "\n".join(lines)
    if edit:
        await target.edit_text(text, reply_markup=keyboard)
    else:
        await target.answer(text, reply_markup=keyboard)


# ── /lead <id>  and  lead_N shortcut ─────────────────────────────────────────

@router.message(Command("lead"), RoleFilter(*_MGMT_ROLES))
async def cmd_lead(message: Message, command: CommandObject, **data: object) -> None:
    """/lead <id> — full lead card + last 20 timeline actions."""
    if not command.args:
        await message.answer("ID kiriting: /lead 7")
        return
    try:
        lead_id = int(command.args.strip())
    except ValueError:
        await message.answer("Noto'g'ri format. Misol: /lead 7")
        return
    _tid = data.get("tenant_id")
    await _show_lead_with_timeline(message, lead_id, tenant_id=_tid)


@router.message(F.text.regexp(r"^/?lead_(\d+)$"), RoleFilter(*_MGMT_ROLES))
async def cmd_lead_shortcut(message: Message, **data: object) -> None:
    """Shortcut: 'lead_7' or '/lead_7' → same as /lead 7."""
    m = re.match(r"^/?lead_(\d+)$", message.text or "")
    if not m:
        return
    _tid = data.get("tenant_id")
    await _show_lead_with_timeline(message, int(m.group(1)), tenant_id=_tid)


async def _show_lead_with_timeline(
    message: Message,
    lead_id: int,
    *,
    tenant_id: int | None = None,
) -> None:
    """Fetch lead + last 20 actions and reply with card + pipeline keyboard."""
    factory = get_session_factory()
    async with factory() as session:
        lead_repo = get_lead_repo(session, tenant_id=tenant_id)
        action_repo = get_lead_action_repo(session, tenant_id=tenant_id)

        lead = await lead_repo.get_by_id(lead_id)
        if lead is None:
            await message.answer(f"Lid #{lead_id} topilmadi")
            return

        actions = await action_repo.get_lead_timeline(lead_id, limit=20)

    card = _format_lead_card(lead)

    timeline_lines = ["\n📈 Timeline (so'nggi harakatlar):"]
    if not actions:
        timeline_lines.append("  (harakatlar yo'q)")
    else:
        for act in reversed(actions):  # oldest → newest
            dt = act["created_at"].astimezone(_TZ).strftime("%d.%m %H:%M")
            emoji = ACTION_EMOJI.get(act["action_type"], "▪️")
            actor_name = act.get("first_name") or f"#{act['actor_user_id']}"
            username = act.get("username")
            actor_str = f"{actor_name} (@{username})" if username else actor_name
            payload_str = ""
            if act.get("payload"):
                payload_str = f" — {_summarize_payload(act['payload'])}"
            timeline_lines.append(
                f"{emoji} [{dt}] {act['action_type']} — {actor_str}{payload_str}"
            )

    full_text = card + "\n".join(timeline_lines)
    # Telegram message limit is 4096 chars
    if len(full_text) > 4000:
        full_text = full_text[:4000] + "\n…"

    await message.answer(full_text, reply_markup=build_pipeline_keyboard(lead_id))
