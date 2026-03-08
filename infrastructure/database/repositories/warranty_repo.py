"""PostgreSQL implementation of AbstractWarrantyRepository."""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.warranty import Warranty
from core.repositories.warranty_repo import AbstractWarrantyRepository
from infrastructure.database.models.warranty import WarrantyModel
from infrastructure.database.repositories.tenant_scope import TenantScopedRepository


class PostgresWarrantyRepository(TenantScopedRepository, AbstractWarrantyRepository):
    """Concrete SQLAlchemy/PostgreSQL warranty repository."""

    def __init__(self, session: AsyncSession, tenant_id: int | None = None) -> None:
        super().__init__(session, tenant_id)

    # ── Mapping ───────────────────────────────────────────────────────────

    def _to_domain(self, model: WarrantyModel) -> Warranty:
        return Warranty(
            id=model.id,
            lead_id=model.lead_id,
            issued_at=model.issued_at,
            expires_at=model.expires_at,
            warranty_card_no=model.warranty_card_no,
            notes=model.notes,
            created_by=model.created_by,
            created_at=model.created_at,
        )

    # ── Reads ─────────────────────────────────────────────────────────────

    async def get_by_id(self, id: int) -> Warranty | None:
        model = await self._session.get(WarrantyModel, id)
        if model is None:
            return None
        if self._tenant_id is not None and model.tenant_id != self._tenant_id:
            return None
        return self._to_domain(model)

    async def get_by_lead(self, lead_id: int) -> Warranty | None:
        stmt = sa.select(WarrantyModel).where(WarrantyModel.lead_id == lead_id)
        stmt = self._apply_tenant_filter(stmt, WarrantyModel)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model else None

    # ── Writes ────────────────────────────────────────────────────────────

    async def create(self, entity: Warranty) -> Warranty:
        model = WarrantyModel(
            lead_id=entity.lead_id,
            issued_at=entity.issued_at,
            expires_at=entity.expires_at,
            warranty_card_no=entity.warranty_card_no,
            notes=entity.notes,
            created_by=entity.created_by,
        )
        self._stamp_tenant_id(model)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_domain(model)

    async def update(self, entity: Warranty) -> Warranty:
        model = await self._session.get(WarrantyModel, entity.id)
        if model is None:
            raise ValueError(f"Warranty {entity.id} not found")
        if self._tenant_id is not None and model.tenant_id != self._tenant_id:
            raise ValueError(f"Warranty {entity.id} not found")
        model.issued_at = entity.issued_at
        model.expires_at = entity.expires_at
        model.warranty_card_no = entity.warranty_card_no
        model.notes = entity.notes
        await self._session.flush()
        return self._to_domain(model)

    async def delete(self, id: int) -> bool:
        stmt = sa.delete(WarrantyModel).where(WarrantyModel.id == id)
        if self._tenant_id is not None:
            stmt = stmt.where(WarrantyModel.tenant_id == self._tenant_id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0
