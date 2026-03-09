"""PostgreSQL implementation of AbstractSubscriptionPaymentRepository."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.subscription_payment import SubscriptionPayment
from core.repositories.subscription_payment_repo import AbstractSubscriptionPaymentRepository
from infrastructure.database.models.subscription_payment import SubscriptionPaymentModel
from infrastructure.database.repositories.tenant_scope import TenantScopedRepository
from shared.constants.enums import SubscriptionPaymentStatus


class PostgresSubscriptionPaymentRepository(TenantScopedRepository, AbstractSubscriptionPaymentRepository):
    """Concrete SQLAlchemy/PostgreSQL subscription payment repository."""

    def __init__(self, session: AsyncSession, tenant_id: int | None = None) -> None:
        super().__init__(session, tenant_id)

    # ── Mapping ───────────────────────────────────────────────────────────

    @staticmethod
    def _to_domain(model: SubscriptionPaymentModel) -> SubscriptionPayment:
        return SubscriptionPayment(
            id=model.id,
            tenant_id=model.tenant_id,
            provider=model.provider,
            status=model.status,
            amount=model.amount,
            currency=model.currency,
            description=model.description,
            merchant_trans_id=model.merchant_trans_id,
            provider_trans_id=model.provider_trans_id,
            extension_days=model.extension_days,
            paid_at=model.paid_at,
            canceled_at=model.canceled_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
            provider_meta=model.provider_meta,
        )

    # ── Reads ─────────────────────────────────────────────────────────────

    async def get_by_id(self, id: int) -> SubscriptionPayment | None:
        model = await self._session.get(SubscriptionPaymentModel, id)
        if model is None:
            return None
        if self._tenant_id is not None and model.tenant_id != self._tenant_id:
            return None
        return self._to_domain(model)

    async def get_by_merchant_trans_id(
        self, merchant_trans_id: str,
    ) -> SubscriptionPayment | None:
        stmt = sa.select(SubscriptionPaymentModel).where(
            SubscriptionPaymentModel.merchant_trans_id == merchant_trans_id,
        )
        stmt = self._apply_tenant_filter(stmt, SubscriptionPaymentModel)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def get_by_provider_trans_id(
        self, provider_trans_id: str,
    ) -> SubscriptionPayment | None:
        stmt = sa.select(SubscriptionPaymentModel).where(
            SubscriptionPaymentModel.provider_trans_id == provider_trans_id,
        )
        stmt = self._apply_tenant_filter(stmt, SubscriptionPaymentModel)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    async def list_by_tenant(
        self, tenant_id: int, limit: int = 20,
    ) -> list[SubscriptionPayment]:
        tid = self._resolve_tenant_id(tenant_id)
        assert tid is not None, "tenant_id required for list_by_tenant"
        stmt = (
            sa.select(SubscriptionPaymentModel)
            .where(SubscriptionPaymentModel.tenant_id == tid)
            .order_by(SubscriptionPaymentModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    # ── Writes ────────────────────────────────────────────────────────────

    async def create(self, entity: SubscriptionPayment) -> SubscriptionPayment:
        model = SubscriptionPaymentModel(
            tenant_id=entity.tenant_id,
            provider=entity.provider,
            status=entity.status,
            amount=entity.amount,
            currency=entity.currency,
            description=entity.description,
            merchant_trans_id=entity.merchant_trans_id,
            provider_trans_id=entity.provider_trans_id,
            extension_days=entity.extension_days,
            provider_meta=entity.provider_meta,
        )
        self._stamp_tenant_id(model)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_domain(model)

    async def update_status(
        self,
        id: int,
        status: SubscriptionPaymentStatus,
        **kwargs: Any,
    ) -> SubscriptionPayment:
        model = await self._session.get(SubscriptionPaymentModel, id)
        if model is None:
            raise ValueError(f"SubscriptionPayment {id} not found")
        if self._tenant_id is not None and model.tenant_id != self._tenant_id:
            raise ValueError(f"SubscriptionPayment {id} not found")

        model.status = status.value

        if status == SubscriptionPaymentStatus.PAID and model.paid_at is None:
            model.paid_at = kwargs.get("paid_at", datetime.now(tz=timezone.utc))
        if status == SubscriptionPaymentStatus.CANCELED and model.canceled_at is None:
            model.canceled_at = datetime.now(tz=timezone.utc)

        if "provider_trans_id" in kwargs:
            model.provider_trans_id = kwargs["provider_trans_id"]
        if "provider_meta" in kwargs:
            model.provider_meta = {**model.provider_meta, **kwargs["provider_meta"]}

        await self._session.flush()
        await self._session.refresh(model)
        return self._to_domain(model)

    async def update(self, entity: SubscriptionPayment) -> SubscriptionPayment:
        raise NotImplementedError("Use update_status() instead")

    async def delete(self, id: int) -> bool:
        stmt = sa.delete(SubscriptionPaymentModel).where(
            SubscriptionPaymentModel.id == id,
        )
        if self._tenant_id is not None:
            stmt = stmt.where(SubscriptionPaymentModel.tenant_id == self._tenant_id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0
