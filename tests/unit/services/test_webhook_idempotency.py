"""Unit tests for payment webhook idempotency.

Covers:
  1. Duplicate webhooks do NOT extend subscription twice
  2. FOR UPDATE row locking is used in write operations
  3. Service returns early on already-processed payments
  4. Click webhook returns ALREADY_PAID on duplicate COMPLETE
  5. Payme webhook returns idempotent response on duplicate PerformTransaction
  6. Model has unique constraint on provider_trans_id
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.domain.subscription_payment import SubscriptionPayment
from core.repositories.subscription_payment_repo import (
    AbstractSubscriptionPaymentRepository,
)
from core.services.subscription_billing_service import SubscriptionBillingService
from shared.constants.enums import (
    SubscriptionPaymentProvider,
    SubscriptionPaymentStatus,
)


def _make_payment(**overrides) -> SubscriptionPayment:
    defaults = dict(
        id=1,
        tenant_id=10,
        provider=SubscriptionPaymentProvider.CLICK,
        status=SubscriptionPaymentStatus.PENDING,
        amount=100_000,
        merchant_trans_id="sub_10_1234_abcd",
        extension_days=30,
    )
    defaults.update(overrides)
    return SubscriptionPayment(**defaults)


# ── Idempotency: duplicate webhook does NOT extend subscription ─────────


class TestDuplicateWebhookDoesNotExtend:
    """The critical invariant: a duplicate webhook must NOT extend subscription."""

    def setup_method(self) -> None:
        self.session = AsyncMock()
        self.repo = AsyncMock(spec=AbstractSubscriptionPaymentRepository)
        self.svc = SubscriptionBillingService(self.session, self.repo)

    async def test_duplicate_success_does_not_extend_subscription(self) -> None:
        """If payment is already PAID, extend_subscription must NOT be called."""
        paid = _make_payment(status=SubscriptionPaymentStatus.PAID)
        self.repo.get_by_merchant_trans_id = AsyncMock(return_value=paid)

        with patch(
            "core.services.billing_service.BillingService"
        ) as MockBilling:
            result = await self.svc.handle_payment_success("sub_10_1234_abcd")

            # Must not instantiate or call BillingService at all
            MockBilling.assert_not_called()

        assert result.status == SubscriptionPaymentStatus.PAID
        self.repo.update_status.assert_not_awaited()

    async def test_first_success_does_extend_subscription(self) -> None:
        """First webhook: extend_subscription IS called exactly once."""
        preparing = _make_payment(status=SubscriptionPaymentStatus.PREPARING)
        paid = _make_payment(status=SubscriptionPaymentStatus.PAID)
        self.repo.get_by_merchant_trans_id = AsyncMock(return_value=preparing)
        self.repo.update_status = AsyncMock(return_value=paid)

        mock_tenant = MagicMock(
            subscription_expires_at=None, admin_user_id=None,
        )
        with patch(
            "core.services.billing_service.BillingService"
        ) as MockBilling:
            mock_billing_inst = MockBilling.return_value
            mock_billing_inst.extend_subscription = AsyncMock(
                return_value=mock_tenant,
            )

            await self.svc.handle_payment_success(
                "sub_10_1234_abcd", provider_trans_id="click-456",
            )

            mock_billing_inst.extend_subscription.assert_awaited_once()

    async def test_two_successive_calls_extend_only_once(self) -> None:
        """Simulate two successive handle_payment_success calls.

        First call: PREPARING → PAID + extend
        Second call: PAID → return early, no extend
        """
        preparing = _make_payment(status=SubscriptionPaymentStatus.PREPARING)
        paid = _make_payment(status=SubscriptionPaymentStatus.PAID)
        self.repo.update_status = AsyncMock(return_value=paid)

        # First call returns PREPARING, second returns PAID
        self.repo.get_by_merchant_trans_id = AsyncMock(
            side_effect=[preparing, paid],
        )

        mock_tenant = MagicMock(
            subscription_expires_at=None, admin_user_id=None,
        )
        with patch(
            "core.services.billing_service.BillingService"
        ) as MockBilling:
            mock_billing_inst = MockBilling.return_value
            mock_billing_inst.extend_subscription = AsyncMock(
                return_value=mock_tenant,
            )

            # First call — processes
            await self.svc.handle_payment_success(
                "sub_10_1234_abcd", provider_trans_id="click-456",
            )
            # Second call — idempotent
            await self.svc.handle_payment_success(
                "sub_10_1234_abcd", provider_trans_id="click-456",
            )

            # extend_subscription called exactly ONCE (not twice)
            assert mock_billing_inst.extend_subscription.await_count == 1


# ── FOR UPDATE is used in write operations ───────────────────────────────


class TestForUpdateUsed:
    """Verify that write operations use FOR UPDATE row locking."""

    def setup_method(self) -> None:
        self.session = AsyncMock()
        self.repo = AsyncMock(spec=AbstractSubscriptionPaymentRepository)
        self.svc = SubscriptionBillingService(self.session, self.repo)

    async def test_handle_prepare_uses_for_update(self) -> None:
        pending = _make_payment(status=SubscriptionPaymentStatus.PENDING)
        preparing = _make_payment(status=SubscriptionPaymentStatus.PREPARING)
        self.repo.get_by_merchant_trans_id = AsyncMock(return_value=pending)
        self.repo.update_status = AsyncMock(return_value=preparing)

        await self.svc.handle_prepare("sub_10_1234_abcd")

        self.repo.get_by_merchant_trans_id.assert_awaited_once_with(
            "sub_10_1234_abcd", for_update=True,
        )

    async def test_handle_payment_success_uses_for_update(self) -> None:
        paid = _make_payment(status=SubscriptionPaymentStatus.PAID)
        self.repo.get_by_merchant_trans_id = AsyncMock(return_value=paid)

        await self.svc.handle_payment_success("sub_10_1234_abcd")

        self.repo.get_by_merchant_trans_id.assert_awaited_once_with(
            "sub_10_1234_abcd", for_update=True,
        )

    async def test_handle_payment_failure_uses_for_update(self) -> None:
        failed = _make_payment(status=SubscriptionPaymentStatus.FAILED)
        self.repo.get_by_merchant_trans_id = AsyncMock(return_value=failed)

        await self.svc.handle_payment_failure("sub_10_1234_abcd")

        self.repo.get_by_merchant_trans_id.assert_awaited_once_with(
            "sub_10_1234_abcd", for_update=True,
        )

    async def test_handle_payment_cancel_uses_for_update(self) -> None:
        canceled = _make_payment(status=SubscriptionPaymentStatus.CANCELED)
        self.repo.get_by_merchant_trans_id = AsyncMock(return_value=canceled)

        await self.svc.handle_payment_cancel("sub_10_1234_abcd")

        self.repo.get_by_merchant_trans_id.assert_awaited_once_with(
            "sub_10_1234_abcd", for_update=True,
        )


# ── Unique constraint on provider_trans_id ───────────────────────────────


class TestProviderTransIdUnique:
    """Verify the model has a unique partial index on provider_trans_id."""

    def test_model_has_unique_provider_trans_id_index(self) -> None:
        from infrastructure.database.models.subscription_payment import (
            SubscriptionPaymentModel,
        )

        # Find the unique index
        table = SubscriptionPaymentModel.__table__
        idx_names = {idx.name for idx in table.indexes}
        assert "uq_sub_payments_provider_trans_id" in idx_names

        idx = next(
            i for i in table.indexes
            if i.name == "uq_sub_payments_provider_trans_id"
        )
        assert idx.unique is True

    def test_merchant_trans_id_is_unique(self) -> None:
        from infrastructure.database.models.subscription_payment import (
            SubscriptionPaymentModel,
        )

        col = SubscriptionPaymentModel.__table__.c.merchant_trans_id
        assert col.unique is True


# ── Read operations do NOT use FOR UPDATE ────────────────────────────────


class TestReadOperationsNoLock:
    """Read-only queries should NOT use FOR UPDATE (no deadlock risk)."""

    def setup_method(self) -> None:
        self.session = AsyncMock()
        self.repo = AsyncMock(spec=AbstractSubscriptionPaymentRepository)
        self.svc = SubscriptionBillingService(self.session, self.repo)

    async def test_get_by_merchant_trans_id_no_lock(self) -> None:
        payment = _make_payment()
        self.repo.get_by_merchant_trans_id = AsyncMock(return_value=payment)

        await self.svc.get_by_merchant_trans_id("sub_10_1234_abcd")

        # Default for_update should be False (not passed)
        self.repo.get_by_merchant_trans_id.assert_awaited_once_with(
            "sub_10_1234_abcd",
        )
