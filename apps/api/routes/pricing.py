"""POST /api/pricing/calculate — pure ceiling price calculation.

No database access required.  The tenant middleware still runs (slug header
required for a consistent security posture), but tenant_id is not used here.
"""
from __future__ import annotations

from fastapi import APIRouter

from core.schemas.pricing_schemas import PriceCalculateRequest, PriceCalculateResponse
from core.services.ceiling_calculator import calculate_quote, is_led_promo_eligible

router = APIRouter()


@router.post("/calculate", response_model=PriceCalculateResponse)
async def calculate_price(payload: PriceCalculateRequest) -> PriceCalculateResponse:
    quote = calculate_quote(
        payload.length,
        payload.width,
        payload.price_per_sqm,
        payload.design_name,
    )
    return PriceCalculateResponse(
        length=quote.length,
        width=quote.width,
        area=quote.area,
        design_name=quote.design_name,
        price_per_sqm=quote.price_per_sqm,
        gross_amount=quote.gross_amount,
        discount_pct=quote.discount_pct,
        discount_amount=quote.discount_amount,
        final_total=quote.final_total,
        promo_eligible=is_led_promo_eligible(quote.area, payload.design_key),
    )
