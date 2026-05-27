"""
CRMService — pipeline stage transitions and history.
"""

from __future__ import annotations

from core.domain.lead import Lead
from core.events.bus import EventBus, StageChanged
from core.repositories.lead_repo import AbstractLeadRepository
from core.repositories.pipeline_repo import AbstractPipelineRepository, PipelineRecord
from shared.constants.enums import PipelineStage
from shared.exceptions.base import (
    InvalidStageTransitionError,
    MissingLostReasonError,
    NotFoundError,
)
from shared.logging import get_logger

log = get_logger(__name__)

# Allowed transitions — see architecture document Section 5.2
# Forward transitions advance the pipeline; backward transitions (marked ←)
# support the "Prev stage" button and stage corrections by admins.
ALLOWED_TRANSITIONS: dict[PipelineStage, list[PipelineStage]] = {
    PipelineStage.NEW: [
        PipelineStage.PACKAGE_SELECTED,
        PipelineStage.CONTACTED,
        PipelineStage.LOST,
    ],
    PipelineStage.PACKAGE_SELECTED: [
        PipelineStage.CONTACTED,
        PipelineStage.LOST,
    ],
    PipelineStage.CONTACTED: [
        PipelineStage.MEASUREMENT,
        PipelineStage.NEW,  # ← backward (undo)
        PipelineStage.LOST,
    ],
    PipelineStage.MEASUREMENT: [
        PipelineStage.QUOTE,
        PipelineStage.CONTACTED,  # ← backward (undo)
        PipelineStage.LOST,
    ],
    PipelineStage.QUOTE: [
        PipelineStage.DEAL,
        PipelineStage.MEASUREMENT,  # ← backward (undo)
        PipelineStage.LOST,
    ],
    PipelineStage.DEAL: [
        PipelineStage.INSTALLATION,
        PipelineStage.QUOTE,  # ← backward (undo)
        PipelineStage.LOST,
    ],
    PipelineStage.INSTALLATION: [
        PipelineStage.COMPLETED,
        PipelineStage.DEAL,  # ← backward (undo)
        PipelineStage.LOST,
    ],
    PipelineStage.COMPLETED: [
        PipelineStage.INSTALLATION,  # ← backward (correction only)
    ],
    PipelineStage.LOST: [
        PipelineStage.NEW,
    ],
}


class CRMService:
    """
    Manages CRM pipeline stage transitions.
    Validates transitions, persists stage records, emits events.
    """

    def __init__(
        self,
        lead_repo: AbstractLeadRepository,
        pipeline_repo: AbstractPipelineRepository,
        event_bus: EventBus,
    ) -> None:
        self._leads = lead_repo
        self._pipeline = pipeline_repo
        self._events = event_bus

    async def advance_stage(
        self,
        lead_id: int,
        new_stage: PipelineStage,
        actor_id: int,
        note: str | None = None,
    ) -> Lead:
        """
        Transition a lead to a new pipeline stage.

        Raises:
            NotFoundError: if lead not found
            InvalidStageTransitionError: if transition is not allowed
            MissingLostReasonError: if moving to LOST without a note
        """
        lead = await self._leads.get_by_id(lead_id)
        if lead is None:
            raise NotFoundError("Lead", lead_id)

        current_stage = await self._pipeline.get_current_stage(lead_id)
        if current_stage is None:
            current_stage = PipelineStage.NEW

        # Validate transition
        valid_next = ALLOWED_TRANSITIONS.get(current_stage, [])
        if new_stage not in valid_next:
            raise InvalidStageTransitionError(current_stage.value, new_stage.value)

        # LOST transitions require a reason note
        if new_stage == PipelineStage.LOST and not note:
            raise MissingLostReasonError("Reason note is required when marking a lead as LOST")

        # Persist the stage change
        await self._pipeline.insert_stage(
            lead_id=lead_id,
            stage=new_stage,
            changed_by=actor_id,
            note=note,
        )

        log.info(
            "stage_advanced",
            lead_id=lead_id,
            from_stage=current_stage.value,
            to_stage=new_stage.value,
            actor_id=actor_id,
        )

        # Emit domain event
        await self._events.emit(
            StageChanged(
                lead_id=lead_id,
                from_stage=current_stage.value,
                to_stage=new_stage.value,
                actor_id=actor_id,
            )
        )

        # Return updated lead with new stage
        updated_lead = await self._leads.get_by_id(lead_id)
        return updated_lead  # type: ignore[return-value]

    async def get_stage_history(self, lead_id: int) -> list[PipelineRecord]:
        """Return full stage history for a lead."""
        return await self._pipeline.get_history(lead_id)

    def get_valid_transitions(self, current_stage: PipelineStage) -> list[PipelineStage]:
        """Return allowed next stages from the current stage."""
        return ALLOWED_TRANSITIONS.get(current_stage, [])
