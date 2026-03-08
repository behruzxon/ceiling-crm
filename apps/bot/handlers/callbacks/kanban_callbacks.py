"""
Kanban pipeline callbacks.

Handlers:
  kanban:stage:{stage}              — show last 10 leads in a kanban column
  kanban:lead:{id}[:{from_stage}]   — show full lead detail card
  kanban:move:{lead_id}:{stage}     — move lead to a kanban column
  kanban:assign:{lead_id}           — show manager assignment picker
  kanban:assign_mgr:{lead_id}:{mgr} — assign a manager to the lead
  kanban:back                       — back to the main kanban board
  kanban:back:{stage}               — back to a specific stage's lead list

Callback data keys always stay ≤ 64 bytes (Telegram limit).
"""
from __future__ import annotations

from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from apps.bot.filters.role import RoleFilter
from core.services.pipeline_service import (
    KANBAN_DISPLAY,
    KANBAN_MOVE_TARGET,
    KANBAN_STAGES,
)
from infrastructure.database.session import get_session_factory
from infrastructure.di import (
    get_admin_group_service,
    get_audit_log_repo,
    get_lead_action_repo,
    get_lead_repo,
    get_pipeline_service,
    get_user_service,
)
from shared.constants.enums import UserRole
from shared.exceptions.base import NotFoundError
from shared.utils.formatting import bold

router = Router(name="callbacks:kanban")

_MGMT_ROLES = (UserRole.MANAGER, UserRole.ADMIN, UserRole.SUPERADMIN)
_TZ = ZoneInfo("Asia/Tashkent")

# How many leads to show per stage-detail page
_PAGE_SIZE = 10


# ── Helpers ───────────────────────────────────────────────────────────────────

