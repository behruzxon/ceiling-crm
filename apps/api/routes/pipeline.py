"""
apps.api.routes.pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~
Read-only kanban pipeline endpoint for the CRM dashboard.

GET /api/v1/pipeline/kanban — 5-column kanban board with lead counts and items.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies.auth import require_api_token
from apps.api.schemas.pipeline import KanbanColumnOut, KanbanLeadOut, KanbanResponse
from core.services.pipeline_service import KANBAN_DISPLAY, KANBAN_STAGES, PipelineService
from infrastructure.database.session import get_db
from infrastructure.di import get_pipeline_service

router = APIRouter(
    prefix="/api/v1",
    tags=["pipeline"],
    dependencies=[Depends(require_api_token)],
)


def _lead_to_kanban_out(lead) -> KanbanLeadOut:
    """Convert a domain Lead to the kanban-safe API response."""
    return KanbanLeadOut(
        id=lead.id,
        name=lead.name,
        phone=lead.phone,
        district=lead.district,
        current_stage=(
            lead.current_stage.value
            if hasattr(lead.current_stage, "value")
            else str(lead.current_stage)
        ),
        score=lead.score,
        lead_status=lead.lead_status,
        room_area=lead.room_area,
        next_follow_up_at=lead.next_follow_up_at,
        created_at=lead.created_at,
        updated_at=lead.updated_at,
    )


@router.get("/pipeline/kanban", response_model=KanbanResponse)
async def kanban_board(
    limit_per_column: int = Query(20, ge=1, le=100, description="Max leads per column"),
    db: AsyncSession = Depends(get_db),
) -> KanbanResponse:
    """Return the 5-column kanban board with counts and top leads per column."""
    svc: PipelineService = get_pipeline_service(db)

    counts = await svc.get_stage_counts()

    columns: list[KanbanColumnOut] = []
    for stage_key in KANBAN_STAGES:
        leads = await svc.get_leads_by_stage(stage_key, limit=limit_per_column)
        columns.append(
            KanbanColumnOut(
                key=stage_key,
                title=KANBAN_DISPLAY.get(stage_key, stage_key),
                count=counts.get(stage_key, 0),
                items=[_lead_to_kanban_out(lead) for lead in leads],
            )
        )

    return KanbanResponse(columns=columns)
