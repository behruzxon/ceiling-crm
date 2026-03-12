"""Tactic outcome repository interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class AbstractTacticOutcomeRepository(ABC):
    """Contract for AI tactic outcome persistence."""

    @abstractmethod
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
        """Append one outcome row (outcome=pending). Return row ID or None."""
        ...

    @abstractmethod
    async def get_pending_outcomes(
        self,
        older_than: datetime,
        limit: int = 200,
    ) -> list[dict]:
        """Return pending outcomes created before *older_than*, oldest first."""
        ...

    @abstractmethod
    async def resolve_outcome(
        self,
        outcome_id: int,
        outcome: str,
        resolved_at: datetime,
    ) -> None:
        """Set outcome and resolved_at on a single row."""
        ...

    @abstractmethod
    async def get_resolved_stats(
        self,
        *,
        event_type: str | None = None,
        since: datetime | None = None,
        min_samples: int = 5,
    ) -> list[dict]:
        """Aggregate resolved outcomes into per-tactic stats.

        Returns list of dicts with keys:
            event_type, tactic_name, objection_type, segment,
            total, engaged, measurement_booked, converted, lost, ignored,
            success_rate
        """
        ...
