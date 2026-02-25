"""Unit tests for Quote domain model computed fields."""
from __future__ import annotations
from decimal import Decimal
from core.domain.quote import Quote, QuoteAddonDetail
from shared.constants.enums import CeilingCategory


def test_quote_base_total():
    """Verify base_total = base_price × area × modifier."""
    quote = Quote(
        id=1, lead_id=1,
        category=CeilingCategory.HI_TECH,
        base_price_per_sqm=Decimal("95000"),
        area_sqm=Decimal("20"),
        district_modifier=Decimal("1.05"),
        created_by=1,
    )
    expected = Decimal("95000") * Decimal("20") * Decimal("1.05")
    assert quote.base_total == expected


def test_quote_total_with_discount():
    """Verify discount applies correctly."""
    quote = Quote(
        id=1, lead_id=1,
        category=CeilingCategory.ODNOTONNY,
        base_price_per_sqm=Decimal("45000"),
        area_sqm=Decimal("10"),
        district_modifier=Decimal("1.00"),
        discount_pct=Decimal("10"),
        created_by=1,
    )
    expected = Decimal("45000") * Decimal("10") * Decimal("0.9")
    assert quote.total == expected
