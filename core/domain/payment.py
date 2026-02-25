"""Domain model for a payment record."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from shared.constants.enums import PaymentMethod, PaymentStatus


class Payment(BaseModel):
    """Immutable snapshot of one payment row."""

    model_config = ConfigDict(frozen=True)

    id: int                          # 0 before DB insert (placeholder convention)
    lead_id: int
    amount: int                      # UZS, integer so'm
    method: PaymentMethod
    status: PaymentStatus
    paid_at: datetime | None = None
    receipt_url: str | None = None
    notes: str | None = None
    created_by: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
