"""
core.services.subscription_billing_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Coordinates subscription payment creation, webhook processing,
and billing lifecycle updates.
"""
from __future__ import annotations

import secrets
import time
from typing import TYPE_CHECKING

from core.domain.subscription_payment import SubscriptionPayment
from shared.constants.enums import (
    BillingStatus,
    SubscriptionPaymentProvider,
    SubscriptionPaymentStatus,
)
from shared.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from core.repositories.subscription_payment_repo import (
        AbstractSubscriptionPaymentRepository,
    )

log = get_logger(__name__)


class SubscriptionBillingService:
    """Orchestrates subscription payment lifecycle."""

    def __init__(
        self,
        session: AsyncSession,
        payment_repo: AbstractSubscriptionPaymentRepository,
    ) -> None:
        self._session = session
        self._payment_repo = payment_repo

    # ── Payment creation ─────────────────────────────────────────────

    async def create_payment(
        self,
        tenant_id: int,
        provider: SubscriptionPaymentProvider,
        amount: int,
        extension_days: int = 30,
        description: str | None = None,
    ) -> SubscriptionPayment:
        """Create a new PENDING subscription payment record."""
        merchant_trans_id = self.generate_merchant_trans_id(tenant_id)

        entity = SubscriptionPayment(
            id=0,  # auto-generated
            tenant_id=tenant_id,
            provider=provider,
            status=SubscriptionPaymentStatus.PENDING,
            amount=amount,
            description=description or f"Obuna — {extension_days} kun",
            merchant_trans_id=merchant_trans_id,
            extension_days=extension_days,
        )
        payment = await self._payment_repo.create(entity)
        log.info(
            "subscription_payment_created",
            tenant_id=tenant_id,
            provider=provider,
            amount=amount,
            merchant_trans_id=merchant_trans_id,
        )
        return payment

    # ── Webhook handlers ─────────────────────────────────────────────

    async def handle_prepare(
        self,
        merchant_trans_id: str,
        provider_trans_id: str | None = None,
        provider_meta: dict | None = None,
    ) -> SubscriptionPayment:
        """Mark payment as PREPARING (Click prepare phase)."""
        payment = await self._payment_repo.get_by_merchant_trans_id(
            merchant_trans_id, for_update=True,
        )
        if payment is None:
            raise ValueError(f"Payment not found: {merchant_trans_id}")
        if payment.status != SubscriptionPaymentStatus.PENDING:
            log.info(
                "duplicate_webhook",
                merchant_trans_id=merchant_trans_id,
                current_status=payment.status,
                action="prepare",
            )
            return payment  # idempotent

        return await self._payment_repo.update_status(
            payment.id,
            SubscriptionPaymentStatus.PREPARING,
            provider_trans_id=provider_trans_id,
            provider_meta=provider_meta or {},
        )

    async def handle_payment_success(
        self,
        merchant_trans_id: str,
        provider_trans_id: str | None = None,
        provider_meta: dict | None = None,
    ) -> SubscriptionPayment:
        """Mark payment as PAID and extend tenant subscription.

        Idempotent: if already PAID, returns existing record without
        double-extending. Uses ``FOR UPDATE`` row lock to prevent race
        conditions from concurrent webhook retries.
        """
        payment = await self._payment_repo.get_by_merchant_trans_id(
            merchant_trans_id, for_update=True,
        )
        if payment is None:
            raise ValueError(f"Payment not found: {merchant_trans_id}")

        # Idempotency guard (race-safe: row is locked via FOR UPDATE)
        if payment.status == SubscriptionPaymentStatus.PAID:
            log.info(
                "duplicate_webhook",
                merchant_trans_id=merchant_trans_id,
                payment_id=payment.id,
                action="payment_success",
            )
            return payment

        updated = await self._payment_repo.update_status(
            payment.id,
            SubscriptionPaymentStatus.PAID,
            provider_trans_id=provider_trans_id,
            provider_meta=provider_meta or {},
        )

        # Extend subscription
        from core.services.billing_service import BillingService

        billing = BillingService(self._session)
        tenant = await billing.extend_subscription(
            updated.tenant_id, days=updated.extension_days,
        )

        log.info(
            "subscription_payment_success",
            tenant_id=updated.tenant_id,
            payment_id=updated.id,
            amount=updated.amount,
            extension_days=updated.extension_days,
            expires_at=(
                tenant.subscription_expires_at.isoformat()
                if tenant and tenant.subscription_expires_at
                else None
            ),
        )

        # Send notification asynchronously (non-blocking)
        if tenant:
            await self._notify_payment_success(tenant, updated)

        return updated

    async def handle_payment_failure(
        self,
        merchant_trans_id: str,
        error_message: str | None = None,
        provider_meta: dict | None = None,
    ) -> SubscriptionPayment:
        """Mark payment as FAILED."""
        payment = await self._payment_repo.get_by_merchant_trans_id(
            merchant_trans_id, for_update=True,
        )
        if payment is None:
            raise ValueError(f"Payment not found: {merchant_trans_id}")
        if payment.status in (
            SubscriptionPaymentStatus.PAID,
            SubscriptionPaymentStatus.FAILED,
        ):
            log.info(
                "duplicate_webhook",
                merchant_trans_id=merchant_trans_id,
                current_status=payment.status,
                action="payment_failure",
            )
            return payment  # idempotent

        meta = provider_meta or {}
        if error_message:
            meta["error_message"] = error_message

        updated = await self._payment_repo.update_status(
            payment.id,
            SubscriptionPaymentStatus.FAILED,
            provider_meta=meta,
        )
        log.warning(
            "subscription_payment_failed",
            tenant_id=updated.tenant_id,
            payment_id=updated.id,
            error=error_message,
        )
        return updated

    async def handle_payment_cancel(
        self,
        merchant_trans_id: str,
        provider_meta: dict | None = None,
    ) -> SubscriptionPayment:
        """Mark payment as CANCELED."""
        payment = await self._payment_repo.get_by_merchant_trans_id(
            merchant_trans_id, for_update=True,
        )
        if payment is None:
            raise ValueError(f"Payment not found: {merchant_trans_id}")
        if payment.status == SubscriptionPaymentStatus.CANCELED:
            log.info(
                "duplicate_webhook",
                merchant_trans_id=merchant_trans_id,
                action="payment_cancel",
            )
            return payment  # idempotent

        updated = await self._payment_repo.update_status(
            payment.id,
            SubscriptionPaymentStatus.CANCELED,
            provider_meta=provider_meta or {},
        )
        log.info(
            "subscription_payment_canceled",
            tenant_id=updated.tenant_id,
            payment_id=updated.id,
        )
        return updated

    # ── Queries ───────────────────────────────────────────────────────

    async def get_by_merchant_trans_id(
        self, merchant_trans_id: str,
    ) -> SubscriptionPayment | None:
        return await self._payment_repo.get_by_merchant_trans_id(merchant_trans_id)

    async def list_tenant_payments(
        self, tenant_id: int, limit: int = 20,
    ) -> list[SubscriptionPayment]:
        return await self._payment_repo.list_by_tenant(tenant_id, limit)

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def generate_merchant_trans_id(tenant_id: int) -> str:
        """Generate a unique merchant transaction ID.

        Format: ``sub_{tenant_id}_{timestamp_ms}_{random_hex}``
        """
        ts = int(time.time() * 1000)
        rand = secrets.token_hex(4)
        return f"sub_{tenant_id}_{ts}_{rand}"

    async def _notify_payment_success(
        self, tenant: object, payment: SubscriptionPayment,
    ) -> None:
        """Send Telegram notification to tenant admin about successful payment."""
        admin_user_id = getattr(tenant, "admin_user_id", None)
        if not admin_user_id:
            return

        try:
            from aiogram import Bot
            from shared.config import get_settings

            settings = get_settings()
            bot = Bot(token=settings.bot.token.get_secret_value())
            try:
                expires_at = getattr(tenant, "subscription_expires_at", None)
                expires_str = (
                    expires_at.strftime("%Y-%m-%d") if expires_at else "--"
                )
                text = (
                    f"Obuna to'lovi qabul qilindi!\n\n"
                    f"Summa: {payment.amount:,} UZS\n"
                    f"Obuna: +{payment.extension_days} kun\n"
                    f"Amal qilish muddati: {expires_str}\n\n"
                    f"Rahmat!"
                )
                await bot.send_message(chat_id=admin_user_id, text=text)
            finally:
                await bot.session.close()
        except Exception:
            log.exception(
                "payment_success_notification_failed",
                tenant_id=payment.tenant_id,
            )