def _kanban_main_keyboard(counts: dict[str, int]) -> InlineKeyboardMarkup:
    """Main kanban board: one button per stage, showing live count."""
    buttons: list[list[InlineKeyboardButton]] = []
    for stage in KANBAN_STAGES:
        label = KANBAN_DISPLAY[stage]
        cnt = counts.get(stage, 0)
        buttons.append([
            InlineKeyboardButton(
                text=f"{label} ({cnt})",
                callback_data=f"kanban:stage:{stage}",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _stage_list_keyboard(
    leads: list,  # list[Lead]
    kanban_stage: str,
    page: int,
    has_more: bool,
) -> InlineKeyboardMarkup:
    """Keyboard for a stage's lead list: one button per lead + navigation."""
    buttons: list[list[InlineKeyboardButton]] = []

    for lead in leads:
        score_tag = f" ⭐{lead.score}" if lead.score else ""
        name_short = lead.name[:18] + "…" if len(lead.name) > 18 else lead.name
        buttons.append([
            InlineKeyboardButton(
                text=f"#{lead.id} | {name_short}{score_tag}",
                callback_data=f"kanban:lead:{lead.id}:{kanban_stage}",
            )
        ])

    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="◀️ Oldingi",
            callback_data=f"kanban:pg:{kanban_stage}:{page - 1}",
        ))
    if has_more:
        nav_row.append(InlineKeyboardButton(
            text="▶️ Keyingi",
            callback_data=f"kanban:pg:{kanban_stage}:{page + 1}",
        ))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([
        InlineKeyboardButton(text="🔙 Kanban", callback_data="kanban:back"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _lead_detail_keyboard(lead_id: int, from_stage: str) -> InlineKeyboardMarkup:
    """Keyboard for a lead detail card: move-to buttons + assign + back."""
    move_row: list[InlineKeyboardButton] = []
    for stage in KANBAN_STAGES:
        label = KANBAN_DISPLAY[stage]
        # Short emoji only to save space (5 buttons in one row)
        emoji = label.split()[0]
        move_row.append(InlineKeyboardButton(
            text=emoji,
            callback_data=f"kanban:move:{lead_id}:{stage}",
        ))

    return InlineKeyboardMarkup(inline_keyboard=[
        move_row,
        [
            InlineKeyboardButton(
                text="👔 Manager belgilash",
                callback_data=f"kanban:assign:{lead_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔙 Orqaga",
                callback_data=f"kanban:back:{from_stage}",
            ),
            InlineKeyboardButton(
                text="🕓 Timeline",
                callback_data=f"timeline:{lead_id}",
            ),
        ],
    ])


def _format_lead_card(lead) -> str:  # type: ignore[type-arg]
    """HTML card for the kanban lead detail view."""
    tz = _TZ
    stage_str = bold(lead.current_stage.value)
    status_tag = f" [{lead.lead_status}]" if lead.lead_status else ""
    pkg_tag = f"\n📦 Paket: {lead.package_type}" if lead.package_type else ""
    score_tag = f"\n⭐ Score: {lead.score}" if lead.score else ""
    area_line = f"\n📐 Maydon: {lead.room_area} m²" if lead.room_area else ""
    mgr_line = f"\n👔 Manager: #{lead.assigned_manager_id}" if lead.assigned_manager_id else ""
    notes_line = f"\n📝 {lead.notes}" if lead.notes else ""
    dt = lead.created_at.astimezone(tz).strftime("%d.%m.%Y %H:%M")
    return (
        f"📋 {bold(f'Lid #{lead.id}')}\n"
        f"👤 {lead.name}\n"
        f"📱 {lead.phone}\n"
        f"📍 {lead.district}\n"
        f"🏷 {lead.category.value}\n"
        f"📊 Bosqich: {stage_str}{status_tag}"
        f"{pkg_tag}{score_tag}{area_line}{mgr_line}{notes_line}\n"
        f"📅 Yaratildi: {dt}"
    )


# ── kanban:back ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "kanban:back", RoleFilter(*_MGMT_ROLES))
async def cb_kanban_back(callback: CallbackQuery, **data: object) -> None:
    """Return to the main kanban board with refreshed counts."""
    factory = get_session_factory()
    async with factory() as session:
        pipeline_svc = get_pipeline_service(session)
        counts = await pipeline_svc.get_stage_counts()

    total = sum(counts.values())
    keyboard = _kanban_main_keyboard(counts)
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"📊 {bold('Pipeline Kanban')}\n"
        f"Jami lidlar: {bold(str(total))}\n\n"
        "Bosqichni tanlang 👇",
        reply_markup=keyboard,
    )
    await callback.answer()


# ── kanban:back:{stage} ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("kanban:back:"), RoleFilter(*_MGMT_ROLES))
async def cb_kanban_back_stage(callback: CallbackQuery, **data: object) -> None:
    """Return to a specific stage's lead list (page 0)."""
    kanban_stage = callback.data.split(":")[2]  # type: ignore[union-attr]
    if kanban_stage not in KANBAN_STAGES:
        await callback.answer("Noto'g'ri bosqich", show_alert=True)
        return

    factory = get_session_factory()
    async with factory() as session:
        pipeline_svc = get_pipeline_service(session)
        leads = await pipeline_svc.get_leads_by_stage(kanban_stage, limit=_PAGE_SIZE + 1)

    has_more = len(leads) > _PAGE_SIZE
    leads = leads[:_PAGE_SIZE]

    display = KANBAN_DISPLAY[kanban_stage]
    if not leads:
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"{display} — lid topilmadi",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Kanban", callback_data="kanban:back"),
            ]]),
        )
        await callback.answer()
        return

    keyboard = _stage_list_keyboard(leads, kanban_stage, page=0, has_more=has_more)
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"{display} — {len(leads)}{'+'if has_more else ''} lead\n\n"
        "Lidni tanlang 👇",
        reply_markup=keyboard,
    )
    await callback.answer()


# ── kanban:stage:{stage} ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("kanban:stage:"), RoleFilter(*_MGMT_ROLES))
async def cb_kanban_stage(callback: CallbackQuery, **data: object) -> None:
    """Show last 10 leads in a kanban stage as clickable buttons."""
    kanban_stage = callback.data.split(":")[2]  # type: ignore[union-attr]
    if kanban_stage not in KANBAN_STAGES:
        await callback.answer("Noto'g'ri bosqich", show_alert=True)
        return

    factory = get_session_factory()
    async with factory() as session:
        pipeline_svc = get_pipeline_service(session)
        leads = await pipeline_svc.get_leads_by_stage(kanban_stage, limit=_PAGE_SIZE + 1)

    has_more = len(leads) > _PAGE_SIZE
    leads = leads[:_PAGE_SIZE]

    display = KANBAN_DISPLAY[kanban_stage]

    if not leads:
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"{display} — bu bosqichda lid topilmadi",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔙 Kanban", callback_data="kanban:back"),
            ]]),
        )
        await callback.answer()
        return

    keyboard = _stage_list_keyboard(leads, kanban_stage, page=0, has_more=has_more)
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"{display} — {len(leads)}{'+'if has_more else ''} lead\n\n"
        "Lidni tanlang 👇",
        reply_markup=keyboard,
    )
    await callback.answer()


