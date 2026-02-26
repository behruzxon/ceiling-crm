"""PostgreSQL implementation of AbstractLeadRepository."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.lead import Lead, LeadAddons
from core.repositories.lead_repo import AbstractLeadRepository
from infrastructure.database.models.lead import LeadModel
from infrastructure.database.models.pipeline_stage import PipelineStageModel
from shared.constants.enums import CeilingCategory, LeadSource, PipelineStage


class PostgresLeadRepository(AbstractLeadRepository):
    """Concrete SQLAlchemy/PostgreSQL lead repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _to_domain(self, model: LeadModel, current_stage: PipelineStage | None = None) -> Lead:
        """Convert ORM model to immutable domain object."""
        addons_data = model.addons or {}
        return Lead(
            id=model.id,
            user_id=model.user_id,
            category=CeilingCategory(model.category) if isinstance(model.category, str) else model.category,
            source=LeadSource(model.source) if isinstance(model.source, str) else model.source,
            source_group_id=model.source_group_id,
            name=model.name,
            phone=model.phone,
            district=model.district,
            room_length=model.room_length,
            room_width=model.room_width,
            room_area=model.room_area,
            addons=LeadAddons(**addons_data) if addons_data else LeadAddons(),
            notes=model.notes,
            utm_source=model.utm_source,
            utm_campaign=model.utm_campaign,
            assigned_manager_id=model.assigned_manager_id,
            current_stage=current_stage or PipelineStage.NEW,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _latest_stage_subquery(self) -> select:
        """Subquery: latest pipeline stage per lead."""
        return (
            select(
                PipelineStageModel.lead_id,
                PipelineStageModel.stage,
            )
            .distinct(PipelineStageModel.lead_id)
            .order_by(PipelineStageModel.lead_id, PipelineStageModel.created_at.desc())
            .subquery("latest_stage")
        )

    async def _get_current_stage(self, lead_id: int) -> PipelineStage | None:
        """Fetch current pipeline stage for a single lead."""
        stmt = (
            select(PipelineStageModel.stage)
            .where(PipelineStageModel.lead_id == lead_id)
            .order_by(PipelineStageModel.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return PipelineStage(row) if isinstance(row, str) else row

    async def get_by_id(self, id: int) -> Lead | None:
        model = await self._session.get(LeadModel, id)
        if model is None:
            return None
        stage = await self._get_current_stage(id)
        return self._to_domain(model, stage or PipelineStage.NEW)

    async def get_by_user_id(self, user_id: int) -> list[Lead]:
        stmt = select(LeadModel).where(LeadModel.user_id == user_id).order_by(LeadModel.created_at.desc())
        result = await self._session.execute(stmt)
        leads = []
        for model in result.scalars().all():
            stage = await self._get_current_stage(model.id)
            leads.append(self._to_domain(model, stage or PipelineStage.NEW))
        return leads

    async def list_by_user(self, user_id: int, limit: int = 5) -> list[Lead]:
        stmt = (
            select(LeadModel)
            .where(LeadModel.user_id == user_id)
            .order_by(LeadModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        leads = []
        for model in result.scalars().all():
            stage = await self._get_current_stage(model.id)
            leads.append(self._to_domain(model, stage or PipelineStage.NEW))
        return leads

    async def get_by_stage(self, stage: PipelineStage) -> list[Lead]:
        latest = self._latest_stage_subquery()
        stmt = (
            select(LeadModel)
            .join(latest, LeadModel.id == latest.c.lead_id)
            .where(latest.c.stage == stage.value)
            .order_by(LeadModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m, stage) for m in result.scalars().all()]

    async def get_by_category(self, category: CeilingCategory) -> list[Lead]:
        stmt = (
            select(LeadModel)
            .where(LeadModel.category == category)
            .order_by(LeadModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        leads = []
        for model in result.scalars().all():
            stage = await self._get_current_stage(model.id)
            leads.append(self._to_domain(model, stage or PipelineStage.NEW))
        return leads

    async def get_stale_new_leads(self, older_than_minutes: int) -> list[Lead]:
        """Return NEW leads with no stage change in the given minutes."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
        latest = self._latest_stage_subquery()
        stmt = (
            select(LeadModel)
            .join(latest, LeadModel.id == latest.c.lead_id)
            .where(
                latest.c.stage == PipelineStage.NEW.value,
                LeadModel.created_at < cutoff,
            )
            .order_by(LeadModel.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m, PipelineStage.NEW) for m in result.scalars().all()]

    async def assign_manager(self, lead_id: int, manager_id: int) -> Lead:
        stmt = (
            update(LeadModel)
            .where(LeadModel.id == lead_id)
            .values(
                assigned_manager_id=manager_id,
                updated_at=datetime.now(timezone.utc),
            )
            .returning(LeadModel)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one()
        stage = await self._get_current_stage(lead_id)
        return self._to_domain(model, stage or PipelineStage.NEW)

    async def get_pipeline_counts(self) -> dict[PipelineStage, int]:
        latest = self._latest_stage_subquery()
        stmt = (
            select(latest.c.stage, func.count())
            .group_by(latest.c.stage)
        )
        result = await self._session.execute(stmt)
        counts: dict[PipelineStage, int] = {}
        for stage_val, count in result.all():
            counts[PipelineStage(stage_val)] = count
        return counts

    async def search(
        self,
        *,
        category: CeilingCategory | None = None,
        stage: PipelineStage | None = None,
        district: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Lead]:
        stmt = select(LeadModel)

        if category is not None:
            stmt = stmt.where(LeadModel.category == category)
        if district is not None:
            stmt = stmt.where(LeadModel.district.ilike(f"%{district}%"))
        if created_after is not None:
            stmt = stmt.where(LeadModel.created_at >= created_after)
        if created_before is not None:
            stmt = stmt.where(LeadModel.created_at <= created_before)

        if stage is not None:
            latest = self._latest_stage_subquery()
            stmt = stmt.join(latest, LeadModel.id == latest.c.lead_id).where(
                latest.c.stage == stage.value
            )

        stmt = stmt.order_by(LeadModel.created_at.desc()).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        leads = []
        for model in result.scalars().all():
            s = await self._get_current_stage(model.id) if stage is None else stage
            leads.append(self._to_domain(model, s or PipelineStage.NEW))
        return leads

    async def create(self, entity: Lead) -> Lead:
        model = LeadModel(
            user_id=entity.user_id,
            category=entity.category.value,
            source=entity.source.value,
            source_group_id=entity.source_group_id,
            name=entity.name,
            phone=entity.phone,
            district=entity.district,
            room_length=entity.room_length,
            room_width=entity.room_width,
            room_area=entity.room_area,
            addons=entity.addons.model_dump() if entity.addons else {},
            notes=entity.notes,
            utm_source=entity.utm_source,
            utm_campaign=entity.utm_campaign,
            assigned_manager_id=entity.assigned_manager_id,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_domain(model, PipelineStage.NEW)

    async def update(self, entity: Lead) -> Lead:
        stmt = (
            update(LeadModel)
            .where(LeadModel.id == entity.id)
            .values(
                name=entity.name,
                phone=entity.phone,
                district=entity.district,
                room_length=entity.room_length,
                room_width=entity.room_width,
                room_area=entity.room_area,
                addons=entity.addons.model_dump() if entity.addons else {},
                notes=entity.notes,
                assigned_manager_id=entity.assigned_manager_id,
                updated_at=datetime.now(timezone.utc),
            )
            .returning(LeadModel)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one()
        stage = await self._get_current_stage(entity.id)
        return self._to_domain(model, stage or PipelineStage.NEW)

    async def delete(self, id: int) -> bool:
        model = await self._session.get(LeadModel, id)
        if model is None:
            return False
        await self._session.delete(model)
        return True
