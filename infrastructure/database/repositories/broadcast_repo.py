"""PostgreSQL implementation of AbstractBroadcastRepository (v2)."""
from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from core.domain.broadcast import Broadcast, SegmentFilter
from core.repositories.broadcast_repo import AbstractBroadcastRepository
from infrastructure.database.models.broadcast import BroadcastModel
from infrastructure.database.models.lead import LeadModel
from infrastructure.database.models.pipeline_stage import PipelineStageModel
from infrastructure.database.models.user import UserModel
from shared.constants.enums import BroadcastStatus, PayloadType, SegmentType


class PostgresBroadcastRepository(AbstractBroadcastRepository):
    """Concrete SQLAlchemy/PostgreSQL broadcast repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── helpers ───────────────────────────────────────────────────────────

    def _to_domain(self, model: BroadcastModel) -> Broadcast:
        return Broadcast(
            id=model.id,
            title=model.title,
            segment_type=model.segment_type
            if isinstance(model.segment_type, str)
            else model.segment_type.value,
            lead_stage=model.lead_stage,
            payload_type=model.payload_type
            if isinstance(model.payload_type, str)
            else model.payload_type.value,
            text=model.text,
            file_id=model.file_id,
            message_template=model.message_template or "",
            media_file_id=model.media_file_id,
            media_type=model.media_type,
            scheduled_at=model.scheduled_at,
            status=BroadcastStatus(model.status)
            if isinstance(model.status, str)
            else model.status,
            total=model.total,
            sent_count=model.sent_count,
            failed_count=model.failed_count,
            finished_at=model.finished_at,
            created_by=model.created_by,
            created_at=model.created_at,
        )

    # ── BaseRepository ────────────────────────────────────────────────────

    async def get_by_id(self, id: int) -> Broadcast | None:
        model = await self._session.get(BroadcastModel, id)
        return self._to_domain(model) if model else None

    async def create(self, entity: Broadcast) -> Broadcast:
        raise NotImplementedError("Use create_broadcast() for v2 creation.")

    async def update(self, entity: Broadcast) -> Broadcast:
        raise NotImplementedError

    async def delete(self, id: int) -> bool:
        stmt = sa.delete(BroadcastModel).where(BroadcastModel.id == id)
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    # ── legacy methods ────────────────────────────────────────────────────

    async def get_due_broadcasts(self, as_of: datetime) -> list[Broadcast]:
        stmt = (
            sa.select(BroadcastModel)
            .where(
                BroadcastModel.status == BroadcastStatus.SCHEDULED.value,
                BroadcastModel.scheduled_at <= as_of,
            )
        )
        result = await self._session.execute(stmt)
        return [self._to_domain(m) for m in result.scalars().all()]

    async def update_counts(
        self, broadcast_id: int, sent_delta: int, failed_delta: int
    ) -> None:
        stmt = (
            sa.update(BroadcastModel)
            .where(BroadcastModel.id == broadcast_id)
            .values(
                sent_count=BroadcastModel.sent_count + sent_delta,
                failed_count=BroadcastModel.failed_count + failed_delta,
            )
        )
        await self._session.execute(stmt)

    async def get_segment_user_ids(self, segment: SegmentFilter) -> list[int]:
        """Resolve legacy SegmentFilter → user IDs. Stub for now."""
        return await self.get_all_private_user_ids()

    async def estimate_segment_size(self, segment: SegmentFilter) -> int:
        ids = await self.get_segment_user_ids(segment)
        return len(ids)

    # ── v2 methods ────────────────────────────────────────────────────────

    async def create_broadcast(
        self,
        segment_type: SegmentType,
        payload_type: PayloadType,
        text: str | None,
        file_id: str | None,
        created_by: int,
        lead_stage: str | None = None,
    ) -> int:
        """Insert a new PENDING broadcast and return its ID."""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        title = f"Rassilka {segment_type.value} {ts}"

        # message_template is a legacy NOT NULL column; populate it from the
        # v2 text field so existing queries that read it still get a value.
        message_template = text or ""

        model = BroadcastModel(
            title=title,
            segment_type=segment_type.value,
            lead_stage=lead_stage,
            payload_type=payload_type.value,
            text=text,
            file_id=file_id,
            message_template=message_template,
            status=BroadcastStatus.PENDING.value,
            created_by=created_by,
        )
        self._session.add(model)
        await self._session.flush()
        return model.id

    async def mark_status(self, broadcast_id: int, status: BroadcastStatus) -> None:
        stmt = (
            sa.update(BroadcastModel)
            .where(BroadcastModel.id == broadcast_id)
            .values(status=status.value)
        )
        await self._session.execute(stmt)

    async def inc_sent(self, broadcast_id: int, n: int = 1) -> None:
        stmt = (
            sa.update(BroadcastModel)
            .where(BroadcastModel.id == broadcast_id)
            .values(sent_count=BroadcastModel.sent_count + n)
        )
        await self._session.execute(stmt)

    async def inc_failed(self, broadcast_id: int, n: int = 1) -> None:
        stmt = (
            sa.update(BroadcastModel)
            .where(BroadcastModel.id == broadcast_id)
            .values(failed_count=BroadcastModel.failed_count + n)
        )
        await self._session.execute(stmt)

    async def finalize(self, broadcast_id: int, finished_at: datetime) -> None:
        stmt = (
            sa.update(BroadcastModel)
            .where(BroadcastModel.id == broadcast_id)
            .values(finished_at=finished_at)
        )
        await self._session.execute(stmt)

    async def get_all_private_user_ids(self) -> list[int]:
        """Return IDs of all non-blocked users."""
        stmt = sa.select(UserModel.id).where(UserModel.is_blocked.is_(False))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_user_ids_by_stage(self, lead_stage: str) -> list[int]:
        """Return distinct user IDs whose current pipeline stage == lead_stage."""
        # Latest stage per lead: max(created_at) per lead_id
        max_dates = (
            sa.select(
                PipelineStageModel.lead_id.label("lead_id"),
                sa.func.max(PipelineStageModel.created_at).label("max_at"),
            )
            .group_by(PipelineStageModel.lead_id)
            .subquery("max_dates")
        )
        # The stage record at that timestamp
        latest_stages = (
            sa.select(
                PipelineStageModel.lead_id.label("lead_id"),
                PipelineStageModel.stage.label("stage"),
            )
            .join(
                max_dates,
                sa.and_(
                    PipelineStageModel.lead_id == max_dates.c.lead_id,
                    PipelineStageModel.created_at == max_dates.c.max_at,
                ),
            )
            .subquery("latest_stages")
        )
        stmt = (
            sa.select(LeadModel.user_id)
            .join(latest_stages, LeadModel.id == latest_stages.c.lead_id)
            .where(latest_stages.c.stage == lead_stage)
            .distinct()
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
