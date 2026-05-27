"""Abstract repository interface for payment records."""

from __future__ import annotations

from abc import abstractmethod

from core.domain.payment import Payment
from core.repositories.base import BaseRepository
from shared.constants.enums import PaymentStatus


class AbstractPaymentRepository(BaseRepository[Payment, int]):

    @abstractmethod
    async def get_by_id(self, id: int) -> Payment | None: ...

    @abstractmethod
    async def list_by_lead(self, lead_id: int) -> list[Payment]:
        """Return all payments for *lead_id*, ordered by created_at asc."""
        ...

    @abstractmethod
    async def create(self, entity: Payment) -> Payment: ...

    @abstractmethod
    async def update_status(
        self,
        id: int,
        status: PaymentStatus,
        *,
        expected_status: PaymentStatus | None = None,
    ) -> Payment:
        """Update status (and set paid_at when transitioning to PAID).

        When *expected_status* is given the row is locked with SELECT FOR UPDATE
        and the transition is rejected if the current status does not match.
        Raises ValueError if not found or if the expected status does not match.
        """
        ...

    @abstractmethod
    async def update(self, entity: Payment) -> Payment: ...

    @abstractmethod
    async def delete(self, id: int) -> bool: ...
