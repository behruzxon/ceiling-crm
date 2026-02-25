"""Domain model for a warranty record."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class Warranty(BaseModel):
    """Immutable snapshot of one warranty row (one per lead)."""

    model_config = ConfigDict(frozen=True)

    id: int                              # 0 before DB insert (placeholder convention)
    lead_id: int
    issued_at: date
    expires_at: date                     # typically issued_at + 15 years
    warranty_card_no: str | None = None
    notes: str | None = None
    created_by: int
    created_at: datetime | None = None
