"""
Fire-and-forget tactic outcome logger.

Usage (from any handler / service):
    asyncio.create_task(log_tactic_outcome(
        event_type="negotiation",
        tactic_name="value_reframe",
        user_id=user_id,
        lead_id=lead_id,
        ...
    ))

Opens its own session, inserts one row, commits. Never raises.
"""

from __future__ import annotations

from shared.logging import get_logger

log = get_logger(__name__)


async def log_tactic_outcome(
    *,
    event_type: str,
    tactic_name: str,
    user_id: int,
    lead_id: int | None = None,
    objection_type: str | None = None,
    lead_score_at_time: int = 0,
    stage_at_time: str | None = None,
    lead_temperature_at_time: str | None = None,
) -> None:
    """Append one row to ai_tactic_outcomes. Never raises."""
    try:
        from infrastructure.database.session import get_session_factory
        from infrastructure.di import get_tactic_outcome_repo

        factory = get_session_factory()
        async with factory() as session:
            repo = get_tactic_outcome_repo(session)
            await repo.insert(
                lead_id=lead_id,
                user_id=user_id,
                event_type=event_type,
                tactic_name=tactic_name,
                objection_type=objection_type,
                lead_score_at_time=lead_score_at_time,
                stage_at_time=stage_at_time,
                lead_temperature_at_time=lead_temperature_at_time,
            )
            await session.commit()
    except Exception:
        log.warning(
            "tactic_outcome_log_failed",
            event_type=event_type,
            tactic_name=tactic_name,
            user_id=user_id,
        )
