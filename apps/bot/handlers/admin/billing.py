"""
apps.bot.handlers.admin.billing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
SUPERADMIN-only tenant billing management.

Commands:
  /tenants                   -- list all tenants with billing status
  /show_tenant {id}          -- detailed tenant view with billing info

Callbacks (billing: prefix):
  billing:detail:{id}        -- detailed billing view
  billing:extend:{id}        -- extend subscription by 30 days
  billing:activate:{id}      -- reactivate expired/suspended tenant
  billing:suspend:{id}       -- suspend a tenant
  billing:back               -- return to list view

RBAC: SUPERADMIN only
"""
from __future__ import annotations

from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from apps.bot.filters.role import RoleFilter
from core.services.billing_service import BillingService
from core.services.bot_registry import BotStatus, get_bot_registry
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_billing_service
from shared.constants.enums import BillingStatus, UserRole
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="admin:billing")

_SUPERADMIN = (UserRole.SUPERADMIN,)

_BILLING_ICONS = {
    BillingStatus.TRIAL.value:     "[TRIAL]",
    BillingStatus.ACTIVE.value:    "[ACTIVE]",
    BillingStatus.EXPIRED.value:   "[EXPIRED]",
    BillingStatus.SUSPENDED.value: "[SUSPENDED]",
}


# ── Formatting ───────────────────────────────────────────────────────────


def _format_date(dt: datetime | None) -> str:
    if not dt:
        return "--"
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def _format_date_short(dt: datetime | None) -> str:
    if not dt:
        return "--"
    return dt.strftime("%Y-%m-%d")


def _days_left(dt: datetime | None) -> str:
    if not dt:
        return ""
    delta = (dt - datetime.now(timezone.utc)).days
    if delta < 0:
        return f" ({abs(delta)}d ago)"
    if delta == 0:
        return " (today)"
    return f" ({delta}d left)"


def _format_tenant_list(tenants: list) -> str:
    if not tenants:
        return "Tenant Billing\n=============================\nNo tenants found."

    lines = [f"Tenant Billing ({len(tenants)} tenants)", "============================="]

    for i, t in enumerate(tenants, 1):
        billing = getattr(t, "billing_status", "trial")
        icon = _BILLING_ICONS.get(billing, "[?]")
        lines.append(f"{i}. {t.name} {icon} T:{t.id}")

        expiry = BillingService.get_expiry_date(t)
        if billing == BillingStatus.TRIAL.value and t.trial_ends_at:
            lines.append(f"   Trial ends: {_format_date_short(t.trial_ends_at)}{_days_left(t.trial_ends_at)}")
        elif billing == BillingStatus.ACTIVE.value and t.subscription_expires_at:
            lines.append(f"   Expires: {_format_date_short(t.subscription_expires_at)}{_days_left(t.subscription_expires_at)}")
        elif billing == BillingStatus.EXPIRED.value:
            exp_date = t.subscription_expires_at or t.trial_ends_at
            lines.append(f"   Expired: {_format_date_short(exp_date)}")
        elif billing == BillingStatus.SUSPENDED.value:
            lines.append("   Manually suspended")

    lines.append("=============================")
    return "\n".join(lines)


def _format_tenant_detail(tenant: object) -> str:
    t = tenant
    billing = getattr(t, "billing_status", "trial")

    # Get bot status from registry
    registry = get_bot_registry()
    bot_state = registry.get_bot_state(t.id)
    bot_status = bot_state.status.value if bot_state else "unknown"

    monthly_price = getattr(t, "monthly_price_uzs", 0)
    billing_plan = getattr(t, "billing_plan", "basic")
    lines = [
        f"Tenant: {t.name}",
        "=============================",
        f"ID:             {t.id}",
        f"Slug:           {t.slug}",
        f"Business type:  {getattr(t, 'business_type', '--')}",
        f"Billing:        {billing}",
        f"Plan:           {billing_plan}",
        f"Monthly price:  {monthly_price:,} UZS",
        f"Trial ends:     {_format_date(getattr(t, 'trial_ends_at', None))}",
        f"Subscription:   {_format_date(getattr(t, 'subscription_expires_at', None))}",
        f"Bot status:     {bot_status}",
        f"Admin user:     {t.admin_user_id or '--'}",
        f"Active:         {t.is_active}",
        f"Created:        {_format_date_short(t.created_at)}",
        "=============================",
    ]
    return "\n".join(lines)


