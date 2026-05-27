"""Pipeline repository interface."""

from __future__ import annotations

from abc import abstractmethod

from core.repositories.base import BaseRepository
from shared.constants.enums import PipelineStage


class PipelineRecord:
    lead_id: int
    stage: PipelineStage
    changed_by: int
    note: str | None
    created_at: object


class AbstractPipelineRepository(BaseRepository[PipelineRecord, int]):
    """Contract for pipeline stage persistence."""

    @abstractmethod
    async def insert_stage(
        self,
        lead_id: int,
        stage: PipelineStage,
        changed_by: int,
        note: str | None = None,
    ) -> PipelineRecord: ...

    @abstractmethod
    async def get_history(self, lead_id: int) -> list[PipelineRecord]: ...

    @abstractmethod
    async def get_current_stage(self, lead_id: int) -> PipelineStage | None: ...
