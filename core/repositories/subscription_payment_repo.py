"""Subscription payment repository interface."""
from __future__ import annotations

from abc import abstractmethod
from typing import Any

from core.domain.subscription_payment import SubscriptionPayment
from core.repositories.base import BaseRepository
from shared.constants.enums import SubscriptionPaymentStatus


class AbstractSubscriptionPaymentRepository(BaseRepository[SubscriptionPayment, int]):
    """Contract for subscription payment persistence."""

    @abstractmethod
    async def get_by_id(self, id: int) -> SubscriptionPayment | None: ...

    @abstractmethod
    async def get_by_merchant_trans_id(
        self, merchant_trans_id: str, *, for_update: bool = False,
    ) -> SubscriptionPayment | None: ...

    @abstractmethod
    async def get_by_provider_trans_id(
        self, provider_trans_id: str, *, for_update: bool = False,
    ) -> SubscriptionPayment | None: ...

    @abstractmethod
    async def list_by_tenant(
        self, tenant_id: int, limit: int = 20,
    ) -> list[SubscriptionPayment]: ...

    @abstractmethod
    async def create(self, entity: SubscriptionPayment) -> SubscriptionPayment: ...

    @abstractmethod
    async def update_status(
        self,
        id: int,
        status: SubscriptionPaymentStatus,
        **kwargs: Any,
    ) -> SubscriptionPayment: ...
