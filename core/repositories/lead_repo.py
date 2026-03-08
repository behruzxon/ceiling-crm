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
    async def assign_manager(
        self, lead_id: int, manager_id: int, *, reason: str | None = None,
    ) -> Lead: ...

    @abstractmethod
    async def unassign_manager(self, lead_id: int) -> Lead: ...

    @abstractmethod
    async def get_assigned_leads(
        self,
        manager_id: int,
        *,
        tenant_id: int | None = None,
        limit: int = 20,
    ) -> list[Lead]:
        """Return leads assigned to a specific manager, ordered by score DESC."""
        ...

    @abstractmethod
    async def get_pipeline_counts(
        self, *, tenant_id: int | None = None,
    ) -> dict[PipelineStage, int]:
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
        lead_temperature: str | None = None,
        tenant_id: int | None = None,
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
    async def get_counts_by_stage(
        self, *, tenant_id: int | None = None,
    ) -> dict[str, int]:
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
        *,
        tenant_id: int | None = None,
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

    @abstractmethod
    async def get_due_user_followups(
        self,
        now: datetime,
        limit: int = 50,
    ) -> list[Lead]:
        """Return leads due for user-facing follow-up messages.

        Conditions: user_followup_at <= now, stage < 3, not closed, not terminal.
        """
        ...

    @abstractmethod
    async def update_user_followup(
        self,
        lead_id: int,
        *,
        user_followup_stage: int | None = None,
        user_followup_at: object = _UNSET,
        user_followup_closed: bool | None = None,
    ) -> None:
        """Update user follow-up tracking columns."""
        ...

    @abstractmethod
    async def update_scoring_engine(
        self,
        lead_id: int,
        *,
        score: int | None = None,
        lead_temperature: str | None = None,
        closing_confidence: float | None = None,
        urgency_signal: str | None = None,
        budget_signal: str | None = None,
        engagement_signal: str | None = None,
        objection_signal: str | None = None,
        scoring_reasons: list[str] | None = None,
        operator_attention: bool | None = None,
        next_follow_up_at: object = _UNSET,
        increment_followup_count: bool = False,
    ) -> None:
        """Persist all scoring engine output columns atomically."""
        ...

    @abstractmethod
    async def get_hot_leads(
        self,
        *,
        tenant_id: int | None = None,
        limit: int = 10,
    ) -> list[Lead]:
        """Return hot leads (temperature='hot' OR score>=60), ordered by score DESC."""
        ...

    @abstractmethod
    async def get_attention_leads(
        self,
        *,
        tenant_id: int | None = None,
        limit: int = 10,
    ) -> list[Lead]:
        """Return leads with operator_attention=TRUE, ordered by score DESC."""
        ...

    @abstractmethod
    async def get_temperature_counts(
        self, *, tenant_id: int | None = None,
    ) -> dict[str, int]:
        """Return lead counts grouped by lead_temperature (hot/warm/cold)."""
        ...

    @abstractmethod
    async def get_recent_leads(
        self, *, tenant_id: int | None = None, limit: int = 10,
    ) -> list[Lead]:
        """Return the most recent leads, ordered by created_at DESC."""
        ...

    @abstractmethod
    async def get_unassigned_leads(
        self, *, tenant_id: int | None = None, limit: int = 10,
    ) -> list[Lead]:
        """Return leads with no assigned_manager_id."""
        ...
