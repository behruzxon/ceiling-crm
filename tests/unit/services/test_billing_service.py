"""Unit tests for BillingService.

Covers:
  1. initialize_trial — sets billing_status + trial_ends_at
  2. extend_subscription — fresh / existing / expired base
  3. activate_tenant — delegates to extend_subscription
  4. suspend_tenant — sets SUSPENDED status
  5. get_expiry_date — TRIAL vs ACTIVE vs EXPIRED
  6. process_expirations — warnings + expiry transitions
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from core.services.billing_service import (
    BillingService,
    DEFAULT_EXTENSION_DAYS,
    TRIAL_DURATION_DAYS,
)
from shared.constants.enums import BillingStatus


def _make_tenant(**overrides) -> MagicMock:
    """Create a mock TenantModel with sensible defaults."""
    defaults = {
        "id": 1,
        "name": "TestTenant",
        "slug": "test",
        "billing_status": BillingStatus.TRIAL.value,
        "trial_ends_at": None,
        "subscription_expires_at": None,
        "admin_user_id": None,
        "is_active": True,
    }
    defaults.update(overrides)
    return MagicMock(**defaults)


class TestInitializeTrial:
    """BillingService.initialize_trial sets trial fields correctly."""

    def setup_method(self) -> None:
        self.session = AsyncMock()
        self.svc = BillingService(self.session)

    def test_sets_billing_status_to_trial(self) -> None:
        tenant = _make_tenant(billing_status=None)
        result = self.svc.initialize_trial(tenant)
        assert result.billing_status == BillingStatus.TRIAL.value

    def test_sets_trial_ends_at(self) -> None:
        tenant = _make_tenant()
        before = datetime.now(timezone.utc)
        result = self.svc.initialize_trial(tenant)
        after = datetime.now(timezone.utc)
        expected_min = before + timedelta(days=TRIAL_DURATION_DAYS)
        expected_max = after + timedelta(days=TRIAL_DURATION_DAYS)
        assert expected_min <= result.trial_ends_at <= expected_max

    def test_returns_same_tenant_object(self) -> None:
        tenant = _make_tenant()
        result = self.svc.initialize_trial(tenant)
        assert result is tenant


class TestExtendSubscription:
    """BillingService.extend_subscription extends or creates subscriptions."""

    def setup_method(self) -> None:
        self.session = AsyncMock()
        self.svc = BillingService(self.session)

    async def test_returns_none_for_missing_tenant(self) -> None:
        self.session.get = AsyncMock(return_value=None)
        result = await self.svc.extend_subscription(999)
        assert result is None

    async def test_fresh_subscription_starts_from_now(self) -> None:
        tenant = _make_tenant(subscription_expires_at=None)
        self.session.get = AsyncMock(return_value=tenant)

        before = datetime.now(timezone.utc)
        result = await self.svc.extend_subscription(1, days=30)
        after = datetime.now(timezone.utc)

        assert result is tenant
        assert result.billing_status == BillingStatus.ACTIVE.value
        # Should be roughly now + 30 days
        assert before + timedelta(days=30) <= result.subscription_expires_at
        assert result.subscription_expires_at <= after + timedelta(days=30)
        self.session.flush.assert_awaited_once()

    async def test_extends_from_existing_future_date(self) -> None:
        future = datetime.now(timezone.utc) + timedelta(days=10)
        tenant = _make_tenant(subscription_expires_at=future)
        self.session.get = AsyncMock(return_value=tenant)

        await self.svc.extend_subscription(1, days=30)

        # Base should be the future date, not now
        expected_min = future + timedelta(days=30) - timedelta(seconds=1)
        assert tenant.subscription_expires_at >= expected_min

    async def test_extends_from_now_when_expired(self) -> None:
        past = datetime.now(timezone.utc) - timedelta(days=5)
        tenant = _make_tenant(subscription_expires_at=past)
        self.session.get = AsyncMock(return_value=tenant)

        before = datetime.now(timezone.utc)
        await self.svc.extend_subscription(1, days=30)

        # Since expired, should extend from now, not from the past date
        assert tenant.subscription_expires_at >= before + timedelta(days=30) - timedelta(seconds=1)

    async def test_sets_active_status(self) -> None:
        tenant = _make_tenant(
            billing_status=BillingStatus.EXPIRED.value,
            subscription_expires_at=None,
        )
        self.session.get = AsyncMock(return_value=tenant)
        await self.svc.extend_subscription(1)
        assert tenant.billing_status == BillingStatus.ACTIVE.value

    async def test_custom_days(self) -> None:
        tenant = _make_tenant(subscription_expires_at=None)
        self.session.get = AsyncMock(return_value=tenant)

        before = datetime.now(timezone.utc)
        await self.svc.extend_subscription(1, days=90)

        assert tenant.subscription_expires_at >= before + timedelta(days=90) - timedelta(seconds=1)


class TestActivateTenant:
    """activate_tenant delegates to extend_subscription with default days."""

    def setup_method(self) -> None:
        self.session = AsyncMock()
        self.svc = BillingService(self.session)

    async def test_activates_with_default_days(self) -> None:
        tenant = _make_tenant(
            billing_status=BillingStatus.EXPIRED.value,
            subscription_expires_at=None,
        )
        self.session.get = AsyncMock(return_value=tenant)
        result = await self.svc.activate_tenant(1)
        assert result is not None
        assert result.billing_status == BillingStatus.ACTIVE.value


class TestSuspendTenant:
    """suspend_tenant sets SUSPENDED status."""

    def setup_method(self) -> None:
        self.session = AsyncMock()
        self.svc = BillingService(self.session)

    async def test_sets_suspended_status(self) -> None:
        tenant = _make_tenant(billing_status=BillingStatus.ACTIVE.value)
        self.session.get = AsyncMock(return_value=tenant)
        result = await self.svc.suspend_tenant(1)
        assert result.billing_status == BillingStatus.SUSPENDED.value
        self.session.flush.assert_awaited_once()

    async def test_returns_none_for_missing_tenant(self) -> None:
        self.session.get = AsyncMock(return_value=None)
        result = await self.svc.suspend_tenant(999)
        assert result is None


class TestGetExpiryDate:
    """get_expiry_date returns the right date based on billing status."""

    def test_trial_returns_trial_ends_at(self) -> None:
        dt = datetime.now(timezone.utc) + timedelta(days=5)
        tenant = _make_tenant(billing_status=BillingStatus.TRIAL.value, trial_ends_at=dt)
        assert BillingService.get_expiry_date(tenant) == dt

    def test_active_returns_subscription_expires_at(self) -> None:
        dt = datetime.now(timezone.utc) + timedelta(days=20)
        tenant = _make_tenant(
            billing_status=BillingStatus.ACTIVE.value,
            subscription_expires_at=dt,
        )
        assert BillingService.get_expiry_date(tenant) == dt

    def test_expired_returns_none(self) -> None:
        tenant = _make_tenant(billing_status=BillingStatus.EXPIRED.value)
        assert BillingService.get_expiry_date(tenant) is None

    def test_suspended_returns_none(self) -> None:
        tenant = _make_tenant(billing_status=BillingStatus.SUSPENDED.value)
        assert BillingService.get_expiry_date(tenant) is None


class TestProcessExpirations:
    """process_expirations handles trial/active expiry and warnings."""

    def setup_method(self) -> None:
        self.session = AsyncMock()
        self.svc = BillingService(self.session)

    async def test_expires_overdue_tenant(self) -> None:
        past = datetime.now(timezone.utc) - timedelta(days=1)
        tenant = _make_tenant(
            billing_status=BillingStatus.TRIAL.value,
            trial_ends_at=past,
        )
        # Mock the query
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tenant]
        self.session.execute = AsyncMock(return_value=mock_result)

        with patch.object(self.svc, "_send_notification", new_callable=AsyncMock):
            counts = await self.svc.process_expirations()

        assert counts["expired"] == 1
        assert tenant.billing_status == BillingStatus.EXPIRED.value

    async def test_sends_warning_at_3_days(self) -> None:
        future = datetime.now(timezone.utc) + timedelta(days=3, seconds=100)
        tenant = _make_tenant(
            billing_status=BillingStatus.ACTIVE.value,
            subscription_expires_at=future,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tenant]
        self.session.execute = AsyncMock(return_value=mock_result)

        with patch.object(self.svc, "_send_notification", new_callable=AsyncMock) as mock_notify:
            counts = await self.svc.process_expirations()

        assert counts["warnings_sent"] == 1
        mock_notify.assert_awaited_once_with(tenant, "3day")

    async def test_skips_tenant_without_expiry(self) -> None:
        tenant = _make_tenant(
            billing_status=BillingStatus.TRIAL.value,
            trial_ends_at=None,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tenant]
        self.session.execute = AsyncMock(return_value=mock_result)

        with patch.object(self.svc, "_send_notification", new_callable=AsyncMock):
            counts = await self.svc.process_expirations()

        assert counts["skipped"] == 1

    async def test_no_action_for_distant_expiry(self) -> None:
        future = datetime.now(timezone.utc) + timedelta(days=15)
        tenant = _make_tenant(
            billing_status=BillingStatus.ACTIVE.value,
            subscription_expires_at=future,
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [tenant]
        self.session.execute = AsyncMock(return_value=mock_result)

        with patch.object(self.svc, "_send_notification", new_callable=AsyncMock) as mock_notify:
            counts = await self.svc.process_expirations()

        assert counts["expired"] == 0
        assert counts["warnings_sent"] == 0
        assert counts["skipped"] == 0
        mock_notify.assert_not_awaited()
