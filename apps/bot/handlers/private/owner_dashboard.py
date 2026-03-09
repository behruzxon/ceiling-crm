"""
apps.bot.handlers.private.owner_dashboard
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tenant owner CRM dashboard — view leads, stats, filters, lead detail,
and operator assignment.

All inline callbacks use the ``owndash:`` prefix.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from apps.bot.keyboards.owner_dashboard import (
    analytics_back_keyboard,
    analytics_period_keyboard,
    dashboard_main_keyboard,
    filter_keyboard,
    lead_detail_keyboard,
    lead_list_keyboard,
    operator_picker_keyboard,
    owner_analytics_detail_keyboard,
    owner_analytics_section_back_keyboard,
    owner_analytics_window_keyboard,
    plan_detail_keyboard,
    subscription_back_keyboard,
    subscription_main_keyboard,
    upgrade_plans_keyboard,
)
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_lead_repo, get_tenant_service
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="private:owner_dashboard")

_PAGE_SIZE = 5


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _get_tenant_id(user_id: int) -> int | None:
    """Resolve tenant_id from admin_user_id. Returns None if no tenant."""
    factory = get_session_factory()
    async with factory() as session:
        svc = get_tenant_service(session)
        tenant = await svc.get_by_admin_user(user_id)
    return tenant.id if tenant else None


def _format_lead_card(lead) -> str:
    """Format a single lead as a one-line summary with score."""
    temp_icon = {"hot": "🔥", "warm": "🌡", "cold": "❄️"}.get(
        lead.lead_temperature or "", "❓",
    )
    name = lead.name or "Nomsiz"
    score = lead.score or 0
    date_str = lead.created_at.strftime("%d.%m") if lead.created_at else "—"
    attn = " ⚠️" if getattr(lead, "operator_attention", False) else ""
    return f"#{lead.id} | {name} | {temp_icon} {score}pt | {date_str}{attn}"


def _format_lead_detail(lead) -> str:
    """Format a full lead detail card."""
    temp_icon = {"hot": "🔥", "warm": "🌡", "cold": "❄️"}.get(
        lead.lead_temperature or "", "❓",
    )
    lines = [
        f"📋 Lid #{lead.id}",
        f"👤 {lead.name or 'Nomsiz'}",
        f"📱 {lead.phone}",
        f"📍 {lead.district}",
        f"{temp_icon} {lead.lead_temperature or '—'} | {lead.score or 0}pt",
    ]
    if lead.room_area:
        lines.append(f"📐 {lead.room_area}m²")
    if lead.urgency_signal:
        lines.append(
            f"Signallar: urgency={lead.urgency_signal} "
            f"budget={lead.budget_signal} "
            f"engagement={lead.engagement_signal}"
        )
    if lead.scoring_reasons:
        lines.append(f"Sabablar: {', '.join(lead.scoring_reasons[:3])}")
    if lead.operator_attention:
        lines.append("⚠️ Operator diqqati kerak")

    # Assignment info
    if lead.assigned_manager_id:
        lines.append(f"👔 Operator: #{lead.assigned_manager_id}")
        if lead.assigned_at:
            lines.append(f"📅 Tayinlangan: {lead.assigned_at.strftime('%d.%m %H:%M')}")
        if lead.assignment_reason:
            lines.append(f"📝 Sabab: {lead.assignment_reason}")
    else:
        lines.append("👔 Tayinlanmagan")

    date_str = lead.created_at.strftime("%d.%m.%Y %H:%M") if lead.created_at else "—"
    lines.append(f"📅 Yaratildi: {date_str}")
    return "\n".join(lines)


async def _build_dashboard_text(tenant_id: int) -> str:
    """Build the main dashboard summary text for a tenant."""
    factory = get_session_factory()
    async with factory() as session:
        repo = get_lead_repo(session, tenant_id=tenant_id)
        stage_counts = await repo.get_counts_by_stage(tenant_id=tenant_id)
        temp_counts = await repo.get_temperature_counts(tenant_id=tenant_id)
        attention_leads = await repo.get_attention_leads(tenant_id=tenant_id, limit=100)

    total = sum(stage_counts.values())
    attn_count = len(attention_leads)
    attn_line = f"\n⚠️ Operator kerak: {attn_count}" if attn_count else ""
    return (
        "📊 CRM Dashboard\n"
        f"Jami lidlar: {total}\n"
        "─────────────────────────\n"
        f"Bosqichlar: Yangi: {stage_counts.get('new', 0)} | "
        f"Hot: {stage_counts.get('hot', 0)} | "
        f"O'lchov: {stage_counts.get('measurement', 0)} | "
        f"Yutilgan: {stage_counts.get('won', 0)} | "
        f"Yo'qotilgan: {stage_counts.get('lost', 0)}\n"
        f"Harorat: 🔥 {temp_counts.get('hot', 0)} | "
        f"🌡 {temp_counts.get('warm', 0)} | "
        f"❄️ {temp_counts.get('cold', 0)}"
        f"{attn_line}"
    )


async def _show_lead_list(
    callback: CallbackQuery,
    leads: list,
    page: int,
    list_type: str,
    title: str,
) -> None:
    """Render a paginated lead list with per-lead detail buttons."""
    has_next = len(leads) > _PAGE_SIZE
    display = leads[:_PAGE_SIZE]

    if not display:
        text = f"{title}\n\nLidlar topilmadi."
        lead_ids = None
    else:
        cards = "\n".join(_format_lead_card(l) for l in display)
        text = f"{title}\n\n{cards}"
        lead_ids = [l.id for l in display]

    await callback.message.answer(
        text,
        reply_markup=lead_list_keyboard(page, has_next, list_type, lead_ids),
    )


# ── Entry point ──────────────────────────────────────────────────────────────

@router.message(Command("my_leads"), F.chat.type == "private")
async def cmd_my_leads(message: Message, **data) -> None:
    """Show CRM dashboard for tenant owner."""
    user_id = message.from_user.id
    tenant_id = await _get_tenant_id(user_id)
    if not tenant_id:
        await message.answer("Biznesingiz topilmadi. Avval /create_business buyrug'ini yuboring.")
        return

    text = await _build_dashboard_text(tenant_id)
    await message.answer(text, reply_markup=dashboard_main_keyboard())


@router.callback_query(F.data == "onb:edit:leads")
async def handle_dashboard_from_mybusiness(callback: CallbackQuery, **data) -> None:
    """Open dashboard from /my_business inline button."""
    await callback.answer()
    user_id = callback.from_user.id
    tenant_id = await _get_tenant_id(user_id)
    if not tenant_id:
        await callback.message.answer("Biznesingiz topilmadi.")
        return

    text = await _build_dashboard_text(tenant_id)
    await callback.message.answer(text, reply_markup=dashboard_main_keyboard())


# ── Back to dashboard ────────────────────────────────────────────────────────

@router.callback_query(F.data == "owndash:back")
async def handle_back(callback: CallbackQuery, **data) -> None:
    await callback.answer()
    user_id = callback.from_user.id
    tenant_id = await _get_tenant_id(user_id)
    if not tenant_id:
        await callback.message.answer("Biznesingiz topilmadi.")
        return

    text = await _build_dashboard_text(tenant_id)
    await callback.message.answer(text, reply_markup=dashboard_main_keyboard())


# ── Lead detail view ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("owndash:lead:"))
async def handle_lead_detail(callback: CallbackQuery, **data) -> None:
    """Show full lead detail with assignment buttons."""
    await callback.answer()
    # Format: owndash:lead:{lead_id}:{list_type}
    parts = callback.data.split(":")
    if len(parts) < 4:
        return
    lead_id = int(parts[2])
    list_type = parts[3]

    tenant_id = await _get_tenant_id(callback.from_user.id)
    if not tenant_id:
        return

    factory = get_session_factory()
    async with factory() as session:
        repo = get_lead_repo(session, tenant_id)
        lead = await repo.get_by_id(lead_id)

    if not lead:
        await callback.message.answer("Lid topilmadi.")
        return

    text = _format_lead_detail(lead)
    await callback.message.answer(
        text,
        reply_markup=lead_detail_keyboard(
            lead_id, list_type, has_operator=bool(lead.assigned_manager_id),
        ),
    )


# ── Operator assignment ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("owndash:assign:"))
async def handle_assign_start(callback: CallbackQuery, **data) -> None:
    """Show operator picker for assignment."""
    await callback.answer()
    lead_id = int(callback.data.split(":")[2])

    tenant_id = await _get_tenant_id(callback.from_user.id)
    if not tenant_id:
        return

    from core.services.operator_assignment_service import OperatorAssignmentService
    svc = OperatorAssignmentService()
    operators = await svc.get_available_operators(tenant_id)

    if not operators:
        await callback.message.answer(
            "Operatorlar topilmadi. Avval manager qo'shing.",
        )
        return

    await callback.message.answer(
        f"Lid #{lead_id} uchun operator tanlang:",
        reply_markup=operator_picker_keyboard(lead_id, operators),
    )


@router.callback_query(F.data.startswith("owndash:do_assign:"))
async def handle_do_assign(callback: CallbackQuery, **data) -> None:
    """Execute operator assignment."""
    await callback.answer()
    # Format: owndash:do_assign:{lead_id}:{operator_id}
    parts = callback.data.split(":")
    if len(parts) < 4:
        return
    lead_id = int(parts[2])
    operator_id = int(parts[3])

    tenant_id = await _get_tenant_id(callback.from_user.id)
    if not tenant_id:
        return

    from core.services.operator_assignment_service import OperatorAssignmentService
    svc = OperatorAssignmentService()
    result = await svc.assign_lead(
        lead_id=lead_id,
        operator_id=operator_id,
        reason="owner_manual",
        actor_id=callback.from_user.id,
        tenant_id=tenant_id,
    )

    if result:
        await callback.message.answer(
            f"✅ Lid #{lead_id} operatorga tayinlandi (ID: {operator_id})",
        )
    else:
        await callback.message.answer("❌ Tayinlash xatolik yuz berdi.")


@router.callback_query(F.data.startswith("owndash:unassign:"))
async def handle_unassign(callback: CallbackQuery, **data) -> None:
    """Remove operator assignment."""
    await callback.answer()
    lead_id = int(callback.data.split(":")[2])

    tenant_id = await _get_tenant_id(callback.from_user.id)
    if not tenant_id:
        return

    from core.services.operator_assignment_service import OperatorAssignmentService
    svc = OperatorAssignmentService()
    result = await svc.unassign_lead(
        lead_id=lead_id,
        actor_id=callback.from_user.id,
        tenant_id=tenant_id,
    )

    if result:
        await callback.message.answer(f"✅ Lid #{lead_id} dan operator olib tashlandi.")
    else:
        await callback.message.answer("❌ Xatolik yuz berdi.")


# ── Operator "my leads" command ──────────────────────────────────────────────

@router.message(Command("my_assigned"), F.chat.type == "private")
async def cmd_my_assigned(message: Message, **data) -> None:
    """Show leads assigned to the current user (for managers)."""
    user_id = message.from_user.id
    db_user = data.get("db_user")
    if not db_user:
        return

    tenant_id = getattr(db_user, "tenant_id", None)
    if not tenant_id:
        await message.answer("Tenant topilmadi.")
        return

    from core.services.operator_assignment_service import OperatorAssignmentService
    svc = OperatorAssignmentService()
    leads = await svc.get_assigned_leads(user_id, tenant_id=tenant_id, limit=20)

    if not leads:
        await message.answer("Sizga tayinlangan lidlar yo'q.")
        return

    cards = "\n".join(_format_lead_card(l) for l in leads)
    lead_ids = [l.id for l in leads[:_PAGE_SIZE]]
    await message.answer(
        f"📋 Mening lidlarim ({len(leads)} ta)\n\n{cards}",
        reply_markup=lead_list_keyboard(0, False, "my", lead_ids),
    )


# ── List views ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "owndash:list:hot")
async def handle_list_hot(callback: CallbackQuery, **data) -> None:
    await callback.answer()
    tenant_id = await _get_tenant_id(callback.from_user.id)
    if not tenant_id:
        return

    factory = get_session_factory()
    async with factory() as session:
        repo = get_lead_repo(session, tenant_id=tenant_id)
        leads = await repo.search(
            lead_temperature="hot", tenant_id=tenant_id,
            limit=_PAGE_SIZE + 1, offset=0,
        )
    await _show_lead_list(callback, leads, 0, "hot", "🔥 Hot lidlar")


@router.callback_query(F.data == "owndash:list:new")
async def handle_list_new(callback: CallbackQuery, **data) -> None:
    await callback.answer()
    tenant_id = await _get_tenant_id(callback.from_user.id)
    if not tenant_id:
        return

    factory = get_session_factory()
    async with factory() as session:
        repo = get_lead_repo(session, tenant_id=tenant_id)
        leads = await repo.get_leads_by_kanban_stage(
            "new", limit=_PAGE_SIZE + 1, offset=0, tenant_id=tenant_id,
        )
    await _show_lead_list(callback, leads, 0, "new", "🆕 Yangi lidlar")


@router.callback_query(F.data == "owndash:list:unassigned")
async def handle_list_unassigned(callback: CallbackQuery, **data) -> None:
    await callback.answer()
    tenant_id = await _get_tenant_id(callback.from_user.id)
    if not tenant_id:
        return

    factory = get_session_factory()
    async with factory() as session:
        repo = get_lead_repo(session, tenant_id=tenant_id)
        leads = await repo.get_unassigned_leads(
            tenant_id=tenant_id, limit=_PAGE_SIZE + 1,
        )
    await _show_lead_list(callback, leads, 0, "unassigned", "👤 Tayinlanmagan lidlar")


@router.callback_query(F.data == "owndash:list:attention")
async def handle_list_attention(callback: CallbackQuery, **data) -> None:
    await callback.answer()
    tenant_id = await _get_tenant_id(callback.from_user.id)
    if not tenant_id:
        return

    factory = get_session_factory()
    async with factory() as session:
        repo = get_lead_repo(session, tenant_id=tenant_id)
        leads = await repo.get_attention_leads(
            tenant_id=tenant_id, limit=_PAGE_SIZE + 1,
        )
    await _show_lead_list(callback, leads, 0, "attention", "⚠️ Operator diqqati kerak")


@router.callback_query(F.data == "owndash:list:all")
async def handle_list_all(callback: CallbackQuery, **data) -> None:
    await callback.answer()
    tenant_id = await _get_tenant_id(callback.from_user.id)
    if not tenant_id:
        return

    factory = get_session_factory()
    async with factory() as session:
        repo = get_lead_repo(session, tenant_id=tenant_id)
        leads = await repo.get_recent_leads(
            tenant_id=tenant_id, limit=_PAGE_SIZE + 1,
        )
    await _show_lead_list(callback, leads, 0, "all", "📋 Barcha lidlar")


# ── Pagination ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("owndash:page:"))
async def handle_pagination(callback: CallbackQuery, **data) -> None:
    await callback.answer()
    # Format: owndash:page:{list_type}:{page}
    parts = callback.data.split(":")
    if len(parts) < 4:
        return
    list_type = parts[2]
    page = int(parts[3])

    tenant_id = await _get_tenant_id(callback.from_user.id)
    if not tenant_id:
        return

    offset = page * _PAGE_SIZE
    factory = get_session_factory()
    async with factory() as session:
        repo = get_lead_repo(session, tenant_id=tenant_id)

        if list_type == "hot":
            leads = await repo.search(
                lead_temperature="hot", tenant_id=tenant_id,
                limit=_PAGE_SIZE + 1, offset=offset,
            )
            title = "🔥 Hot lidlar"
        elif list_type == "new":
            leads = await repo.get_leads_by_kanban_stage(
                "new", limit=_PAGE_SIZE + 1, offset=offset, tenant_id=tenant_id,
            )
            title = "🆕 Yangi lidlar"
        elif list_type == "unassigned":
            leads = await repo.get_unassigned_leads(
                tenant_id=tenant_id, limit=_PAGE_SIZE + 1,
            )
            title = "👤 Tayinlanmagan lidlar"
        elif list_type == "attention":
            leads = await repo.get_attention_leads(
                tenant_id=tenant_id, limit=_PAGE_SIZE + 1,
            )
            title = "⚠️ Operator diqqati kerak"
        elif list_type == "all":
            leads = await repo.get_recent_leads(
                tenant_id=tenant_id, limit=_PAGE_SIZE + 1,
            )
            title = "📋 Barcha lidlar"
        elif list_type.startswith("temp_"):
            temp = list_type.replace("temp_", "")
            leads = await repo.search(
                lead_temperature=temp, tenant_id=tenant_id,
                limit=_PAGE_SIZE + 1, offset=offset,
            )
            temp_icon = {"hot": "🔥", "warm": "🌡", "cold": "❄️"}.get(temp, "")
            title = f"{temp_icon} {temp.capitalize()} lidlar"
        elif list_type.startswith("date_"):
            days = int(list_type.replace("date_", ""))
            since = datetime.now(timezone.utc) - timedelta(days=days)
            leads = await repo.search(
                created_after=since, tenant_id=tenant_id,
                limit=_PAGE_SIZE + 1, offset=offset,
            )
            title = f"📅 Oxirgi {days} kun"
        else:
            return

    await _show_lead_list(callback, leads, page, list_type, title)


# ── Filters ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "owndash:filters")
async def handle_filters(callback: CallbackQuery, **data) -> None:
    await callback.answer()
    await callback.message.answer(
        "Filtr tanlang:",
        reply_markup=filter_keyboard(),
    )


@router.callback_query(F.data.startswith("owndash:filter:temp:"))
async def handle_filter_temp(callback: CallbackQuery, **data) -> None:
    await callback.answer()
    temp = callback.data.replace("owndash:filter:temp:", "")
    tenant_id = await _get_tenant_id(callback.from_user.id)
    if not tenant_id:
        return

    factory = get_session_factory()
    async with factory() as session:
        repo = get_lead_repo(session, tenant_id=tenant_id)
        leads = await repo.search(
            lead_temperature=temp, tenant_id=tenant_id,
            limit=_PAGE_SIZE + 1, offset=0,
        )

    temp_icon = {"hot": "🔥", "warm": "🌡", "cold": "❄️"}.get(temp, "")
    await _show_lead_list(callback, leads, 0, f"temp_{temp}", f"{temp_icon} {temp.capitalize()} lidlar")


@router.callback_query(F.data.startswith("owndash:filter:date:"))
async def handle_filter_date(callback: CallbackQuery, **data) -> None:
    await callback.answer()
    days = int(callback.data.replace("owndash:filter:date:", ""))
    tenant_id = await _get_tenant_id(callback.from_user.id)
    if not tenant_id:
        return

    since = datetime.now(timezone.utc) - timedelta(days=days)
    factory = get_session_factory()
    async with factory() as session:
        repo = get_lead_repo(session, tenant_id=tenant_id)
        leads = await repo.search(
            created_after=since, tenant_id=tenant_id,
            limit=_PAGE_SIZE + 1, offset=0,
        )

    await _show_lead_list(callback, leads, 0, f"date_{days}", f"📅 Oxirgi {days} kun")


# ── Analytics ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "owndash:analytics")
async def handle_analytics_menu(callback: CallbackQuery, **data) -> None:
    """Show period selector for analytics."""
    await callback.answer()
    await callback.message.answer(
        "📊 Tahlil davri tanlang:",
        reply_markup=analytics_period_keyboard(),
    )


@router.callback_query(F.data.startswith("owndash:analytics:"))
async def handle_analytics_report(callback: CallbackQuery, **data) -> None:
    """Generate and display the sales analytics report for the selected period."""
    await callback.answer()

    tenant_id = await _get_tenant_id(callback.from_user.id)
    if not tenant_id:
        await callback.message.answer("Biznesingiz topilmadi.")
        return

    days = int(callback.data.split(":")[-1])
    await callback.message.answer(f"📊 Tahlil qilinmoqda ({days} kun)...")

    try:
        factory = get_session_factory()
        async with factory() as session:
            repo = get_lead_repo(session, tenant_id=tenant_id)
            leads = await repo.get_leads_for_analytics(days=days, limit=500)

        if not leads:
            await callback.message.answer(
                f"📊 Oxirgi {days} kunda lidlar topilmadi.",
                reply_markup=analytics_back_keyboard(),
            )
            return

        from apps.bot.handlers.admin.analytics import _build_leads_data, _format_report
        from core.services.sales_analytics_service import build_sales_analytics

        leads_data = await _build_leads_data(leads)
        report = build_sales_analytics(leads_data)
        text = _format_report(report, days)

        if len(text) <= 4096:
            await callback.message.answer(text, reply_markup=analytics_back_keyboard())
        else:
            parts = text.split("\n\n")
            chunk = ""
            for part in parts:
                if len(chunk) + len(part) + 2 > 4000:
                    await callback.message.answer(chunk)
                    chunk = part
                else:
                    chunk = f"{chunk}\n\n{part}" if chunk else part
            if chunk:
                await callback.message.answer(
                    chunk, reply_markup=analytics_back_keyboard(),
                )

    except Exception:
        log.exception("owner_analytics_failed", tenant_id=tenant_id)
        await callback.message.answer(
            "❌ Tahlil xatolik yuz berdi.",
            reply_markup=analytics_back_keyboard(),
        )


# ── Owner Analytics (ownstat:*) ─────────────────────────────────────────────


@router.message(Command("analytics"), F.chat.type == "private")
async def cmd_analytics(message: Message, **data) -> None:
    """Owner analytics entry point — show time window picker."""
    tenant_id = await _get_tenant_id(message.from_user.id)
    if not tenant_id:
        await message.answer("Biznesingiz topilmadi. Avval /create_business buyrug'ini yuboring.")
        return

    await message.answer(
        "📊 Analitika — davr tanlang:",
        reply_markup=owner_analytics_window_keyboard(),
    )


@router.callback_query(F.data == "ownstat:pick")
async def handle_analytics_pick(callback: CallbackQuery, **data) -> None:
    """Show time window picker for owner analytics."""
    await callback.answer()
    tenant_id = await _get_tenant_id(callback.from_user.id)
    if not tenant_id:
        await callback.message.answer("Biznesingiz topilmadi.")
        return

    await callback.message.answer(
        "📊 Analitika — davr tanlang:",
        reply_markup=owner_analytics_window_keyboard(),
    )


@router.callback_query(F.data.startswith("ownstat:window:"))
async def handle_analytics_window(callback: CallbackQuery, **data) -> None:
    """Generate and display owner analytics summary for selected window."""
    await callback.answer()
    window = int(callback.data.split(":")[-1])

    tenant_id = await _get_tenant_id(callback.from_user.id)
    if not tenant_id:
        await callback.message.answer("Biznesingiz topilmadi.")
        return

    try:
        from core.services.owner_analytics_service import (
            format_analytics_summary,
            get_owner_analytics,
        )

        analytics = await get_owner_analytics(tenant_id, window_days=window)
        text = format_analytics_summary(analytics)
        await callback.message.answer(
            text, reply_markup=owner_analytics_detail_keyboard(window),
        )
        log.info(
            "owner_analytics_shown",
            tenant_id=tenant_id,
            window=window,
            user_id=callback.from_user.id,
        )
    except Exception:
        log.exception("owner_analytics_failed", tenant_id=tenant_id, window=window)
        await callback.message.answer("❌ Analitika xatolik yuz berdi.")


@router.callback_query(F.data.startswith("ownstat:detail:"))
async def handle_analytics_detail(callback: CallbackQuery, **data) -> None:
    """Show a specific analytics section (funnel, operator, followup)."""
    await callback.answer()
    # Format: ownstat:detail:{section}:{window}
    parts = callback.data.split(":")
    if len(parts) < 4:
        return
    section = parts[2]
    window = int(parts[3])

    tenant_id = await _get_tenant_id(callback.from_user.id)
    if not tenant_id:
        return

    try:
        from core.services.owner_analytics_service import (
            format_followup_detail,
            format_funnel_detail,
            format_operator_detail,
            get_owner_analytics,
        )

        analytics = await get_owner_analytics(tenant_id, window_days=window)

        formatters = {
            "funnel": format_funnel_detail,
            "operator": format_operator_detail,
            "followup": format_followup_detail,
        }
        formatter = formatters.get(section)
        if not formatter:
            await callback.message.answer("Noto'g'ri bo'lim.")
            return

        text = formatter(analytics)
        await callback.message.answer(
            text, reply_markup=owner_analytics_section_back_keyboard(window),
        )
    except Exception:
        log.exception("owner_analytics_detail_failed", section=section)
        await callback.message.answer("❌ Xatolik yuz berdi.")


@router.callback_query(F.data.startswith("ownstat:refresh:"))
async def handle_analytics_refresh(callback: CallbackQuery, **data) -> None:
    """Invalidate cache and regenerate analytics."""
    await callback.answer("Yangilanmoqda...")
    window = int(callback.data.split(":")[-1])

    tenant_id = await _get_tenant_id(callback.from_user.id)
    if not tenant_id:
        return

    try:
        # Invalidate cache first
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys

        await get_redis().delete(CacheKeys.owner_analytics(tenant_id, window))

        from core.services.owner_analytics_service import (
            format_analytics_summary,
            get_owner_analytics,
        )

        analytics = await get_owner_analytics(tenant_id, window_days=window)
        text = format_analytics_summary(analytics)
        await callback.message.answer(
            text, reply_markup=owner_analytics_detail_keyboard(window),
        )
        log.info("owner_analytics_refreshed", tenant_id=tenant_id, window=window)
    except Exception:
        log.exception("owner_analytics_refresh_failed", tenant_id=tenant_id)
        await callback.message.answer("❌ Yangilash xatolik yuz berdi.")


# ── Subscription Management (ownsub:*) ──────────────────────────────────


async def _get_tenant(user_id: int):
    """Fetch the full tenant record for a given admin_user_id."""
    factory = get_session_factory()
    async with factory() as session:
        svc = get_tenant_service(session)
        return await svc.get_by_admin_user(user_id)


def _format_subscription_info(tenant) -> str:
    """Format subscription status for display."""
    from shared.constants.enums import BillingStatus
    from shared.constants.plans import get_plan_config
    from core.services.billing_service import BillingService

    plan = get_plan_config(tenant.billing_plan)
    status = tenant.billing_status or "unknown"
    status_icon = {
        "trial": "🟡 Sinov",
        "active": "🟢 Faol",
        "expired": "🔴 Tugagan",
        "suspended": "⛔ To'xtatilgan",
    }.get(status, status)

    expiry = BillingService.get_expiry_date(tenant)
    days_left = ""
    if expiry:
        from datetime import datetime, timezone
        delta = (expiry - datetime.now(timezone.utc)).days
        days_left = f" ({delta} kun qoldi)" if delta > 0 else " (tugagan)"

    lines = [
        "📋 Obuna ma'lumotlari",
        "",
        f"Reja: {plan.display_name}",
        f"Holat: {status_icon}{days_left}",
        "",
        "📊 Reja limitleri:",
        f"  Lidlar: {plan.leads_per_month}/oy" if plan.leads_per_month > 0 else "  Lidlar: Cheksiz",
        f"  AI xabarlar: {plan.ai_messages_per_day}/kun" if plan.ai_messages_per_day > 0 else "  AI xabarlar: Cheksiz",
        f"  Bilimlar bazasi: {'✅' if plan.knowledge_base_enabled else '❌'}",
        f"  Operator tayinlash: {'✅' if plan.operator_assignment_enabled else '❌'}",
        f"  Analitika: {'✅' if plan.analytics_enabled else '❌'}",
    ]

    if plan.monthly_price_uzs > 0:
        lines.append(f"\n💰 Narx: {plan.monthly_price_uzs:,} so'm/oy")

    return "\n".join(lines)


async def _format_usage_line(tenant_id: int, plan_name: str) -> str:
    """Format current usage stats."""
    try:
        from core.services.usage_service import get_usage_summary

        usage = await get_usage_summary(tenant_id, plan_name)
        leads_line = (
            f"{usage.leads_used}/{usage.leads_limit}"
            if usage.leads_limit > 0
            else f"{usage.leads_used}/∞"
        )
        ai_line = (
            f"{usage.ai_messages_used}/{usage.ai_messages_limit}"
            if usage.ai_messages_limit > 0
            else f"{usage.ai_messages_used}/∞"
        )
        return (
            "\n📈 Joriy foydalanish:\n"
            f"  Lidlar bu oy: {leads_line}\n"
            f"  AI xabarlar bugun: {ai_line}"
        )
    except Exception:
        return ""


@router.message(Command("subscription"), F.chat.type == "private")
async def cmd_subscription(message: Message, **data) -> None:
    """Show subscription info for the tenant owner."""
    tenant = await _get_tenant(message.from_user.id)
    if not tenant:
        await message.answer(
            "Biznesingiz topilmadi. Avval /create_business buyrug'ini yuboring.",
        )
        return

    text = _format_subscription_info(tenant)
    usage = await _format_usage_line(tenant.id, tenant.billing_plan)
    await message.answer(
        text + usage,
        reply_markup=subscription_main_keyboard(),
    )


@router.callback_query(F.data == "ownsub:back")
async def handle_sub_back(callback: CallbackQuery, **data) -> None:
    """Return to subscription info."""
    await callback.answer()
    tenant = await _get_tenant(callback.from_user.id)
    if not tenant:
        await callback.message.answer("Biznesingiz topilmadi.")
        return

    text = _format_subscription_info(tenant)
    usage = await _format_usage_line(tenant.id, tenant.billing_plan)
    await callback.message.answer(
        text + usage,
        reply_markup=subscription_main_keyboard(),
    )


@router.callback_query(F.data == "ownsub:upgrade")
async def handle_upgrade_menu(callback: CallbackQuery, **data) -> None:
    """Show available plans for upgrade."""
    await callback.answer()
    tenant = await _get_tenant(callback.from_user.id)
    if not tenant:
        return

    await callback.message.answer(
        "⬆️ Rejani tanlang:",
        reply_markup=upgrade_plans_keyboard(tenant.billing_plan or "free"),
    )


@router.callback_query(F.data.startswith("ownsub:plan:"))
async def handle_plan_detail(callback: CallbackQuery, **data) -> None:
    """Show detailed info about a specific plan."""
    await callback.answer()
    plan_name = callback.data.split(":")[-1]

    from shared.constants.plans import get_plan_config
    config = get_plan_config(plan_name)

    leads_text = f"{config.leads_per_month:,}/oy" if config.leads_per_month > 0 else "Cheksiz"
    ai_text = f"{config.ai_messages_per_day:,}/kun" if config.ai_messages_per_day > 0 else "Cheksiz"

    text = (
        f"📦 {config.display_name} reja\n\n"
        f"💰 Narx: {config.monthly_price_uzs:,} so'm/oy\n\n"
        f"Imkoniyatlar:\n"
        f"  Lidlar: {leads_text}\n"
        f"  AI xabarlar: {ai_text}\n"
        f"  Bilimlar bazasi: {'✅' if config.knowledge_base_enabled else '❌'}\n"
        f"  Operator tayinlash: {'✅' if config.operator_assignment_enabled else '❌'}\n"
        f"  Analitika: {'✅' if config.analytics_enabled else '❌'}\n"
    )

    await callback.message.answer(text, reply_markup=plan_detail_keyboard(plan_name))


@router.callback_query(F.data.startswith("ownsub:confirm:"))
async def handle_plan_confirm(callback: CallbackQuery, **data) -> None:
    """Confirm plan upgrade (payment placeholder)."""
    await callback.answer()
    plan_name = callback.data.split(":")[-1]

    tenant = await _get_tenant(callback.from_user.id)
    if not tenant:
        return

    from shared.constants.plans import get_plan_config
    config = get_plan_config(plan_name)

    # Payment placeholder — in the future this will create an invoice
    # via Click.uz or Payme.uz and return a payment URL
    await callback.message.answer(
        f"💳 {config.display_name} rejasiga o'tish\n\n"
        f"Narx: {config.monthly_price_uzs:,} so'm/oy\n\n"
        f"To'lov tizimi tez orada ulanadi.\n"
        f"Hozircha administrator bilan bog'laning: @admin_support",
        reply_markup=subscription_back_keyboard(),
    )
    log.info(
        "upgrade_requested",
        tenant_id=tenant.id,
        plan=plan_name,
        price=config.monthly_price_uzs,
    )
