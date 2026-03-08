"""
LeadService — lead creation and management.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from core.domain.lead import Lead, LeadAddons
from core.events.bus import EventBus, LeadCreated
from core.repositories.lead_repo import AbstractLeadRepository
from core.repositories.pipeline_repo import AbstractPipelineRepository
from shared.constants.enums import CeilingCategory, LeadSource, PipelineStage
from shared.exceptions.base import NotFoundError
from shared.logging import get_logger

if TYPE_CHECKING:
    from infrastructure.database.repositories.lead_action_repo import PostgresLeadActionRepository

log = get_logger(__name__)


class LeadLimitExceeded(Exception):
    """Raised when a tenant's monthly lead quota is exhausted."""


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
        action_repo: "PostgresLeadActionRepository | None" = None,
    ) -> None:
        self._leads = lead_repo
        self._pipeline = pipeline_repo
        self._events = event_bus
        self._actions = action_repo

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
        *,
        tenant_id: int | None = None,
        plan_name: str | None = None,
    ) -> Lead:
        """
        Create a new lead and initialise it in the NEW pipeline stage.
        Logs lead_created action. Emits LeadCreated event.

        If *tenant_id* and *plan_name* are provided, checks the monthly
        lead quota before creating.  Raises ``LeadLimitExceeded`` if over
        the plan limit.
        """
        # ── Plan-based lead quota check ──────────────────────────────────
        if tenant_id is not None:
            try:
                from core.services.usage_service import check_lead_limit

                result = await check_lead_limit(tenant_id, plan_name)
                if not result.allowed:
                    raise LeadLimitExceeded(result.reason or "Lid limiti tugadi.")
            except LeadLimitExceeded:
                raise
            except Exception:
                pass  # fail open

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

        # Timeline: record lead_created action
        if self._actions is not None:
            await self._actions.insert(
                created_lead.id,
                user_id,
                "lead_created",
                payload={"source": source.value, "category": category.value},
            )

        log.info(
            "lead_created",
            lead_id=created_lead.id,
            user_id=user_id,
            category=category.value,
            source=source.value,
        )

        # Track usage for billing
        if tenant_id is not None:
            try:
                from core.services.usage_service import track_lead_created

                await track_lead_created(tenant_id)
            except Exception:
                pass  # never block lead creation for tracking failure

        # Emit domain event
        await self._events.emit(LeadCreated(
            lead_id=created_lead.id,
            user_id=user_id,
            category=category.value,
            source=source.value,
        ))

        return created_lead

    async def assign_manager(
        self,
        lead_id: int,
        manager_id: int,
        actor_id: int,
        *,
        reason: str = "admin_manual",
    ) -> Lead:
        """Assign a manager to a lead."""
        lead = await self._leads.get_by_id(lead_id)
        if lead is None:
            raise NotFoundError("Lead", lead_id)

        result = await self._leads.assign_manager(lead_id, manager_id, reason=reason)
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
