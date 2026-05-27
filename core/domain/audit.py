"""Audit log domain model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AuditLog(BaseModel):
    """Immutable audit trail record."""

    model_config = {"frozen": True}

    id: int
    actor_id: int | None = None  # None = system action
    action: str  # e.g. "lead.stage_changed"
    entity_type: str  # e.g. "lead"
    entity_id: int
    old_value: dict[str, Any] | None = None
    new_value: dict[str, Any] | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
