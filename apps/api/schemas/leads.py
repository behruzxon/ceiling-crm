"""Pydantic response schemas for the leads API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class LeadAddonsOut(BaseModel):
    """Add-on selections attached to a lead."""

    led_strip: bool = False
    led_rgb: bool = False
    chandelier_holes: int = 0
    spot_holes: int = 0
    cornice: bool = False
    profile_rounding: bool = False
    two_level_step: bool = False


class LeadOut(BaseModel):
    """Single lead in the API response."""

    id: int
    user_id: int
    category: str
    source: str
    source_group_id: int | None = None
    name: str
    phone: str
    district: str
    room_length: Decimal | None = None
    room_width: Decimal | None = None
    room_area: Decimal | None = None
    addons: LeadAddonsOut = LeadAddonsOut()
    notes: str | None = None
    utm_source: str | None = None
    utm_campaign: str | None = None
    assigned_manager_id: int | None = None
    current_stage: str
    package_type: str | None = None
    lead_status: str | None = None
    last_action: str | None = None
    score: int = 0
    lead_temperature: str | None = None
    closing_confidence: float | None = None
    next_follow_up_at: datetime | None = None
    follow_up_count: int = 0
    created_at: datetime
    updated_at: datetime


class LeadListResponse(BaseModel):
    """Paginated list of leads."""

    items: list[LeadOut]
    page: int
    page_size: int
    total: int
    total_pages: int
    has_next: bool
    has_prev: bool
