"""Pydantic request/response schemas for the Lead API route."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from shared.constants.enums import CeilingCategory, LeadSource


class LeadCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=7, max_length=20)
    district: str = "—"
    category: CeilingCategory = CeilingCategory.ODNOTONNY
    source: LeadSource = LeadSource.WEB
    notes: str | None = None
    channel_user_id: str | None = None  # web session ID → hashed to int for user_id


class LeadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    district: str
    source: str
    category: str
    lead_status: str | None
    score: int
    created_at: datetime
