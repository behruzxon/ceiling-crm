"""Appointment domain model."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from shared.constants.enums import AppointmentStatus, AppointmentType


class Appointment(BaseModel):
    """Measurement or installation appointment."""
    model_config = {"frozen": True}

    id: int
    lead_id: int
    type: AppointmentType
    installer_id: int | None = None
    brigade_id: int | None = None
    scheduled_at: datetime
    duration_minutes: int = 60
    district: str
    address: str | None = None
    status: AppointmentStatus = AppointmentStatus.SCHEDULED
    notes: str | None = None
    created_by: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