# ── kanban:pg:{stage}:{page} ──────────────────────────────────────────────────

@router.callback_query(F.data.startswith("kanban:pg:"), RoleFilter(*_MGMT_ROLES))
async def cb_kanban_page(callback: CallbackQuery, **data: object) -> None:
    """Paginate through leads in a kanban stage."""
    parts = callback.data.split(":")  # type: ignore[union-attr]
    kanban_stage = parts[2]
    try:
        page = int(parts[3])
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri sahifa", show_alert=True)
        return

    if kanban_stage not in KANBAN_STAGES:
        await callback.answer("Noto'g'ri bosqich", show_alert=True)
        return

    offset = page * _PAGE_SIZE
    factory = get_session_factory()
    async with factory() as session:
        pipeline_svc = get_pipeline_service(session)
        leads = await pipeline_svc.get_leads_by_stage(
            kanban_stage, limit=_PAGE_SIZE + 1, offset=offset
        )

    has_more = len(leads) > _PAGE_SIZE
    leads = leads[:_PAGE_SIZE]

    display = KANBAN_DISPLAY[kanban_stage]

    if not leads:
        await callback.answer("Boshqa lid yo'q", show_alert=True)
        return

    keyboard = _stage_list_keyboard(leads, kanban_stage, page=page, has_more=has_more)
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"{display} — sahifa {page + 1}\n\n"
        "Lidni tanlang 👇",
        reply_markup=keyboard,
    )
    await callback.answer()


# ── kanban:lead:{id}[:{from_stage}] ──────────────────────────────────────────

@router.callback_query(F.data.startswith("kanban:lead:"), RoleFilter(*_MGMT_ROLES))
async def cb_kanban_lead(callback: CallbackQuery, **data: object) -> None:
    """Show full lead detail card with move + assign buttons."""
    parts = callback.data.split(":")  # type: ignore[union-attr]
    try:
        lead_id = int(parts[2])
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri ID", show_alert=True)
        return
    from_stage = parts[3] if len(parts) > 3 else KANBAN_STAGES[0]

    factory = get_session_factory()
    async with factory() as session:
        pipeline_svc = get_pipeline_service(session)
        lead = await pipeline_svc.get_lead(lead_id)

    if lead is None:
        await callback.answer(f"Lid #{lead_id} topilmadi", show_alert=True)
        return

    card = _format_lead_card(lead)
    keyboard = _lead_detail_keyboard(lead_id, from_stage)
    await callback.message.edit_text(  # type: ignore[union-attr]
        card,
        reply_markup=keyboard,
    )
    await callback.answer()


# ── kanban:move:{lead_id}:{stage} ────────────────────────────────────────────

@router.callback_query(F.data.startswith("kanban:move:"), RoleFilter(*_MGMT_ROLES))
async def cb_kanban_move(callback: CallbackQuery, **data: object) -> None:
    """Move a lead to a kanban column (admin override, all side-effects logged)."""
    parts = callback.data.split(":")  # type: ignore[union-attr]
    try:
        lead_id = int(parts[2])
        new_stage = parts[3]
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri ma'lumot", show_alert=True)
        return

    if new_stage not in KANBAN_STAGES:
        await callback.answer("Noto'g'ri bosqich", show_alert=True)
        return

    actor_id: int = callback.from_user.id  # type: ignore[union-attr]
    actor_name: str = callback.from_user.full_name  # type: ignore[union-attr]

    factory = get_session_factory()
    async with factory() as session:
        try:
            pipeline_svc = get_pipeline_service(session)
            lead = await pipeline_svc.move_stage(
                lead_id=lead_id,
                new_kanban_stage=new_stage,
                actor_id=actor_id,
            )
            await session.commit()

            # Notify admin groups
            admin_group_svc = get_admin_group_service(session)
            chat_ids = await admin_group_svc.list_all_chat_ids()
        except NotFoundError:
            await callback.answer("Lid topilmadi", show_alert=True)
            return
        except Exception:
            await session.rollback()
            await callback.answer("Xatolik yuz berdi", show_alert=True)
            raise

    stage_label = KANBAN_DISPLAY[new_stage]
    pipeline_stage = KANBAN_MOVE_TARGET[new_stage]

    # Update the message in-place to the refreshed lead card
    card = _format_lead_card(lead)
    keyboard = _lead_detail_keyboard(lead_id, new_stage)
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"✅ Bosqich o'zgartirildi: {stage_label}\n\n{card}",
        reply_markup=keyboard,
    )
    await callback.answer(f"→ {stage_label}")

    # Notify admin groups (fire-and-forget, ignore individual failures)
    bot: Bot = callback.bot  # type: ignore[assignment]
    notify_text = (
        f"📊 Lid #{lead_id} bosqichi o'zgartirildi\n"
        f"👤 {lead.name}\n"
        f"🔄 Yangi bosqich: {stage_label} ({pipeline_stage.value})\n"
        f"👮 Admin: {actor_name}"
    )
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, notify_text)
        except Exception:
            pass


