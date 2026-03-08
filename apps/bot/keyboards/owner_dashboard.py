"""Inline keyboards for the tenant owner CRM dashboard."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def dashboard_main_keyboard() -> InlineKeyboardMarkup:
    """Main dashboard action buttons."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔥 Hot lidlar", callback_data="owndash:list:hot"),
            InlineKeyboardButton(text="🆕 Yangi lidlar", callback_data="owndash:list:new"),
        ],
        [
            InlineKeyboardButton(text="👤 Tayinlanmagan", callback_data="owndash:list:unassigned"),
            InlineKeyboardButton(text="⚠️ Diqqat kerak", callback_data="owndash:list:attention"),
        ],
        [
            InlineKeyboardButton(text="📋 Barcha lidlar", callback_data="owndash:list:all"),
        ],
        [
            InlineKeyboardButton(text="📊 Analitika", callback_data="ownstat:pick"),
            InlineKeyboardButton(text="🔍 Filtrlar", callback_data="owndash:filters"),
        ],
        [
            InlineKeyboardButton(text="🧠 Bilimlar bazasi", callback_data="kb:main"),
        ],
    ])


def lead_list_keyboard(
    page: int,
    has_next: bool,
    list_type: str,
    lead_ids: list[int] | None = None,
) -> InlineKeyboardMarkup:
    """Pagination + per-lead detail buttons + back button for lead lists."""
    rows: list[list[InlineKeyboardButton]] = []

    # Per-lead "view" buttons (up to 5 per row pair)
    if lead_ids:
        row: list[InlineKeyboardButton] = []
        for lid in lead_ids:
            row.append(InlineKeyboardButton(
                text=f"#{lid}",
                callback_data=f"owndash:lead:{lid}:{list_type}",
            ))
            if len(row) == 3:
                rows.append(row)
                row = []
        if row:
            rows.append(row)

    # Pagination
    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ Oldingi",
            callback_data=f"owndash:page:{list_type}:{page - 1}",
        ))
    if has_next:
        nav_row.append(InlineKeyboardButton(
            text="Keyingi ➡️",
            callback_data=f"owndash:page:{list_type}:{page + 1}",
        ))
    if nav_row:
        rows.append(nav_row)
    rows.append([InlineKeyboardButton(text="🔙 Ortga", callback_data="owndash:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def lead_detail_keyboard(
    lead_id: int,
    list_type: str,
    has_operator: bool = False,
) -> InlineKeyboardMarkup:
    """Buttons for a single lead detail view."""
    rows: list[list[InlineKeyboardButton]] = []
    if has_operator:
        rows.append([
            InlineKeyboardButton(
                text="🔄 Qayta tayinlash",
                callback_data=f"owndash:assign:{lead_id}",
            ),
            InlineKeyboardButton(
                text="❌ Olib tashlash",
                callback_data=f"owndash:unassign:{lead_id}",
            ),
        ])
    else:
        rows.append([
            InlineKeyboardButton(
                text="👔 Operator tayinlash",
                callback_data=f"owndash:assign:{lead_id}",
            ),
        ])
    rows.append([
        InlineKeyboardButton(
            text="🔙 Ortga",
            callback_data=f"owndash:list:{list_type}",
        ),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def operator_picker_keyboard(
    lead_id: int,
    operators: list,
) -> InlineKeyboardMarkup:
    """Inline buttons for selecting an operator to assign."""
    rows: list[list[InlineKeyboardButton]] = []
    for op in operators[:10]:
        name = getattr(op, "first_name", None) or f"ID:{op.id}"
        rows.append([InlineKeyboardButton(
            text=f"👤 {name}",
            callback_data=f"owndash:do_assign:{lead_id}:{op.id}",
        )])
    rows.append([InlineKeyboardButton(
        text="🔙 Bekor qilish",
        callback_data=f"owndash:lead:{lead_id}:all",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def analytics_period_keyboard() -> InlineKeyboardMarkup:
    """Period selector for owner analytics."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="7 kun", callback_data="owndash:analytics:7"),
            InlineKeyboardButton(text="30 kun", callback_data="owndash:analytics:30"),
            InlineKeyboardButton(text="90 kun", callback_data="owndash:analytics:90"),
        ],
        [InlineKeyboardButton(text="🔙 Ortga", callback_data="owndash:back")],
    ])


def analytics_back_keyboard() -> InlineKeyboardMarkup:
    """Back button shown after analytics report."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Boshqa davr", callback_data="owndash:analytics"),
            InlineKeyboardButton(text="🔙 Dashboard", callback_data="owndash:back"),
        ],
    ])


def filter_keyboard() -> InlineKeyboardMarkup:
    """Temperature + date range filter buttons."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔥 Hot", callback_data="owndash:filter:temp:hot"),
            InlineKeyboardButton(text="🌡 Warm", callback_data="owndash:filter:temp:warm"),
            InlineKeyboardButton(text="❄️ Cold", callback_data="owndash:filter:temp:cold"),
        ],
        [
            InlineKeyboardButton(text="Bugun", callback_data="owndash:filter:date:1"),
            InlineKeyboardButton(text="7 kun", callback_data="owndash:filter:date:7"),
            InlineKeyboardButton(text="30 kun", callback_data="owndash:filter:date:30"),
        ],
        [InlineKeyboardButton(text="🔙 Ortga", callback_data="owndash:back")],
    ])


def owner_analytics_window_keyboard() -> InlineKeyboardMarkup:
    """Time window selector for owner analytics."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Bugun", callback_data="ownstat:window:1"),
            InlineKeyboardButton(text="7 kun", callback_data="ownstat:window:7"),
            InlineKeyboardButton(text="30 kun", callback_data="ownstat:window:30"),
        ],
        [InlineKeyboardButton(text="🔙 Dashboard", callback_data="owndash:back")],
    ])


