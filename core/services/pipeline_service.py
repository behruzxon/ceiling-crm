"""
PipelineService — simplified kanban pipeline management.

Provides a 5-column kanban view (NEW / HOT / MEASUREMENT / WON / LOST)
on top of the detailed 9-stage pipeline stored in pipeline_stages.

Unlike CRMService, move_stage() bypasses ALLOWED_TRANSITIONS so that
admins can freely re-assign any lead to any kanban column.
Every move is still persisted to pipeline_stages + lead_actions + audit_logs.
"""

from __future__ import annotations

from core.domain.lead import Lead
from core.repositories.lead_repo import AbstractLeadRepository
from core.repositories.pipeline_repo import AbstractPipelineRepository
from infrastructure.database.repositories.audit_log_repo import PostgresAuditLogRepository
from infrastructure.database.repositories.lead_action_repo import PostgresLeadActionRepository
from shared.constants.enums import PipelineStage
from shared.exceptions.base import NotFoundError
from shared.logging import get_logger

log = get_logger(__name__)

# ── Kanban stage constants ────────────────────────────────────────────────────
KANBAN_NEW = "new"
KANBAN_HOT = "hot"
KANBAN_MEASUREMENT = "measurement"
KANBAN_WON = "won"
KANBAN_LOST = "lost"

KANBAN_STAGES: list[str] = [
    KANBAN_NEW,
    KANBAN_HOT,
    KANBAN_MEASUREMENT,
    KANBAN_WON,
    KANBAN_LOST,
]

# Display label for each kanban stage (emoji + short name)
KANBAN_DISPLAY: dict[str, str] = {
    KANBAN_NEW: "🔵 NEW",
    KANBAN_HOT: "🔥 HOT",
    KANBAN_MEASUREMENT: "📐 MEASUREMENT",
    KANBAN_WON: "🏆 WON",
    KANBAN_LOST: "❌ LOST",
}

# When an admin moves a lead to a kanban column, record this pipeline stage
KANBAN_MOVE_TARGET: dict[str, PipelineStage] = {
    KANBAN_NEW: PipelineStage.NEW,
    KANBAN_HOT: PipelineStage.CONTACTED,
    KANBAN_MEASUREMENT: PipelineStage.MEASUREMENT,
    KANBAN_WON: PipelineStage.COMPLETED,
    KANBAN_LOST: PipelineStage.LOST,
}


class PipelineService:
    """
    Manages the simplified 5-column kanban view of the CRM pipeline.

    get_stage_counts()  — count leads per kanban column (for the /pipeline keyboard)
    get_leads_by_stage()— list leads in a column (for the stage-detail view)
    move_stage()        — move a lead to a kanban column (admin override)
    """

    def __init__(
        self,
        lead_repo: AbstractLeadRepository,
        pipeline_repo: AbstractPipelineRepository,
        action_repo: PostgresLeadActionRepository,
        audit_repo: PostgresAuditLogRepository,
    ) -> None:
        self._leads = lead_repo
        self._pipeline = pipeline_repo
        self._actions = action_repo
        self._audit = audit_repo

    async def get_stage_counts(self) -> dict[str, int]:
        """Return lead counts grouped into 5 kanban stages.

        Leads with no pipeline_stages record are counted as 'new'.
        """
        return await self._leads.get_counts_by_stage()

    async def get_lead(self, lead_id: int) -> Lead | None:
        """Return a single lead by ID, or None if not found."""
        return await self._leads.get_by_id(lead_id)

    async def get_leads_by_stage(
        self,
        kanban_stage: str,
        limit: int = 10,
        offset: int = 0,
    ) -> list[Lead]:
        """Return leads in a kanban stage bucket, newest-first."""
        return await self._leads.get_leads_by_kanban_stage(kanban_stage, limit=limit, offset=offset)

    async def move_stage(
        self,
        lead_id: int,
        new_kanban_stage: str,
        actor_id: int,
        note: str | None = None,
    ) -> Lead:
        """Move a lead to a kanban column (admin override — no transition checks).

        Side-effects (all within the caller's transaction):
        1. leads.lead_status  → updated to *new_kanban_stage*
        2. pipeline_stages    → new row inserted
        3. lead_actions       → row with action_type='stage_change'
        4. audit_logs         → row with action='lead.stage_changed'

        Returns the refreshed Lead domain object.
        Raises NotFoundError if the lead does not exist.
        """
        lead = await self._leads.get_by_id(lead_id)
        if lead is None:
            raise NotFoundError("Lead", lead_id)

        old_pipeline_stage = await self._pipeline.get_current_stage(lead_id)
        old_pipeline_stage = old_pipeline_stage or PipelineStage.NEW
        new_pipeline_stage = KANBAN_MOVE_TARGET.get(new_kanban_stage, PipelineStage.NEW)

        # 1. Update leads.lead_status
        await self._leads.update_lead_status(lead_id, new_kanban_stage)

        # 2. Insert pipeline stage record (bypasses ALLOWED_TRANSITIONS)
        await self._pipeline.insert_stage(
            lead_id=lead_id,
            stage=new_pipeline_stage,
            changed_by=actor_id,
            note=note or f"Kanban move: {old_pipeline_stage.value} → {new_pipeline_stage.value}",
        )

        # 3. Insert lead action
        await self._actions.insert(
            lead_id=lead_id,
            actor_user_id=actor_id,
            action_type="stage_change",
            payload={
                "old": old_pipeline_stage.value,
                "new": new_pipeline_stage.value,
                "kanban_stage": new_kanban_stage,
            },
        )

        # 4. Insert audit log
        await self._audit.insert(
            actor_id=actor_id,
            action="lead.stage_changed",
            entity_type="lead",
            entity_id=lead_id,
            old_value={"stage": old_pipeline_stage.value},
            new_value={
                "stage": new_pipeline_stage.value,
                "kanban_stage": new_kanban_stage,
            },
        )

        log.info(
            "kanban_stage_moved",
            lead_id=lead_id,
            from_stage=old_pipeline_stage.value,
            to_stage=new_pipeline_stage.value,
            kanban_stage=new_kanban_stage,
            actor_id=actor_id,
        )

        updated = await self._leads.get_by_id(lead_id)
        return updated  # type: ignore[return-value]
