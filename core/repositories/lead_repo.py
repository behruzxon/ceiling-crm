"""Lead repository interface."""
from __future__ import annotations
from abc import abstractmethod
from datetime import datetime
from core.domain.lead import Lead
from core.repositories.base import BaseRepository
from shared.constants.enums import CeilingCategory, PipelineStage


class AbstractLeadRepository(BaseRepository[Lead, int]):
    """Contract for lead persistence operations."""

    @abstractmethod
    async def get_by_id(self, id: int) -> Lead | None: ...

    @abstractmethod
    async def get_by_user_id(self, user_id: int) -> list[Lead]: ...

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
