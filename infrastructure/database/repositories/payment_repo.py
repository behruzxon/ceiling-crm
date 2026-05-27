"""PostgreSQL implementation of AbstractPaymentRepository."""
from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.payment import Payment
from core.repositories.payment_repo import AbstractPaymentRepository
from infrastructure.database.models.payment import PaymentModel
from shared.constants.enums import PaymentStatus


class PostgresPaymentRepository(AbstractPaymentRepository):
    """Concrete SQLAlchemy/PostgreSQL payment repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Mapping ───────────────────────────────────────────────────────────

    def _to_domain(self, model: PaymentModel) -> Payment:
        return Payment(
            id=model.id,
            lead_id=model.lead_id,
            amount=model.amount,
            method=model.method,
            status=model.status,
            paid_at=model.paid_at,
            receipt_url=model.receipt_url,
            notes=model.notes,
            proof_file_id=model.proof_file_id,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    # ── Reads ─────────────────────────────────────────────────────────────

    async def get_by_id(self, id: int) -> Payment | None:
        model = await self._session.get(PaymentModel, id)
        return self._to_domain(model) if model else None

    async def list_by_lead(self, lead_id: int) -> list[Payment]:
        result = await self._session.execute(
            sa.select(PaymentModel)
            .where(PaymentModel.lead_id == lead_id)
            .order_by(PaymentModel.created_at)
        )
        return [self._to_domain(row) for row in result.scalars().all()]

    # ── Writes ────────────────────────────────────────────────────────────

    async def create(self, entity: Payment) -> Payment:
        model = PaymentModel(
            lead_id=entity.lead_id,
            amount=entity.amount,
            method=entity.method,
            status=entity.status,
            paid_at=entity.paid_at,
            receipt_url=entity.receipt_url,
            notes=entity.notes,
            proof_file_id=entity.proof_file_id,
            created_by=entity.created_by,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_domain(model)

    async def update_status(
        self,
        id: int,
        status: PaymentStatus,
        *,
        expected_status: PaymentStatus | None = None,
    ) -> Payment:
        if expected_status is not None:
            # Lock the row and verify current status atomically.
            result = await self._session.execute(
                sa.select(PaymentModel)
                .where(PaymentModel.id == id)
                .with_for_update()
            )
            model = result.scalar_one_or_none()
        else:
            model = await self._session.get(PaymentModel, id)

        if model is None:
            raise ValueError(f"Payment {id} not found")

        if expected_status is not None and model.status != expected_status:
            raise ValueError(
                f"Payment {id} status is '{model.status}', expected '{expected_status.value}'"
            )

        model.status = status
        if status == PaymentStatus.PAID and model.paid_at is None:
            model.paid_at = datetime.now(tz=UTC)
        await self._session.flush()
        # onupdate=func.now() expires `updated_at` server-side after flush;
        # refresh fetches the new value via an awaited SELECT, avoiding
        # the MissingGreenlet error that sync lazy-load would trigger.
        await self._session.refresh(model)
        return self._to_domain(model)

    async def update(self, entity: Payment) -> Payment:
        model = await self._session.get(PaymentModel, entity.id)
        if model is None:
            raise ValueError(f"Payment {entity.id} not found")
        model.amount = entity.amount
        model.method = entity.method
        model.status = entity.status
        model.paid_at = entity.paid_at
        model.receipt_url = entity.receipt_url
        model.notes = entity.notes
        await self._session.flush()
        await self._session.refresh(model)  # same reason as update_status above
        return self._to_domain(model)

    async def delete(self, id: int) -> bool:
        result = await self._session.execute(
            sa.delete(PaymentModel).where(PaymentModel.id == id)
        )
        return result.rowcount > 0
