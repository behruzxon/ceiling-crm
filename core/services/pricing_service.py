"""
PricingService — quote calculation engine.
"""
from __future__ import annotations

from decimal import Decimal

from core.domain.lead import LeadAddons
from core.domain.quote import Quote, QuoteAddonDetail
from infrastructure.cache.client import get_redis
from shared.constants.enums import CeilingCategory
from shared.logging import get_logger

log = get_logger(__name__)

# Default base prices per sqm (UZS) — seeded to Redis cache
DEFAULT_BASE_PRICES: dict[CeilingCategory, Decimal] = {
    CeilingCategory.MATTE_WHITE:    Decimal("120000"),
    CeilingCategory.GLOSSY_WHITE:   Decimal("130000"),
    CeilingCategory.BLACK_PREMIUM:  Decimal("180000"),
    CeilingCategory.FLORAL_3D:      Decimal("250000"),
    CeilingCategory.MARBLE:         Decimal("220000"),
    CeilingCategory.LED_BACKLIGHT:  Decimal("200000"),
    CeilingCategory.STARRY_SKY:     Decimal("300000"),
    CeilingCategory.TWO_LEVEL:      Decimal("280000"),
    CeilingCategory.OFFICE_MINIMAL: Decimal("100000"),
    CeilingCategory.KITCHEN:        Decimal("140000"),
}

# Add-on unit prices (UZS)
ADDON_PRICES = {
    "led_strip":        Decimal("25000"),   # per linear meter
    "led_rgb":          Decimal("40000"),   # per linear meter
    "chandelier_holes": Decimal("50000"),   # per hole
    "spot_holes":       Decimal("30000"),   # per hole
    "cornice":          Decimal("15000"),   # per linear meter
    "profile_rounding": Decimal("80000"),   # flat fee
    "two_level_step":   Decimal("200000"),  # flat fee
}


class PricingService:
    """
    Calculates ceiling installation quotes.

    Price formula:
        TOTAL = (base_price_per_sqm × area_sqm × district_modifier)
                + addons_total - discount
    """

    async def calculate_quote(
        self,
        lead_id: int,
        category: CeilingCategory,
        area_sqm: Decimal,
        district: str,
        addons: LeadAddons,
        created_by: int,
        discount_pct: Decimal = Decimal("0"),
    ) -> Quote:
        """Calculate a full quote for a lead."""
        base_price = await self.get_base_price(category)
        modifier = await self.get_district_modifier(district)

        # Estimate perimeter from area (assume roughly square room)
        side = area_sqm ** Decimal("0.5")
        perimeter = side * 4

        addons_detail = self._calculate_addons(addons, area_sqm, perimeter)

        quote = Quote(
            id=0,
            lead_id=lead_id,
            category=category,
            base_price_per_sqm=base_price,
            area_sqm=area_sqm,
            district_modifier=modifier,
            addons_detail=addons_detail,
            discount_pct=discount_pct,
            created_by=created_by,
        )

        log.info(
            "quote_calculated",
            lead_id=lead_id,
            category=category.value,
            area_sqm=str(area_sqm),
            total=str(quote.total),
        )
        return quote

    async def get_base_price(self, category: CeilingCategory) -> Decimal:
        """Return base price per sqm from Redis cache with fallback to defaults."""
        cache = get_redis()
        cached = await cache.get(f"price:{category.value}")
        if cached is not None:
            return Decimal(cached)
        return DEFAULT_BASE_PRICES.get(category, Decimal("120000"))

    async def get_district_modifier(self, district: str) -> Decimal:
        """Return district zone modifier from Redis cache."""
        cache = get_redis()
        cached = await cache.get(f"district_mod:{district.lower()}")
        if cached is not None:
            return Decimal(cached)
        return Decimal("1.00")

    def _calculate_addons(
        self,
        addons: LeadAddons,
        area_sqm: Decimal,
        perimeter: Decimal,
    ) -> list[QuoteAddonDetail]:
        """Itemise add-on costs."""
        details: list[QuoteAddonDetail] = []

        if addons.led_strip:
            details.append(QuoteAddonDetail(
                name="LED strip",
                quantity=perimeter,
                unit_price=ADDON_PRICES["led_strip"],
                total=perimeter * ADDON_PRICES["led_strip"],
            ))

        if addons.led_rgb:
            details.append(QuoteAddonDetail(
                name="LED RGB",
                quantity=perimeter,
                unit_price=ADDON_PRICES["led_rgb"],
                total=perimeter * ADDON_PRICES["led_rgb"],
            ))

        if addons.chandelier_holes > 0:
            qty = Decimal(addons.chandelier_holes)
            details.append(QuoteAddonDetail(
                name="Chandelier holes",
                quantity=qty,
                unit_price=ADDON_PRICES["chandelier_holes"],
                total=qty * ADDON_PRICES["chandelier_holes"],
            ))

        if addons.spot_holes > 0:
            qty = Decimal(addons.spot_holes)
            details.append(QuoteAddonDetail(
                name="Spot light holes",
                quantity=qty,
                unit_price=ADDON_PRICES["spot_holes"],
                total=qty * ADDON_PRICES["spot_holes"],
            ))

        if addons.cornice:
            details.append(QuoteAddonDetail(
                name="Cornice",
                quantity=perimeter,
                unit_price=ADDON_PRICES["cornice"],
                total=perimeter * ADDON_PRICES["cornice"],
            ))

        if addons.profile_rounding:
            details.append(QuoteAddonDetail(
                name="Profile rounding",
                quantity=Decimal("1"),
                unit_price=ADDON_PRICES["profile_rounding"],
                total=ADDON_PRICES["profile_rounding"],
            ))

        if addons.two_level_step:
            details.append(QuoteAddonDetail(
                name="Two-level step",
                quantity=Decimal("1"),
                unit_price=ADDON_PRICES["two_level_step"],
                total=ADDON_PRICES["two_level_step"],
            ))

        return details
