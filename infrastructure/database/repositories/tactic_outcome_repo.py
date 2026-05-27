"""Concrete PostgreSQL repository for ai_tactic_outcomes."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from core.repositories.tactic_outcome_repo import AbstractTacticOutcomeRepository
from infrastructure.database.models.ai_tactic_outcome import AiTacticOutcomeModel
from shared.logging import get_logger

log = get_logger(__name__)


class PostgresTacticOutcomeRepository(AbstractTacticOutcomeRepository):
    """Append-mostly repository for AI tactic outcome tracking."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert(
        self,
        *,
        lead_id: int | None,
        user_id: int,
        event_type: str,
        tactic_name: str,
        objection_type: str | None = None,
        lead_score_at_time: int = 0,
        stage_at_time: str | None = None,
        lead_temperature_at_time: str | None = None,
    ) -> int | None:
        """Append one outcome row. Never raises."""
        try:
            row = AiTacticOutcomeModel(
                lead_id=lead_id,
                user_id=user_id,
                event_type=event_type,
                tactic_name=tactic_name,
                objection_type=objection_type,
                lead_score_at_time=lead_score_at_time,
                stage_at_time=stage_at_time,
                lead_temperature_at_time=lead_temperature_at_time,
            )
            self._session.add(row)
            await self._session.flush()
            return row.id
        except Exception:
            log.warning(
                "tactic_outcome_insert_error",
                user_id=user_id,
                event_type=event_type,
                tactic_name=tactic_name,
            )
            return None

    async def get_pending_outcomes(
        self,
        older_than: datetime,
        limit: int = 200,
    ) -> list[dict]:
        """Return pending outcomes created before *older_than*."""
        stmt = (
            sa.select(AiTacticOutcomeModel)
            .where(
                AiTacticOutcomeModel.outcome == "pending",
                AiTacticOutcomeModel.created_at < older_than,
            )
            .order_by(AiTacticOutcomeModel.created_at)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [
            {
                "id": r.id,
                "lead_id": r.lead_id,
                "user_id": r.user_id,
                "event_type": r.event_type,
                "tactic_name": r.tactic_name,
                "created_at": r.created_at,
            }
            for r in rows
        ]

    async def resolve_outcome(
        self,
        outcome_id: int,
        outcome: str,
        resolved_at: datetime,
    ) -> None:
        """Set outcome and resolved_at on a single row."""
        stmt = (
            sa.update(AiTacticOutcomeModel)
            .where(AiTacticOutcomeModel.id == outcome_id)
            .values(outcome=outcome, resolved_at=resolved_at)
        )
        await self._session.execute(stmt)

    async def get_resolved_stats(
        self,
        *,
        event_type: str | None = None,
        since: datetime | None = None,
        min_samples: int = 5,
    ) -> list[dict]:
        """Aggregate resolved outcomes into per-tactic stats."""
        t = AiTacticOutcomeModel

        filters = [t.outcome != "pending"]
        if event_type:
            filters.append(t.event_type == event_type)
        if since:
            filters.append(t.created_at >= since)

        total_col = sa.func.count().label("total")
        engaged_col = sa.func.count().filter(t.outcome == "engaged").label("engaged")
        meas_col = (
            sa.func.count().filter(t.outcome == "measurement_booked").label("measurement_booked")
        )
        conv_col = sa.func.count().filter(t.outcome == "converted").label("converted")
        lost_col = sa.func.count().filter(t.outcome == "lost").label("lost")
        ignored_col = sa.func.count().filter(t.outcome == "ignored").label("ignored")

        stmt = (
            sa.select(
                t.event_type,
                t.tactic_name,
                t.objection_type,
                t.lead_temperature_at_time.label("segment"),
                total_col,
                engaged_col,
                meas_col,
                conv_col,
                lost_col,
                ignored_col,
            )
            .where(*filters)
            .group_by(
                t.event_type,
                t.tactic_name,
                t.objection_type,
                t.lead_temperature_at_time,
            )
            .having(sa.func.count() >= min_samples)
        )

        result = await self._session.execute(stmt)
        rows = result.all()

        stats: list[dict] = []
        for r in rows:
            total = r.total or 1
            success = (r.engaged or 0) + (r.measurement_booked or 0) + (r.converted or 0)
            stats.append(
                {
                    "event_type": r.event_type,
                    "tactic_name": r.tactic_name,
                    "objection_type": r.objection_type,
                    "segment": r.segment,
                    "total": total,
                    "engaged": r.engaged or 0,
                    "measurement_booked": r.measurement_booked or 0,
                    "converted": r.converted or 0,
                    "lost": r.lost or 0,
                    "ignored": r.ignored or 0,
                    "success_rate": success / total,
                }
            )
        return stats
