"""Quote domain model."""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, computed_field
from shared.constants.enums import CeilingCategory


class QuoteAddonDetail(BaseModel):
    name: str
    quantity: Decimal
    unit_price: Decimal
    total: Decimal


class Quote(BaseModel):
    """Price quote calculated for a lead."""
    model_config = {"frozen": True}

    id: int
    lead_id: int
    category: CeilingCategory
    base_price_per_sqm: Decimal
    area_sqm: Decimal
    district_modifier: Decimal = Decimal("1.00")
    addons_detail: list[QuoteAddonDetail] = Field(default_factory=list)
    discount_pct: Decimal = Decimal("0")
    currency: str = "UZS"
    is_accepted: bool | None = None         # None = pending
    created_by: int
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @computed_field  # type: ignore[misc]
    @property
    def base_total(self) -> Decimal:
        return self.base_price_per_sqm * self.area_sqm * self.district_modifier

    @computed_field  # type: ignore[misc]
    @property
    def addons_total(self) -> Decimal:
        return sum(a.total for a in self.addons_detail)

    @computed_field  # type: ignore[misc]
    @property
    def subtotal(self) -> Decimal:
        return self.base_total + self.addons_total

    @computed_field  # type: ignore[misc]
    @property
    def total(self) -> Decimal:
        discount_factor = (100 - self.discount_pct) / 100
        return self.subtotal * discount_factor