# ── kanban:assign:{lead_id} ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("kanban:assign:"), RoleFilter(*_MGMT_ROLES))
async def cb_kanban_assign(callback: CallbackQuery, **data: object) -> None:
    """Show a list of managers to assign to the lead."""
    try:
        lead_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri ID", show_alert=True)
        return

    factory = get_session_factory()
    async with factory() as session:
        user_svc = get_user_service(session)
        managers = await user_svc.get_managers()

    if not managers:
        await callback.answer("Faol menejerlar topilmadi", show_alert=True)
        return

    buttons: list[list[InlineKeyboardButton]] = []
    for mgr in managers[:10]:  # cap at 10 to stay within message limits
        name = mgr.first_name
        if mgr.username:
            name += f" @{mgr.username}"
        buttons.append([
            InlineKeyboardButton(
                text=f"👤 {name}",
                callback_data=f"kanban:assign_mgr:{lead_id}:{mgr.id}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="🔙 Orqaga",
            callback_data=f"kanban:lead:{lead_id}",
        )
    ])

    await callback.message.edit_text(  # type: ignore[union-attr]
        f"👔 Lid #{lead_id} uchun menejerni tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )
    await callback.answer()


# ── kanban:assign_mgr:{lead_id}:{mgr_id} ─────────────────────────────────────

@router.callback_query(F.data.startswith("kanban:assign_mgr:"), RoleFilter(*_MGMT_ROLES))
async def cb_kanban_assign_mgr(callback: CallbackQuery, **data: object) -> None:
    """Assign a manager to the lead and return to the lead card."""
    parts = callback.data.split(":")  # type: ignore[union-attr]
    try:
        lead_id = int(parts[2])
        mgr_id  = int(parts[3])
    except (IndexError, ValueError):
        await callback.answer("Noto'g'ri ma'lumot", show_alert=True)
        return

    actor_id: int = callback.from_user.id  # type: ignore[union-attr]

    factory = get_session_factory()
    async with factory() as session:
        try:
            lead_repo   = get_lead_repo(session)
            action_repo = get_lead_action_repo(session)
            audit_repo  = get_audit_log_repo(session)

            lead = await lead_repo.assign_manager(lead_id, mgr_id, reason="kanban_manual")

            await action_repo.insert(
                lead_id=lead_id,
                actor_user_id=actor_id,
                action_type="lead_assigned",
                payload={"manager_id": mgr_id},
            )
            await audit_repo.insert(
                actor_id=actor_id,
                action="lead.manager_assigned",
                entity_type="lead",
                entity_id=lead_id,
                new_value={"manager_id": mgr_id},
            )
            await session.commit()
        except Exception:
            await session.rollback()
            await callback.answer("Xatolik yuz berdi", show_alert=True)
            raise

    card = _format_lead_card(lead)
    # Use the lead's current kanban stage as the "from_stage" to allow back-navigation
    current_kanban = lead.lead_status if lead.lead_status in KANBAN_STAGES else KANBAN_STAGES[0]
    keyboard = _lead_detail_keyboard(lead_id, current_kanban)
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"✅ Manager #{mgr_id} tayinlandi\n\n{card}",
        reply_markup=keyboard,
    )
    await callback.answer(f"Manager #{mgr_id} tayinlandi")
