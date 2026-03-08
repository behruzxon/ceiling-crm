"""PostgreSQL implementation of AbstractPipelineRepository."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.repositories.pipeline_repo import AbstractPipelineRepository, PipelineRecord
from infrastructure.database.models.pipeline_stage import PipelineStageModel
from infrastructure.database.repositories.tenant_scope import TenantScopedRepository
from shared.constants.enums import PipelineStage


class PostgresPipelineRepository(TenantScopedRepository, AbstractPipelineRepository):
    """Concrete SQLAlchemy/PostgreSQL pipeline repository."""

    def __init__(self, session: AsyncSession, tenant_id: int | None = None) -> None:
        super().__init__(session, tenant_id)

    def _to_record(self, model: PipelineStageModel) -> PipelineRecord:
        record = PipelineRecord()
        record.lead_id = model.lead_id
        record.stage = PipelineStage(model.stage) if isinstance(model.stage, str) else model.stage
        record.changed_by = model.changed_by
        record.note = model.note
        record.created_at = model.created_at
        return record

    async def insert_stage(
        self,
        lead_id: int,
        stage: PipelineStage,
        changed_by: int,
        note: str | None = None,
    ) -> PipelineRecord:
        model = PipelineStageModel(
            lead_id=lead_id,
            stage=stage.value,
            changed_by=changed_by,
            note=note,
        )
        self._stamp_tenant_id(model)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_record(model)

    async def get_history(self, lead_id: int) -> list[PipelineRecord]:
        stmt = (
            select(PipelineStageModel)
            .where(PipelineStageModel.lead_id == lead_id)
            .order_by(PipelineStageModel.created_at.asc())
        )
        stmt = self._apply_tenant_filter(stmt, PipelineStageModel)
        result = await self._session.execute(stmt)
        return [self._to_record(m) for m in result.scalars().all()]

    async def get_current_stage(self, lead_id: int) -> PipelineStage | None:
        stmt = (
            select(PipelineStageModel.stage)
            .where(PipelineStageModel.lead_id == lead_id)
            .order_by(PipelineStageModel.created_at.desc())
            .limit(1)
        )
        stmt = self._apply_tenant_filter(stmt, PipelineStageModel)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return PipelineStage(row) if isinstance(row, str) else row

    async def get_by_id(self, id: int) -> PipelineRecord | None:
        model = await self._session.get(PipelineStageModel, id)
        if model is None:
            return None
        if self._tenant_id is not None and model.tenant_id != self._tenant_id:
            return None
        return self._to_record(model)

    async def create(self, entity: PipelineRecord) -> PipelineRecord:
        return await self.insert_stage(
            lead_id=entity.lead_id,
            stage=entity.stage,
            changed_by=entity.changed_by,
            note=entity.note,
        )

    async def update(self, entity: PipelineRecord) -> PipelineRecord:
        raise NotImplementedError("Pipeline records are immutable (event-sourced)")

    async def delete(self, id: int) -> bool:
        raise NotImplementedError("Pipeline records are immutable (event-sourced)")
