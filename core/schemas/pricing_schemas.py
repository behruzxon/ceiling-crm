"""Pydantic schemas for the Pricing API route."""
from __future__ import annotations

from pydantic import BaseModel, Field


class PriceCalculateRequest(BaseModel):
    length: float = Field(..., gt=0, le=50)
    width: float = Field(..., gt=0, le=50)
    price_per_sqm: int = Field(..., gt=0)
    design_name: str = "—"
    design_key: str = ""  # used for LED promo eligibility check


class PriceCalculateResponse(BaseModel):
    length: float
    width: float
    area: float
    design_name: str
    price_per_sqm: int
    gross_amount: int
    discount_pct: int
    discount_amount: int
    final_total: int
    promo_eligible: bool
