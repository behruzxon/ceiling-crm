"""Pydantic response schemas for the pipeline/kanban API."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class KanbanLeadOut(BaseModel):
    """Single lead item within a kanban column — dashboard-safe fields only."""

    id: int
    name: str
    phone: str
    district: str
    current_stage: str
    score: int = 0
    lead_status: str | None = None
    room_area: Decimal | None = None
    next_follow_up_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class KanbanColumnOut(BaseModel):
    """One kanban column with its leads."""

    key: str
    title: str
    count: int
    items: list[KanbanLeadOut]


class KanbanResponse(BaseModel):
    """Full kanban board response — 5 columns with counts and leads."""

    columns: list[KanbanColumnOut]
