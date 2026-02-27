"""
LeadService — lead creation and management.
"""
from __future__ import annotations

from core.domain.lead import Lead, LeadAddons
from core.events.bus import EventBus, LeadCreated
from core.repositories.lead_repo import AbstractLeadRepository
from core.repositories.pipeline_repo import AbstractPipelineRepository
from shared.constants.enums import CeilingCategory, LeadSource, PipelineStage
from shared.exceptions.base import NotFoundError
from shared.logging import get_logger

log = get_logger(__name__)


class LeadService:
    """
    Handles lead creation, assignment, and pipeline-aware queries.
    Emits domain events on significant state changes.
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

    async def create_lead(
        self,
        user_id: int,
        category: CeilingCategory,
        name: str,
        phone: str,
        district: str,
        source: LeadSource = LeadSource.GROUP,
        source_group_id: int | None = None,
        addons: LeadAddons | None = None,
        notes: str | None = None,
        utm_source: str | None = None,
        utm_campaign: str | None = None,
    ) -> Lead:
        """
        Create a new lead and initialise it in the NEW pipeline stage.
        Emits LeadCreated event.
        """
        # Build domain object (id=0 placeholder, DB assigns real ID)
        lead = Lead(
            id=0,
            user_id=user_id,
            category=category,
            source=source,
            source_group_id=source_group_id,
            name=name,
            phone=phone,
            district=district,
            addons=addons or LeadAddons(),
            notes=notes,
            utm_source=utm_source,
            utm_campaign=utm_campaign,
        )

        created_lead = await self._leads.create(lead)

        # Initialise pipeline at NEW stage
        await self._pipeline.insert_stage(
            lead_id=created_lead.id,
            stage=PipelineStage.NEW,
            changed_by=user_id,
            note="Lead created",
        )

        log.info(
            "lead_created",
            lead_id=created_lead.id,
            user_id=user_id,
            category=category.value,
            source=source.value,
        )

        # Emit domain event
        await self._events.emit(LeadCreated(
            lead_id=created_lead.id,
            user_id=user_id,
            category=category.value,
            source=source.value,
        ))

        return created_lead

    async def assign_manager(self, lead_id: int, manager_id: int, actor_id: int) -> Lead:
        """Assign a manager to a lead."""
        lead = await self._leads.get_by_id(lead_id)
        if lead is None:
            raise NotFoundError("Lead", lead_id)

        result = await self._leads.assign_manager(lead_id, manager_id)
        log.info("lead_assigned", lead_id=lead_id, manager_id=manager_id, actor_id=actor_id)
        return result

    async def get_lead(self, lead_id: int) -> Lead:
        """Fetch lead by ID. Raises NotFoundError if absent."""
        lead = await self._leads.get_by_id(lead_id)
        if lead is None:
            raise NotFoundError("Lead", lead_id)
        return lead

    async def search_leads(self, **filters: object) -> list[Lead]:
        """Flexible lead search delegated to repository."""
        return await self._leads.search(**filters)

    async def select_package(
        self,
        user_id: int,
        package_type: str,
        first_name: str,
        score_delta: int,
        lead_status: str,
    ) -> Lead:
        """Record that a user selected a package.

        Upserts the lead (create or update), then inserts a PACKAGE_SELECTED
        pipeline stage record.  Does NOT go through CRMService transition
        validation — package selection is an entry-point action, not a
        pipeline-internal move.
        """
        lead = await self._leads.upsert_package_lead(
            user_id=user_id,
            package_type=package_type,
            first_name=first_name,
            score_delta=score_delta,
            lead_status=lead_status,
        )

        await self._pipeline.insert_stage(
            lead_id=lead.id,
            stage=PipelineStage.PACKAGE_SELECTED,
            changed_by=user_id,
            note=f"Paket tanlandi: {package_type}",
        )

        log.info(
            "package_selected",
            lead_id=lead.id,
            user_id=user_id,
            package_type=package_type,
            lead_status=lead_status,
            score_delta=score_delta,
        )
        return lead