# ── Keyboards ────────────────────────────────────────────────────────────


def _list_keyboard(tenants: list) -> InlineKeyboardMarkup:
    buttons = []
    for t in tenants:
        billing = getattr(t, "billing_status", "trial")
        icon = _BILLING_ICONS.get(billing, "")
        buttons.append([InlineKeyboardButton(
            text=f"{t.name} {icon}",
            callback_data=f"billing:detail:{t.id}",
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _detail_keyboard(tenant_id: int, billing_status: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    # Row 1: lifecycle actions
    row1: list[InlineKeyboardButton] = []
    if billing_status in (BillingStatus.TRIAL.value, BillingStatus.ACTIVE.value):
        row1.append(InlineKeyboardButton(
            text="Extend 30d",
            callback_data=f"billing:extend:{tenant_id}",
        ))
        row1.append(InlineKeyboardButton(
            text="Suspend",
            callback_data=f"billing:suspend:{tenant_id}",
        ))
    elif billing_status in (BillingStatus.EXPIRED.value, BillingStatus.SUSPENDED.value):
        row1.append(InlineKeyboardButton(
            text="Activate",
            callback_data=f"billing:activate:{tenant_id}",
        ))
    if row1:
        rows.append(row1)

    # Row 2: payment actions
    rows.append([
        InlineKeyboardButton(text="Pay", callback_data=f"billing:pay:{tenant_id}"),
        InlineKeyboardButton(text="History", callback_data=f"billing:payments:{tenant_id}"),
    ])

    # Row 3: back
    rows.append([InlineKeyboardButton(text="<< Back", callback_data="billing:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── Handlers ─────────────────────────────────────────────────────────────


@router.message(Command("tenants"), RoleFilter(*_SUPERADMIN))
async def cmd_tenants(message: Message, **data: object) -> None:
    """List all tenants with billing status."""
    factory = get_session_factory()
    async with factory() as session:
        svc = get_billing_service(session)
        tenants = await svc.list_all_tenants()

    text = _format_tenant_list(tenants)
    await message.answer(text, reply_markup=_list_keyboard(tenants))


@router.message(Command("show_tenant"), RoleFilter(*_SUPERADMIN))
async def cmd_show_tenant(message: Message, **data: object) -> None:
    """Show detailed tenant info. Usage: /show_tenant {id}"""
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Usage: /show_tenant {tenant_id}")
        return

    try:
        tenant_id = int(parts[1])
    except ValueError:
        await message.answer("Invalid tenant ID. Usage: /show_tenant {tenant_id}")
        return

    from infrastructure.database.models.tenant import TenantModel

    factory = get_session_factory()
    async with factory() as session:
        tenant = await session.get(TenantModel, tenant_id)

    if tenant is None:
        await message.answer(f"Tenant {tenant_id} not found.")
        return

    billing = getattr(tenant, "billing_status", "trial")
    text = _format_tenant_detail(tenant)
    await message.answer(text, reply_markup=_detail_keyboard(tenant_id, billing))


@router.callback_query(F.data == "billing:back", RoleFilter(*_SUPERADMIN))
async def cb_back(callback: CallbackQuery, **data: object) -> None:
    """Return to tenant list view."""
    await callback.answer()
    factory = get_session_factory()
    async with factory() as session:
        svc = get_billing_service(session)
        tenants = await svc.list_all_tenants()

    text = _format_tenant_list(tenants)
    await callback.message.edit_text(text, reply_markup=_list_keyboard(tenants))  # type: ignore[union-attr]


@router.callback_query(F.data.startswith("billing:detail:"), RoleFilter(*_SUPERADMIN))
async def cb_detail(callback: CallbackQuery, **data: object) -> None:
    """Show detailed billing view for one tenant."""
    await callback.answer()
    tenant_id = int((callback.data or "").split(":")[-1])

    from infrastructure.database.models.tenant import TenantModel

    factory = get_session_factory()
    async with factory() as session:
        tenant = await session.get(TenantModel, tenant_id)

    if tenant is None:
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"Tenant {tenant_id} not found.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="<< Back", callback_data="billing:back"),
            ]]),
        )
        return

    billing = getattr(tenant, "billing_status", "trial")
    text = _format_tenant_detail(tenant)
    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=_detail_keyboard(tenant_id, billing),
    )


@router.callback_query(F.data.startswith("billing:extend:"), RoleFilter(*_SUPERADMIN))
async def cb_extend(callback: CallbackQuery, **data: object) -> None:
    """Extend subscription by 30 days."""
    tenant_id = int((callback.data or "").split(":")[-1])
    await callback.answer("Extending...")
    log.info("billing_extend_requested", tenant_id=tenant_id, by_user=callback.from_user.id)

    factory = get_session_factory()
    async with factory() as session:
        svc = get_billing_service(session)
        tenant = await svc.extend_subscription(tenant_id)
        await session.commit()

    if tenant is None:
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"Tenant {tenant_id} not found.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="<< Back", callback_data="billing:back"),
            ]]),
        )
        return

    billing = getattr(tenant, "billing_status", "active")
    text = f"Extended +30 days\n\n{_format_tenant_detail(tenant)}"
    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=_detail_keyboard(tenant_id, billing),
    )