def owner_analytics_detail_keyboard(window: int) -> InlineKeyboardMarkup:
    """Section drilldown + refresh buttons after analytics summary."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📈 Funnel", callback_data=f"ownstat:detail:funnel:{window}"),
            InlineKeyboardButton(text="👔 Operator", callback_data=f"ownstat:detail:operator:{window}"),
        ],
        [
            InlineKeyboardButton(text="🔄 Follow-up", callback_data=f"ownstat:detail:followup:{window}"),
            InlineKeyboardButton(text="🔃 Yangilash", callback_data=f"ownstat:refresh:{window}"),
        ],
        [
            InlineKeyboardButton(text="📊 Boshqa davr", callback_data="ownstat:pick"),
            InlineKeyboardButton(text="🔙 Dashboard", callback_data="owndash:back"),
        ],
    ])


def owner_analytics_section_back_keyboard(window: int) -> InlineKeyboardMarkup:
    """Back to summary from a detail section."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Umumiy", callback_data=f"ownstat:window:{window}"),
            InlineKeyboardButton(text="🔙 Dashboard", callback_data="owndash:back"),
        ],
    ])


# ── Subscription UI ─────────────────────────────────────────────────────


def subscription_main_keyboard() -> InlineKeyboardMarkup:
    """Subscription info screen with upgrade button."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⬆️ Rejani yangilash", callback_data="ownsub:upgrade"),
        ],
        [
            InlineKeyboardButton(text="🔙 Dashboard", callback_data="owndash:back"),
        ],
    ])


def upgrade_plans_keyboard(current_plan: str) -> InlineKeyboardMarkup:
    """Show available plans for upgrade (skip current and lower plans)."""
    from shared.constants.plans import PLAN_CONFIGS

    plan_order = ["free", "basic", "pro", "enterprise"]
    current_idx = plan_order.index(current_plan) if current_plan in plan_order else -1

    rows: list[list[InlineKeyboardButton]] = []
    for plan_name in plan_order:
        if plan_order.index(plan_name) <= current_idx:
            continue  # skip current and lower plans
        config = PLAN_CONFIGS[plan_name]
        price_text = (
            f"{config.monthly_price_uzs:,} so'm/oy"
            if config.monthly_price_uzs > 0
            else "Bepul"
        )
        rows.append([
            InlineKeyboardButton(
                text=f"{config.display_name} — {price_text}",
                callback_data=f"ownsub:plan:{plan_name}",
            ),
        ])

    if not rows:
        rows.append([
            InlineKeyboardButton(
                text="Siz eng yuqori rejada",
                callback_data="ownsub:back",
            ),
        ])

    rows.append([
        InlineKeyboardButton(text="🔙 Ortga", callback_data="ownsub:back"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def plan_detail_keyboard(plan_name: str) -> InlineKeyboardMarkup:
    """Show plan details with confirm + back buttons."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="💳 To'lash",
                callback_data=f"ownsub:confirm:{plan_name}",
            ),
        ],
        [
            InlineKeyboardButton(text="🔙 Rejalar", callback_data="ownsub:upgrade"),
        ],
    ])


def subscription_back_keyboard() -> InlineKeyboardMarkup:
    """Back to subscription info."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Obuna", callback_data="ownsub:back")],
    ])
