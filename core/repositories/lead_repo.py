"""Lead repository interface."""
from __future__ import annotations

from abc import abstractmethod
from datetime import datetime

from core.domain.lead import Lead
from core.repositories.base import BaseRepository
from shared.constants.enums import CeilingCategory, PipelineStage

_UNSET = object()  # sentinel: "don't touch this column"


class AbstractLeadRepository(BaseRepository[Lead, int]):
    """Contract for lead persistence operations."""

    @abstractmethod
    async def get_by_id(self, id: int) -> Lead | None: ...

    @abstractmethod
    async def get_by_user_id(self, user_id: int) -> list[Lead]: ...

    @abstractmethod
    async def list_by_user(self, user_id: int, limit: int = 5) -> list[Lead]:
        """Return the *limit* most recent leads for *user_id*, newest first."""
        ...

    @abstractmethod
    async def get_by_stage(self, stage: PipelineStage) -> list[Lead]: ...

    @abstractmethod
    async def get_by_category(self, category: CeilingCategory) -> list[Lead]: ...

    @abstractmethod
    async def get_stale_new_leads(self, older_than_minutes: int) -> list[Lead]:
        """Return NEW leads with no stage change in the given minutes."""
        ...

    @abstractmethod
    async def assign_manager(self, lead_id: int, manager_id: int) -> Lead: ...

    @abstractmethod
    async def get_pipeline_counts(self) -> dict[PipelineStage, int]:
        """Return count of leads per pipeline stage."""
        ...

    @abstractmethod
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
    ) -> list[Lead]: ...

    @abstractmethod
    async def upsert_package_lead(
        self,
        user_id: int,
        package_type: str,
        first_name: str,
        score_delta: int,
        lead_status: str,
    ) -> Lead:
        """Create or update a lead when the user selects a package.

        If a lead already exists for *user_id*, updates its package fields and
        increments the score in-place.  Otherwise creates a minimal placeholder
        lead that can be completed later via the full order flow.
        """
        ...

    @abstractmethod
    async def update_lead_status(self, lead_id: int, lead_status: str) -> None:
        """Update the lead_status column (hot / warm / cold / blocked)."""
        ...

    @abstractmethod
    async def update_last_action(self, lead_id: int, last_action: str) -> None:
        """Stamp leads.last_action with *last_action*. Used for dedupe markers."""
        ...

    @abstractmethod
    async def get_counts_by_stage(self) -> dict[str, int]:
        """Return lead counts grouped into 5 kanban buckets.

        Buckets: new | hot | measurement | won | lost
        Leads with no pipeline_stages record are counted as 'new'.
        """
        ...

    @abstractmethod
    async def get_leads_by_kanban_stage(
        self,
        kanban_stage: str,
        limit: int = 10,
        offset: int = 0,
    ) -> list[Lead]:
        """Return leads for a kanban bucket, ordered newest-first.

        kanban_stage must be one of: new | hot | measurement | won | lost
        """
        ...

    @abstractmethod
    async def update_ai_scoring(
        self,
        lead_id: int,
        *,
        lead_temperature: str | None = None,
        closing_confidence: float | None = None,
        next_follow_up_at: object = _UNSET,
        increment_followup_count: bool = False,
    ) -> None:
        """Persist AI scoring columns to a lead.

        Only columns with non-_UNSET values are updated.
        Pass ``next_follow_up_at=None`` to explicitly clear the schedule.
        Pass ``increment_followup_count=True`` to atomically increment the counter.
        """
        ...

    @abstractmethod
    async def set_lost_reason(self, lead_id: int, reason: str) -> None:
        """Set the lost_reason column when a lead is marked LOST."""
        ...

    @abstractmethod
    async def get_lost_reason_counts(
        self,
        since: datetime | None = None,
    ) -> dict[str, int]:
        """Return counts of lost leads grouped by lost_reason."""
        ...

    @abstractmethod
    async def get_leads_for_analytics(
        self,
        days: int = 30,
        limit: int = 500,
    ) -> list[Lead]:
        """Return ALL leads (including terminal) created within *days*, newest first.

        Used by the Sales Analytics engine to compute aggregate metrics.
        Includes won/lost leads for conversion rate calculations.
        """
        ...

    @abstractmethod
    async def get_active_leads(self, limit: int = 50) -> list[Lead]:
        """Return non-terminal leads ordered by updated_at desc.

        Terminal statuses (deal, lost) are excluded.
        Used by the Deal Radar to rank active pipeline leads.
        """
        ...

    @abstractmethod
    async def get_daily_stats(self, since: datetime) -> dict:
        """Return aggregate stats since *since*.

        Returns dict with keys: new_leads, converted, lost,
        active_deals, top_source, lost_reasons.
        """
        ...

    @abstractmethod
    async def get_inactive_leads(
        self,
        inactive_since: datetime,
        exclude_statuses: frozenset[str] | None = None,
    ) -> list[Lead]:
        """Return leads with updated_at <= inactive_since, excluding given statuses."""
        ...

    @abstractmethod
    async def get_due_followups(
        self,
        now: datetime,
        limit: int = 100,
    ) -> list[Lead]:
        """Return leads where next_follow_up_at <= now, excluding terminal states.

        Terminal states (deal / lost / won / completed) are skipped automatically.
        Results are ordered by next_follow_up_at ascending.
        """
        ...
