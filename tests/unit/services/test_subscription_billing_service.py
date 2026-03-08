"""Unit tests for SubscriptionBillingService.

Covers:
  1. create_payment — creates PENDING record via repo
  2. handle_prepare — transitions PENDING → PREPARING, idempotent
  3. handle_payment_success — PAID + extend_subscription, idempotent
  4. handle_payment_failure — FAILED, idempotent
  5. handle_payment_cancel — CANCELED, idempotent
  6. generate_merchant_trans_id — format and uniqueness
  7. Missing payment raises ValueError
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from core.domain.subscription_payment import SubscriptionPayment
from core.repositories.subscription_payment_repo import (
    AbstractSubscriptionPaymentRepository,
)
from core.services.subscription_billing_service import SubscriptionBillingService
from shared.constants.enums import (
    SubscriptionPaymentProvider,
    SubscriptionPaymentStatus,
)

import pytest


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


class TestCreatePayment:
    """create_payment builds a PENDING record and calls repo.create."""

    def setup_method(self) -> None:
        self.session = AsyncMock()
        self.repo = AsyncMock(spec=AbstractSubscriptionPaymentRepository)
        self.svc = SubscriptionBillingService(self.session, self.repo)

    async def test_creates_pending_payment(self) -> None:
        created = _make_payment(id=42)
        self.repo.create = AsyncMock(return_value=created)

        result = await self.svc.create_payment(
            tenant_id=10,
            provider=SubscriptionPaymentProvider.CLICK,
            amount=100_000,
        )

        assert result.id == 42
        self.repo.create.assert_awaited_once()
        entity = self.repo.create.call_args[0][0]
        assert entity.status == SubscriptionPaymentStatus.PENDING
        assert entity.tenant_id == 10
        assert entity.amount == 100_000

    async def test_custom_extension_days(self) -> None:
        self.repo.create = AsyncMock(return_value=_make_payment(extension_days=90))

        result = await self.svc.create_payment(
            tenant_id=10,
            provider=SubscriptionPaymentProvider.PAYME,
            amount=200_000,
            extension_days=90,
        )

        entity = self.repo.create.call_args[0][0]
        assert entity.extension_days == 90


class TestHandlePrepare:
    """handle_prepare transitions PENDING → PREPARING."""

    def setup_method(self) -> None:
        self.session = AsyncMock()
        self.repo = AsyncMock(spec=AbstractSubscriptionPaymentRepository)
        self.svc = SubscriptionBillingService(self.session, self.repo)

    async def test_transitions_to_preparing(self) -> None:
        pending = _make_payment(status=SubscriptionPaymentStatus.PENDING)
        preparing = _make_payment(status=SubscriptionPaymentStatus.PREPARING)
        self.repo.get_by_merchant_trans_id = AsyncMock(return_value=pending)
        self.repo.update_status = AsyncMock(return_value=preparing)

        result = await self.svc.handle_prepare("sub_10_1234_abcd", "click-123")

        assert result.status == SubscriptionPaymentStatus.PREPARING
        self.repo.update_status.assert_awaited_once_with(
            1, SubscriptionPaymentStatus.PREPARING,
            provider_trans_id="click-123", provider_meta={},
        )

    async def test_idempotent_when_already_preparing(self) -> None:
        preparing = _make_payment(status=SubscriptionPaymentStatus.PREPARING)
        self.repo.get_by_merchant_trans_id = AsyncMock(return_value=preparing)

        result = await self.svc.handle_prepare("sub_10_1234_abcd")

        assert result.status == SubscriptionPaymentStatus.PREPARING
        self.repo.update_status.assert_not_awaited()

    async def test_raises_when_not_found(self) -> None:
        self.repo.get_by_merchant_trans_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Payment not found"):
            await self.svc.handle_prepare("nonexistent")


class TestHandlePaymentSuccess:
    """handle_payment_success marks PAID and extends subscription."""

    def setup_method(self) -> None:
        self.session = AsyncMock()
        self.repo = AsyncMock(spec=AbstractSubscriptionPaymentRepository)
        self.svc = SubscriptionBillingService(self.session, self.repo)

    async def test_marks_paid_and_extends(self) -> None:
        pending = _make_payment(status=SubscriptionPaymentStatus.PREPARING)
        paid = _make_payment(status=SubscriptionPaymentStatus.PAID)
        self.repo.get_by_merchant_trans_id = AsyncMock(return_value=pending)
        self.repo.update_status = AsyncMock(return_value=paid)

        mock_tenant = MagicMock(subscription_expires_at=None, admin_user_id=None)
        with patch(
            "core.services.billing_service.BillingService"
        ) as MockBilling:
            mock_billing_inst = MockBilling.return_value
            mock_billing_inst.extend_subscription = AsyncMock(return_value=mock_tenant)

            result = await self.svc.handle_payment_success(
                "sub_10_1234_abcd", provider_trans_id="click-456",
            )

        assert result.status == SubscriptionPaymentStatus.PAID
        mock_billing_inst.extend_subscription.assert_awaited_once_with(
            paid.tenant_id, days=paid.extension_days,
        )

    async def test_idempotent_when_already_paid(self) -> None:
        paid = _make_payment(status=SubscriptionPaymentStatus.PAID)
        self.repo.get_by_merchant_trans_id = AsyncMock(return_value=paid)

        result = await self.svc.handle_payment_success("sub_10_1234_abcd")

        assert result.status == SubscriptionPaymentStatus.PAID
        self.repo.update_status.assert_not_awaited()

    async def test_raises_when_not_found(self) -> None:
        self.repo.get_by_merchant_trans_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Payment not found"):
            await self.svc.handle_payment_success("nonexistent")


class TestHandlePaymentFailure:
    """handle_payment_failure marks FAILED."""

    def setup_method(self) -> None:
        self.session = AsyncMock()
        self.repo = AsyncMock(spec=AbstractSubscriptionPaymentRepository)
        self.svc = SubscriptionBillingService(self.session, self.repo)

    async def test_marks_failed(self) -> None:
        pending = _make_payment(status=SubscriptionPaymentStatus.PENDING)
        failed = _make_payment(status=SubscriptionPaymentStatus.FAILED)
        self.repo.get_by_merchant_trans_id = AsyncMock(return_value=pending)
        self.repo.update_status = AsyncMock(return_value=failed)

        result = await self.svc.handle_payment_failure(
            "sub_10_1234_abcd", error_message="timeout",
        )

        assert result.status == SubscriptionPaymentStatus.FAILED
        meta = self.repo.update_status.call_args[1]["provider_meta"]
        assert meta["error_message"] == "timeout"

    async def test_idempotent_when_already_paid(self) -> None:
        """Cannot fail a PAID payment."""
        paid = _make_payment(status=SubscriptionPaymentStatus.PAID)
        self.repo.get_by_merchant_trans_id = AsyncMock(return_value=paid)

        result = await self.svc.handle_payment_failure("sub_10_1234_abcd")

        assert result.status == SubscriptionPaymentStatus.PAID
        self.repo.update_status.assert_not_awaited()

    async def test_idempotent_when_already_failed(self) -> None:
        failed = _make_payment(status=SubscriptionPaymentStatus.FAILED)
        self.repo.get_by_merchant_trans_id = AsyncMock(return_value=failed)

        result = await self.svc.handle_payment_failure("sub_10_1234_abcd")

        assert result.status == SubscriptionPaymentStatus.FAILED
        self.repo.update_status.assert_not_awaited()

    async def test_raises_when_not_found(self) -> None:
        self.repo.get_by_merchant_trans_id = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="Payment not found"):
            await self.svc.handle_payment_failure("nonexistent")


class TestHandlePaymentCancel:
    """handle_payment_cancel marks CANCELED."""

    def setup_method(self) -> None:
        self.session = AsyncMock()
        self.repo = AsyncMock(spec=AbstractSubscriptionPaymentRepository)
        self.svc = SubscriptionBillingService(self.session, self.repo)

    async def test_marks_canceled(self) -> None:
        pending = _make_payment(status=SubscriptionPaymentStatus.PENDING)
        canceled = _make_payment(status=SubscriptionPaymentStatus.CANCELED)
        self.repo.get_by_merchant_trans_id = AsyncMock(return_value=pending)
        self.repo.update_status = AsyncMock(return_value=canceled)

        result = await self.svc.handle_payment_cancel("sub_10_1234_abcd")

        assert result.status == SubscriptionPaymentStatus.CANCELED

    async def test_idempotent_when_already_canceled(self) -> None:
        canceled = _make_payment(status=SubscriptionPaymentStatus.CANCELED)
        self.repo.get_by_merchant_trans_id = AsyncMock(return_value=canceled)

        result = await self.svc.handle_payment_cancel("sub_10_1234_abcd")

        assert result.status == SubscriptionPaymentStatus.CANCELED
        self.repo.update_status.assert_not_awaited()


class TestGenerateMerchantTransId:
    """generate_merchant_trans_id produces correct format."""

    def test_format_prefix(self) -> None:
        tid = SubscriptionBillingService.generate_merchant_trans_id(42)
        assert tid.startswith("sub_42_")

    def test_unique_across_calls(self) -> None:
        ids = {
            SubscriptionBillingService.generate_merchant_trans_id(1) for _ in range(10)
        }
        assert len(ids) == 10

    def test_contains_timestamp_and_hex(self) -> None:
        tid = SubscriptionBillingService.generate_merchant_trans_id(5)
        parts = tid.split("_")
        assert len(parts) == 4  # sub, 5, timestamp, hex
        assert parts[0] == "sub"
        assert parts[1] == "5"
        assert parts[2].isdigit()
        assert len(parts[3]) == 8  # token_hex(4) = 8 chars


class TestListAndLookup:
    """Delegation methods for queries."""

    def setup_method(self) -> None:
        self.session = AsyncMock()
        self.repo = AsyncMock(spec=AbstractSubscriptionPaymentRepository)
        self.svc = SubscriptionBillingService(self.session, self.repo)

    async def test_get_by_merchant_trans_id(self) -> None:
        payment = _make_payment()
        self.repo.get_by_merchant_trans_id = AsyncMock(return_value=payment)

        result = await self.svc.get_by_merchant_trans_id("sub_10_1234_abcd")

        assert result is payment

    async def test_list_tenant_payments(self) -> None:
        payments = [_make_payment(id=i) for i in range(3)]
        self.repo.list_by_tenant = AsyncMock(return_value=payments)

        result = await self.svc.list_tenant_payments(10, limit=5)

        assert len(result) == 3
        self.repo.list_by_tenant.assert_awaited_once_with(10, 5)
