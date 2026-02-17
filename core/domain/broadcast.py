"""Broadcast domain model."""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field
from shared.constants.enums import BroadcastStatus, CeilingCategory, PipelineStage


class SegmentFilter(BaseModel):
    """Audience segment definition for broadcasts."""
    categories: list[CeilingCategory] | None = None
    pipeline_stages: list[PipelineStage] | None = None
    districts: list[str] | None = None
    joined_after: datetime | None = None
    joined_before: datetime | None = None
    source: str | None = None
    language: str | None = None


class Broadcast(BaseModel):
    """Segmented broadcast message."""
    model_config = {"frozen": True}

    id: int
    title: str
    message_template: str
    media_file_id: str | None = None
    media_type: str | None = None
    segment_filter: SegmentFilter = Field(default_factory=SegmentFilter)
    scheduled_at: datetime | None = None
    status: BroadcastStatus = BroadcastStatus.DRAFT
    sent_count: int = 0
    failed_count: int = 0
    created_by: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