@router.callback_query(F.data.startswith("billing:activate:"), RoleFilter(*_SUPERADMIN))
async def cb_activate(callback: CallbackQuery, **data: object) -> None:
    """Reactivate an expired/suspended tenant with 30-day subscription."""
    tenant_id = int((callback.data or "").split(":")[-1])
    await callback.answer("Activating...")
    log.info("billing_activate_requested", tenant_id=tenant_id, by_user=callback.from_user.id)

    factory = get_session_factory()
    async with factory() as session:
        svc = get_billing_service(session)
        tenant = await svc.activate_tenant(tenant_id)
        await session.commit()

    if tenant is None:
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"Tenant {tenant_id} not found.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="<< Back", callback_data="billing:back"),
            ]]),
        )
        return

    # Try starting the bot if it was paused
    registry = get_bot_registry()
    bot_state = registry.get_bot_state(tenant_id)
    if bot_state and bot_state.status == BotStatus.PAUSED:
        async with factory() as session:
            await registry.start_bot(tenant_id, session)

    billing = getattr(tenant, "billing_status", "active")
    text = f"Tenant activated (30-day subscription)\n\n{_format_tenant_detail(tenant)}"
    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=_detail_keyboard(tenant_id, billing),
    )


@router.callback_query(F.data.startswith("billing:suspend:"), RoleFilter(*_SUPERADMIN))
async def cb_suspend(callback: CallbackQuery, **data: object) -> None:
    """Suspend a tenant."""
    tenant_id = int((callback.data or "").split(":")[-1])
    await callback.answer("Suspending...")
    log.info("billing_suspend_requested", tenant_id=tenant_id, by_user=callback.from_user.id)

    factory = get_session_factory()
    async with factory() as session:
        svc = get_billing_service(session)
        tenant = await svc.suspend_tenant(tenant_id)
        await session.commit()

    if tenant is None:
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"Tenant {tenant_id} not found.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="<< Back", callback_data="billing:back"),
            ]]),
        )
        return

    # Stop the bot via registry
    registry = get_bot_registry()
    await registry.stop_bot(tenant_id)

    billing = getattr(tenant, "billing_status", "suspended")
    text = f"Tenant suspended. Bot stopped.\n\n{_format_tenant_detail(tenant)}"
    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=_detail_keyboard(tenant_id, billing),
    )


# ── Payment provider selection ──────────────────────────────────────────


@router.callback_query(F.data.startswith("billing:pay:"), RoleFilter(*_SUPERADMIN))
async def cb_pay(callback: CallbackQuery, **data: object) -> None:
    """Show provider selection or generate payment link."""
    parts = (callback.data or "").split(":")
    # billing:pay:{tenant_id}
    if len(parts) == 3:
        await _show_provider_selection(callback, int(parts[2]))
    # billing:pay:{tenant_id}:{provider}
    elif len(parts) == 4:
        await _generate_payment_link(callback, int(parts[2]), parts[3])


