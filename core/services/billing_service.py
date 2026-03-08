"""
core.services.billing_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Manages tenant billing lifecycle: trial initialization, subscription
extension, suspension, activation, and daily expiration processing.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select

from shared.constants.enums import BillingStatus, SubscriptionPlan
from shared.constants.plans import get_plan_config
from shared.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from infrastructure.database.models.tenant import TenantModel

log = get_logger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────

TRIAL_DURATION_DAYS = 7
DEFAULT_EXTENSION_DAYS = 30
WARNING_DAYS = (3, 1)

_MSG_WARNING_3DAY = (
    "Diqqat! Sizning obunangiz 3 kundan keyin tugaydi.\n\n"
    "Obunani uzaytiring — aks holda bot to'xtatiladi.\n"
    "Savol bo'lsa: @admin_support"
)

_MSG_WARNING_1DAY = (
    "Diqqat! Sizning obunangiz <b>ERTAGA</b> tugaydi!\n\n"
    "Botni to'xtatmaslik uchun hozir obunani uzaytiring.\n"
    "Savol bo'lsa: @admin_support"
)

_MSG_EXPIRED = (
    "Sizning obunangiz tugadi.\n"
    "Bot to'xtatildi. Obunani qayta faollashtirish uchun "
    "administrator bilan bog'laning: @admin_support"
)

_NOTIFICATION_MESSAGES = {
    "3day": _MSG_WARNING_3DAY,
    "1day": _MSG_WARNING_1DAY,
    "expired": _MSG_EXPIRED,
}


# ── Service ───────────────────────────────────────────────────────────────


class BillingService:
    """Manages tenant billing lifecycle."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Trial ─────────────────────────────────────────────────────────

    def initialize_trial(self, tenant: TenantModel) -> TenantModel:
        """Set trial fields on a newly created tenant (before flush).

        Trial tenants get PRO plan features for the trial duration.
        """
        now = datetime.now(timezone.utc)
        tenant.billing_status = BillingStatus.TRIAL.value
        tenant.billing_plan = SubscriptionPlan.PRO.value
        tenant.trial_ends_at = now + timedelta(days=TRIAL_DURATION_DAYS)

        log.info(
            "trial_started",
            tenant_id=getattr(tenant, "id", None),
            plan=SubscriptionPlan.PRO.value,
            trial_ends_at=(now + timedelta(days=TRIAL_DURATION_DAYS)).isoformat(),
        )
        return tenant

    # ── Subscription lifecycle ────────────────────────────────────────

    async def extend_subscription(
        self, tenant_id: int, days: int = DEFAULT_EXTENSION_DAYS,
    ) -> TenantModel | None:
        """Extend or create a subscription for the given tenant."""
        from infrastructure.database.models.tenant import TenantModel as TM

        tenant = await self._session.get(TM, tenant_id)
        if tenant is None:
            return None

        now = datetime.now(timezone.utc)
        base = tenant.subscription_expires_at
        if base is None or base < now:
            base = now
        tenant.subscription_expires_at = base + timedelta(days=days)
        tenant.billing_status = BillingStatus.ACTIVE.value
        await self._session.flush()

        log.info(
            "subscription_extended",
            tenant_id=tenant_id,
            days=days,
            expires_at=tenant.subscription_expires_at.isoformat(),
        )
        return tenant

    async def activate_tenant(self, tenant_id: int) -> TenantModel | None:
        """Reactivate an expired/suspended tenant with 30-day subscription."""
        return await self.extend_subscription(tenant_id, DEFAULT_EXTENSION_DAYS)

    async def suspend_tenant(self, tenant_id: int) -> TenantModel | None:
        """Manually suspend a tenant."""
        from infrastructure.database.models.tenant import TenantModel as TM

        tenant = await self._session.get(TM, tenant_id)
        if tenant is None:
            return None
        tenant.billing_status = BillingStatus.SUSPENDED.value
        await self._session.flush()

        log.info("tenant_suspended", tenant_id=tenant_id)
        return tenant

    async def upgrade_plan(
        self,
        tenant_id: int,
        plan: str,
        *,
        extend_days: int = DEFAULT_EXTENSION_DAYS,
    ) -> TenantModel | None:
        """Upgrade a tenant's subscription plan.

        Sets billing_plan, monthly_price_uzs, billing_status=ACTIVE,
        and extends the subscription period.
        """
        from infrastructure.database.models.tenant import TenantModel as TM

        tenant = await self._session.get(TM, tenant_id)
        if tenant is None:
            return None

        config = get_plan_config(plan)
        old_plan = tenant.billing_plan

        tenant.billing_plan = plan
        tenant.monthly_price_uzs = config.monthly_price_uzs
        tenant.billing_status = BillingStatus.ACTIVE.value

        now = datetime.now(timezone.utc)
        base = tenant.subscription_expires_at
        if base is None or base < now:
            base = now
        tenant.subscription_expires_at = base + timedelta(days=extend_days)
        await self._session.flush()

        log.info(
            "plan_upgraded",
            tenant_id=tenant_id,
            old_plan=old_plan,
            new_plan=plan,
            price_uzs=config.monthly_price_uzs,
            expires_at=tenant.subscription_expires_at.isoformat(),
        )
        return tenant

    async def downgrade_to_free(self, tenant_id: int) -> TenantModel | None:
        """Downgrade a tenant to the FREE plan (used after trial expiry)."""
        from infrastructure.database.models.tenant import TenantModel as TM

        tenant = await self._session.get(TM, tenant_id)
        if tenant is None:
            return None

        old_plan = tenant.billing_plan
        free_config = get_plan_config(SubscriptionPlan.FREE.value)

        tenant.billing_plan = SubscriptionPlan.FREE.value
        tenant.monthly_price_uzs = free_config.monthly_price_uzs
        await self._session.flush()

        log.info(
            "plan_downgraded",
            tenant_id=tenant_id,
            old_plan=old_plan,
            new_plan=SubscriptionPlan.FREE.value,
        )
        return tenant

    async def check_limits(self, tenant_id: int) -> dict:
        """Check current usage vs plan limits for a tenant.

        Returns a dict with limit check results. Fails open.
        """
        from infrastructure.database.models.tenant import TenantModel as TM
        from core.services.usage_service import get_usage_summary

        tenant = await self._session.get(TM, tenant_id)
        if tenant is None:
            return {"error": "tenant_not_found"}

        usage = await get_usage_summary(tenant_id, tenant.billing_plan)
        return {
            "plan": usage.plan_name,
            "leads_used": usage.leads_used,
            "leads_limit": usage.leads_limit,
            "leads_remaining": usage.leads_remaining,
            "ai_used": usage.ai_messages_used,
            "ai_limit": usage.ai_messages_limit,
            "ai_remaining": usage.ai_remaining,
        }

    @staticmethod
    async def reset_usage(tenant_id: int) -> None:
        """Reset monthly usage counters for a tenant."""
        from core.services.usage_service import reset_monthly_usage

        await reset_monthly_usage(tenant_id)
        log.info("usage_reset", tenant_id=tenant_id)

    # ── Queries ───────────────────────────────────────────────────────

    async def list_all_tenants(self) -> list[TenantModel]:
        """Return all tenants ordered by ID."""
        from infrastructure.database.models.tenant import TenantModel as TM

        result = await self._session.execute(select(TM).order_by(TM.id))
        return list(result.scalars().all())

    @staticmethod
    def get_expiry_date(tenant: TenantModel) -> datetime | None:
        """Return the relevant expiry date based on billing status."""
        status = getattr(tenant, "billing_status", None)
        if status == BillingStatus.TRIAL.value:
            return getattr(tenant, "trial_ends_at", None)
        if status == BillingStatus.ACTIVE.value:
            return getattr(tenant, "subscription_expires_at", None)
        return None

    # ── Daily expiration processing ───────────────────────────────────

    async def process_expirations(self) -> dict[str, int]:
        """Check all trial/active tenants for expiry.

        Sends warnings at 3d and 1d before, expires overdue tenants.
        Returns counts: {warnings_sent, expired, skipped}.
        """
        from infrastructure.database.models.tenant import TenantModel as TM

        now = datetime.now(timezone.utc)
        result = await self._session.execute(
            select(TM).where(
                TM.billing_status.in_([
                    BillingStatus.TRIAL.value,
                    BillingStatus.ACTIVE.value,
                ])
            )
        )
        tenants = result.scalars().all()

        counts = {"warnings_sent": 0, "expired": 0, "skipped": 0}

        for tenant in tenants:
            expiry = self.get_expiry_date(tenant)
            if expiry is None:
                counts["skipped"] += 1
                continue

            days_left = (expiry - now).days

            if days_left <= 0:
                was_trial = tenant.billing_status == BillingStatus.TRIAL.value
                tenant.billing_status = BillingStatus.EXPIRED.value
                # Downgrade trial → FREE plan (keep bot running with limits)
                if was_trial:
                    tenant.billing_plan = SubscriptionPlan.FREE.value
                    tenant.monthly_price_uzs = 0
                    log.info(
                        "trial_ended",
                        tenant_id=tenant.id,
                        downgraded_to="free",
                    )
                await self._send_notification(tenant, "expired")
                counts["expired"] += 1
                log.info(
                    "tenant_expired",
                    tenant_id=tenant.id,
                    billing_status_was=tenant.billing_status,
                )
            elif days_left in WARNING_DAYS:
                await self._send_notification(tenant, f"{days_left}day")
                counts["warnings_sent"] += 1

        await self._session.flush()
        return counts

    # ── Notification helper ───────────────────────────────────────────

    async def _send_notification(
        self, tenant: TenantModel, notification_type: str,
    ) -> None:
        """Send billing notification to tenant admin_user_id with dedup."""
        if not tenant.admin_user_id:
            return

        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys, CacheTTL

        redis = get_redis()
        key = CacheKeys.billing_notification_sent(tenant.id, notification_type)
        already_sent = await redis.get(key)
        if already_sent:
            return

        text = _NOTIFICATION_MESSAGES.get(notification_type)
        if not text:
            return

        from aiogram import Bot
        from shared.config import get_settings

        settings = get_settings()
        bot = Bot(token=settings.bot.token.get_secret_value())
        try:
            await bot.send_message(
                chat_id=tenant.admin_user_id,
                text=f"<b>{tenant.name}</b>\n\n{text}",
                parse_mode="HTML",
            )
            await redis.set(key, "1", ttl=CacheTTL.BILLING_NOTIFICATION)
            log.info(
                "billing_notification_sent",
                tenant_id=tenant.id,
                type=notification_type,
                admin_user_id=tenant.admin_user_id,
            )
        except Exception:
            log.exception(
                "billing_notification_failed",
                tenant_id=tenant.id,
                type=notification_type,
            )
        finally:
            await bot.session.close()
