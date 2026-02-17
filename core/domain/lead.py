"""Lead domain model."""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field
from shared.constants.enums import CeilingCategory, LeadSource, PipelineStage


class LeadAddons(BaseModel):
    """Add-on selections for a lead/quote."""
    led_strip: bool = False
    led_rgb: bool = False
    chandelier_holes: int = 0
    spot_holes: int = 0
    cornice: bool = False
    profile_rounding: bool = False
    two_level_step: bool = False


class Lead(BaseModel):
    """Immutable domain representation of a sales lead."""
    model_config = {"frozen": True}

    id: int
    user_id: int
    category: CeilingCategory
    source: LeadSource = LeadSource.GROUP
    source_group_id: int | None = None
    name: str
    phone: str
    district: str
    room_length: Decimal | None = None
    room_width: Decimal | None = None
    room_area: Decimal | None = None
    addons: LeadAddons = Field(default_factory=LeadAddons)
    notes: str | None = None
    utm_source: str | None = None
    utm_campaign: str | None = None
    assigned_manager_id: int | None = None
    current_stage: PipelineStage = PipelineStage.NEW
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
