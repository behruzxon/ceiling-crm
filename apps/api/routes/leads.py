"""
apps.api.routes.leads
~~~~~~~~~~~~~~~~~~~~~
Read-only leads endpoint for the CRM dashboard.

GET /api/v1/leads — paginated list with optional stage filter.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies.auth import require_api_token
from apps.api.schemas.leads import LeadListResponse, LeadOut
from core.domain.lead import Lead
from infrastructure.database.models.lead import LeadModel
from infrastructure.database.models.pipeline_stage import PipelineStageModel
from infrastructure.database.session import get_db
from infrastructure.di import get_lead_repo
from shared.constants.enums import PipelineStage

router = APIRouter(
    prefix="/api/v1",
    tags=["leads"],
    dependencies=[Depends(require_api_token)],
)


def _lead_to_out(lead: Lead) -> LeadOut:
    """Convert a domain Lead to the API response schema."""
    return LeadOut.model_validate(lead.model_dump())


def _stage_subquery(alias: str = "ls_api") -> "sa.Subquery":
    """Latest pipeline stage per lead (mirrors repo helper)."""
    return (
        select(
            PipelineStageModel.lead_id,
            PipelineStageModel.stage,
        )
        .distinct(PipelineStageModel.lead_id)
        .order_by(PipelineStageModel.lead_id, PipelineStageModel.created_at.desc())
        .subquery(alias)
    )


@router.get("/leads", response_model=LeadListResponse)
async def list_leads(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    stage: PipelineStage | None = Query(None, description="Filter by pipeline stage"),
    db: AsyncSession = Depends(get_db),
) -> LeadListResponse:
    """Return a paginated list of leads, newest first."""
    repo = get_lead_repo(db)
    offset = (page - 1) * page_size

    # Fetch items via existing repo method
    items = await repo.search(stage=stage, limit=page_size, offset=offset)

    # Total count (matching the same filter logic as search)
    if stage is not None:
        latest = _stage_subquery()
        count_stmt = (
            select(func.count())
            .select_from(LeadModel)
            .join(latest, LeadModel.id == latest.c.lead_id)
            .where(latest.c.stage == stage.value)
        )
    else:
        count_stmt = select(func.count()).select_from(LeadModel)

    total = (await db.execute(count_stmt)).scalar() or 0
    total_pages = max(1, (total + page_size - 1) // page_size)

    return LeadListResponse(
        items=[_lead_to_out(lead) for lead in items],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )
