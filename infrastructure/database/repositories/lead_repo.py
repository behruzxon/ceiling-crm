"""PostgreSQL implementation of AbstractLeadRepository."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
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
            package_type=model.package_type,
            lead_status=model.lead_status,
            last_action=model.last_action,
            score=model.score or 0,
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

    async def upsert_package_lead(
        self,
        user_id: int,
        package_type: str,
        first_name: str,
        score_delta: int,
        lead_status: str,
    ) -> Lead:
        """Create or update a lead when the user selects a package.

        Finds the most recent lead for *user_id* and updates its package
        fields + increments score.  If no lead exists yet, inserts a minimal
        placeholder (name = first_name, phone = '—', district = 'Noma'lum').
        """
        stmt = (
            select(LeadModel)
            .where(LeadModel.user_id == user_id)
            .order_by(LeadModel.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is not None:
            update_stmt = (
                update(LeadModel)
                .where(LeadModel.id == model.id)
                .values(
                    package_type=package_type,
                    lead_status=lead_status,
                    last_action="package_order",
                    score=LeadModel.score + score_delta,
                    updated_at=datetime.now(timezone.utc),
                )
                .returning(LeadModel)
            )
            res = await self._session.execute(update_stmt)
            model = res.scalar_one()
            return self._to_domain(model, PipelineStage.PACKAGE_SELECTED)

        # No existing lead — create minimal placeholder
        model = LeadModel(
            user_id=user_id,
            category=CeilingCategory.ODNOTONNY.value,
            source=LeadSource.DEEPLINK.value,
            name=first_name,
            phone="—",
            district="Noma'lum",
            package_type=package_type,
            lead_status=lead_status,
            last_action="package_order",
            score=score_delta,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_domain(model, PipelineStage.NEW)

    async def update_lead_status(self, lead_id: int, lead_status: str) -> None:
        """Update the lead_status column (hot / warm / cold / blocked)."""
        stmt = (
            update(LeadModel)
            .where(LeadModel.id == lead_id)
            .values(lead_status=lead_status, updated_at=datetime.now(timezone.utc))
        )
        await self._session.execute(stmt)

    async def update_last_action(self, lead_id: int, last_action: str) -> None:
        """Stamp leads.last_action with *last_action*. Used for dedupe markers."""
        stmt = (
            update(LeadModel)
            .where(LeadModel.id == lead_id)
            .values(last_action=last_action, updated_at=datetime.now(timezone.utc))
        )
        await self._session.execute(stmt)

    # ── Kanban helpers ─────────────────────────────────────────────────────────

    # Map kanban bucket → pipeline stage values stored in pipeline_stages.stage
    _KANBAN_PIPELINE_MAP: dict[str, list[str]] = {
        "new":         [PipelineStage.NEW.value, PipelineStage.PACKAGE_SELECTED.value],
        "hot":         [PipelineStage.CONTACTED.value],
        "measurement": [PipelineStage.MEASUREMENT.value, PipelineStage.QUOTE.value],
        "won":         [PipelineStage.DEAL.value, PipelineStage.INSTALLATION.value, PipelineStage.COMPLETED.value],
        "lost":        [PipelineStage.LOST.value],
    }

    async def get_counts_by_stage(self) -> dict[str, int]:
        """Return lead counts grouped into 5 kanban buckets.

        Uses an OUTER JOIN so leads with no pipeline_stages row fall into 'new'.
        """
        latest = (
            select(
                PipelineStageModel.lead_id,
                PipelineStageModel.stage,
            )
            .distinct(PipelineStageModel.lead_id)
            .order_by(PipelineStageModel.lead_id, PipelineStageModel.created_at.desc())
            .subquery("latest_stage_kb")
        )

        stage_col = latest.c.stage
        kanban_expr = sa.case(
            (stage_col.in_(["CONTACTED"]), "hot"),
            (stage_col.in_(["MEASUREMENT", "QUOTE"]), "measurement"),
            (stage_col.in_(["DEAL", "INSTALLATION", "COMPLETED"]), "won"),
            (stage_col == "LOST", "lost"),
            else_="new",  # NEW, PACKAGE_SELECTED and NULL (no stage) → new
        )

        stmt = (
            select(kanban_expr.label("kanban_stage"), func.count().label("cnt"))
            .select_from(LeadModel)
            .outerjoin(latest, LeadModel.id == latest.c.lead_id)
            .group_by("kanban_stage")
        )

        result = await self._session.execute(stmt)
        counts: dict[str, int] = {
            "new": 0, "hot": 0, "measurement": 0, "won": 0, "lost": 0,
        }
        for kanban_stage, cnt in result.all():
            if kanban_stage in counts:
                counts[kanban_stage] = cnt
        return counts

    async def get_leads_by_kanban_stage(
        self,
        kanban_stage: str,
        limit: int = 10,
        offset: int = 0,
    ) -> list[Lead]:
        """Return leads for a kanban bucket, newest-first.

        For the 'new' bucket an OUTER JOIN is used so leads with no
        pipeline_stages record are included.
        """
        pipeline_stages = self._KANBAN_PIPELINE_MAP.get(
            kanban_stage.lower(), [PipelineStage.NEW.value]
        )

        latest = (
            select(
                PipelineStageModel.lead_id,
                PipelineStageModel.stage,
            )
            .distinct(PipelineStageModel.lead_id)
            .order_by(PipelineStageModel.lead_id, PipelineStageModel.created_at.desc())
            .subquery("latest_stage_kb2")
        )

        if kanban_stage.lower() == "new":
            stmt = (
                select(LeadModel, latest.c.stage)
                .outerjoin(latest, LeadModel.id == latest.c.lead_id)
                .where(
                    sa.or_(
                        latest.c.stage.in_(pipeline_stages),
                        latest.c.stage.is_(None),
                    )
                )
                .order_by(LeadModel.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
        else:
            stmt = (
                select(LeadModel, latest.c.stage)
                .join(latest, LeadModel.id == latest.c.lead_id)
                .where(latest.c.stage.in_(pipeline_stages))
                .order_by(LeadModel.created_at.desc())
                .limit(limit)
                .offset(offset)
            )

        rows = (await self._session.execute(stmt)).all()
        leads: list[Lead] = []
        for row in rows:
            model: LeadModel = row[0]
            stage_val: str | None = row[1]
            stage = PipelineStage(stage_val) if stage_val else PipelineStage.NEW
            leads.append(self._to_domain(model, stage))
        return leads
