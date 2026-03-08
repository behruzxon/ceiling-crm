"""Subscription payment domain model."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from shared.constants.enums import SubscriptionPaymentProvider, SubscriptionPaymentStatus


class SubscriptionPayment(BaseModel):
    """Immutable snapshot of a subscription payment record."""

    model_config = ConfigDict(frozen=True)

    id: int
    tenant_id: int
    provider: SubscriptionPaymentProvider
    status: SubscriptionPaymentStatus
    amount: int
    currency: str = "UZS"
    description: str | None = None
    merchant_trans_id: str
    provider_trans_id: str | None = None
    extension_days: int = 30
    paid_at: datetime | None = None
    canceled_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    provider_meta: dict = {}