async def _show_provider_selection(callback: CallbackQuery, tenant_id: int) -> None:
    """Show available payment providers as buttons."""
    await callback.answer()

    from shared.config import get_settings
    settings = get_settings()

    buttons: list[list[InlineKeyboardButton]] = []
    if settings.click.is_configured:
        buttons.append([InlineKeyboardButton(
            text="Click.uz",
            callback_data=f"billing:pay:{tenant_id}:click",
        )])
    if settings.payme.is_configured:
        buttons.append([InlineKeyboardButton(
            text="Payme.uz",
            callback_data=f"billing:pay:{tenant_id}:payme",
        )])
    if not buttons:
        buttons.append([InlineKeyboardButton(
            text="No providers configured",
            callback_data=f"billing:detail:{tenant_id}",
        )])
    buttons.append([InlineKeyboardButton(
        text="<< Back",
        callback_data=f"billing:detail:{tenant_id}",
    )])

    await callback.message.edit_text(  # type: ignore[union-attr]
        f"Tenant {tenant_id}\n\nTo'lov usulini tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


async def _generate_payment_link(
    callback: CallbackQuery, tenant_id: int, provider_name: str,
) -> None:
    """Create a payment record and generate a payment link."""
    await callback.answer("Generating payment link...")

    from infrastructure.database.models.tenant import TenantModel
    from infrastructure.di import get_subscription_billing_service
    from shared.constants.enums import SubscriptionPaymentProvider

    try:
        provider_enum = SubscriptionPaymentProvider(provider_name)
    except ValueError:
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"Unknown provider: {provider_name}",
        )
        return

    factory = get_session_factory()
    async with factory() as session:
        tenant = await session.get(TenantModel, tenant_id)
        if tenant is None:
            await callback.message.edit_text(  # type: ignore[union-attr]
                f"Tenant {tenant_id} not found.",
            )
            return

        amount = tenant.monthly_price_uzs
        if amount <= 0:
            await callback.message.edit_text(  # type: ignore[union-attr]
                f"Tenant {tenant.name}: monthly_price_uzs = 0.\n"
                "Set a price first via /show_tenant.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="<< Back", callback_data=f"billing:detail:{tenant_id}"),
                ]]),
            )
            return

        svc = get_subscription_billing_service(session, tenant_id)
        payment = await svc.create_payment(
            tenant_id=tenant_id,
            provider=provider_enum,
            amount=amount,
        )
        await session.commit()

    # Generate payment URL via provider
    from shared.config import get_settings
    settings = get_settings()

    if provider_enum == SubscriptionPaymentProvider.CLICK:
        from infrastructure.payment.click_provider import ClickPaymentProvider
        provider = ClickPaymentProvider(settings.click)
    else:
        from infrastructure.payment.payme_provider import PaymePaymentProvider
        provider = PaymePaymentProvider(settings.payme)

    result = await provider.create_invoice(
        tenant_id=tenant_id,
        amount=amount,
        currency="UZS",
        description=f"Obuna — {payment.extension_days} kun",
        merchant_trans_id=payment.merchant_trans_id,
    )

    if not result.success:
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"Payment link error: {result.error_message}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="<< Back", callback_data=f"billing:detail:{tenant_id}"),
            ]]),
        )
        return

    await callback.message.edit_text(  # type: ignore[union-attr]
        f"Payment link for tenant {tenant_id}\n\n"
        f"Amount: {amount:,} UZS\n"
        f"Provider: {provider_name}\n"
        f"ID: {payment.merchant_trans_id}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Open payment page", url=result.payment_url)],
            [InlineKeyboardButton(text="<< Back", callback_data=f"billing:detail:{tenant_id}")],
        ]),
    )


# ── Payment history ─────────────────────────────────────────────────────


_PAYMENT_STATUS_ICONS = {
    "pending": "[PENDING]",
    "preparing": "[PREPARING]",
    "paid": "[PAID]",
    "canceled": "[CANCELED]",
    "failed": "[FAILED]",
}


@router.callback_query(F.data.startswith("billing:payments:"), RoleFilter(*_SUPERADMIN))
async def cb_payment_history(callback: CallbackQuery, **data: object) -> None:
    """Show subscription payment history for a tenant."""
    await callback.answer()
    tenant_id = int((callback.data or "").split(":")[-1])

    from infrastructure.di import get_subscription_billing_service

    factory = get_session_factory()
    async with factory() as session:
        svc = get_subscription_billing_service(session, tenant_id)
        payments = await svc.list_tenant_payments(tenant_id, limit=10)

    if not payments:
        text = f"Tenant {tenant_id}\n\nNo subscription payments found."
    else:
        lines = [f"Tenant {tenant_id} — Payment History", "============================="]
        for p in payments:
            icon = _PAYMENT_STATUS_ICONS.get(p.status, "[?]")
            date_str = p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "--"
            lines.append(f"{icon} {p.amount:,} UZS | {p.provider} | {date_str}")
        lines.append("=============================")
        text = "\n".join(lines)

    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="<< Back", callback_data=f"billing:detail:{tenant_id}"),
        ]]),
    )
