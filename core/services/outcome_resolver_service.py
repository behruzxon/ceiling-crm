"""
Outcome resolver — resolves pending tactic outcomes by checking lead progression.

Resolution logic:
  1. Converted:  lead stage → DEAL / INSTALLATION / COMPLETED within 7 days
  2. Measurement: lead stage → MEASUREMENT / QUOTE within 24 hours
  3. Lost:        lead stage → LOST or lead_status = "lost" within 7 days
  4. Engaged:     ai_user_memory.updated_at > outcome.created_at within 6 hours
  5. Ignored:     none of the above after 24 hours
  6. Skip:        < 1 hour old — leave pending

Batch size: 200 per cycle, run every 5 minutes by scheduler.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from shared.logging import get_logger

log = get_logger(__name__)

# Minimum age before resolving (avoid premature resolution)
_MIN_AGE = timedelta(hours=1)

# Windows for each resolution type
_CONVERTED_WINDOW = timedelta(days=7)
_MEASUREMENT_WINDOW = timedelta(hours=24)
_LOST_WINDOW = timedelta(days=7)
_ENGAGED_WINDOW = timedelta(hours=6)
_IGNORED_THRESHOLD = timedelta(hours=24)

# Pipeline stages that count as conversion
_CONVERTED_STAGES = frozenset({"deal", "installation", "completed"})
_MEASUREMENT_STAGES = frozenset({"measurement", "quote"})


class OutcomeResolverService:
    """Resolve pending AI tactic outcomes by checking lead/user state."""

    async def resolve_pending_outcomes(self) -> int:
        """Process up to 200 pending outcomes. Returns resolved count."""
        from infrastructure.database.session import get_session_factory
        from infrastructure.di import get_tactic_outcome_repo

        now = datetime.now(timezone.utc)
        older_than = now - _MIN_AGE  # only outcomes >= 1h old

        factory = get_session_factory()
        resolved = 0

        try:
            async with factory() as session:
                repo = get_tactic_outcome_repo(session)
                pending = await repo.get_pending_outcomes(older_than, limit=200)

                if not pending:
                    return 0

                for row in pending:
                    outcome = await self._resolve_one(
                        row, now, session,
                    )
                    if outcome:
                        await repo.resolve_outcome(row["id"], outcome, now)
                        resolved += 1

                await session.commit()
        except Exception:
            log.exception("outcome_resolver_error")

        if resolved:
            log.info("outcomes_resolved", count=resolved, total_pending=len(pending))
        return resolved

    async def _resolve_one(
        self,
        row: dict,
        now: datetime,
        session: object,
    ) -> str | None:
        """Determine outcome for one pending row. Returns outcome string or None (leave pending)."""
        created_at: datetime = row["created_at"]
        lead_id: int | None = row.get("lead_id")
        user_id: int = row["user_id"]
        age = now - created_at

        # 1. Check lead stage transitions (if lead exists)
        if lead_id:
            stage = await self._get_latest_stage(lead_id, session)
            if stage:
                stage_lower = stage.lower() if isinstance(stage, str) else stage.value.lower()

                # Converted: DEAL / INSTALLATION / COMPLETED
                if stage_lower in _CONVERTED_STAGES and age <= _CONVERTED_WINDOW:
                    return "converted"

                # Measurement booked: MEASUREMENT / QUOTE
                if stage_lower in _MEASUREMENT_STAGES and age <= _MEASUREMENT_WINDOW:
                    return "measurement_booked"

                # Lost: stage is LOST
                if stage_lower == "lost" and age <= _LOST_WINDOW:
                    return "lost"

            # Also check lead_status for "lost"
            lead_status = await self._get_lead_status(lead_id, session)
            if lead_status and lead_status.lower() == "lost" and age <= _LOST_WINDOW:
                return "lost"

        # 2. Check user engagement (replied after tactic)
        if age <= _ENGAGED_WINDOW:
            engaged = await self._check_user_engaged(user_id, created_at)
            if engaged:
                return "engaged"

        # 3. Too old + no positive signal → ignored
        if age > _IGNORED_THRESHOLD:
            return "ignored"

        # 4. Still within windows, leave pending
        return None

    @staticmethod
    async def _get_latest_stage(lead_id: int, session: object) -> str | None:
        """Get the latest pipeline stage for a lead."""
        import sqlalchemy as sa
        from infrastructure.database.models.pipeline_stage import PipelineStageModel

        stmt = (
            sa.select(PipelineStageModel.stage)
            .where(PipelineStageModel.lead_id == lead_id)
            .order_by(PipelineStageModel.created_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)  # type: ignore[union-attr]
        row = result.scalar_one_or_none()
        return row

    @staticmethod
    async def _get_lead_status(lead_id: int, session: object) -> str | None:
        """Get lead_status from leads table."""
        import sqlalchemy as sa
        from infrastructure.database.models.lead import LeadModel

        stmt = (
            sa.select(LeadModel.lead_status)
            .where(LeadModel.id == lead_id)
        )
        result = await session.execute(stmt)  # type: ignore[union-attr]
        return result.scalar_one_or_none()

    @staticmethod
    async def _check_user_engaged(user_id: int, after: datetime) -> bool:
        """Check if user interacted after the tactic was applied (via AI memory)."""
        try:
            from infrastructure.cache.client import get_redis
            from infrastructure.cache.keys import CacheKeys
            import json

            redis = get_redis()
            raw = await redis.get(CacheKeys.ai_memory(user_id))
            if not raw:
                return False

            mem = json.loads(raw)
            updated_at = mem.get("updated_at")
            if not updated_at:
                return False

            # Parse ISO timestamp
            if isinstance(updated_at, str):
                from datetime import datetime as dt
                mem_ts = dt.fromisoformat(updated_at)
            elif isinstance(updated_at, (int, float)):
                mem_ts = datetime.fromtimestamp(updated_at, tz=timezone.utc)
            else:
                return False

            return mem_ts > after
        except Exception:
            return False
