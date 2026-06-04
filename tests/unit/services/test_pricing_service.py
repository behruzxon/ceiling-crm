"""Unit tests for PricingService quote calculation.

Money-path matrix for the revenue-critical quote engine. Formula (frozen here as
existing behavior — these tests do not change service logic):

    base_total = base_price_per_sqm * area_sqm * district_modifier
    perimeter  = (area_sqm ** 0.5) * 4            # rough square-room estimate
    addons_total = sum of per-addon totals, where
        led_strip / led_rgb / cornice  -> perimeter * unit_price   (linear meters)
        chandelier_holes / spot_holes  -> count * unit_price       (per hole)
        profile_rounding / two_level   -> flat unit_price          (qty 1)
    subtotal = base_total + addons_total
    total    = subtotal * (100 - discount_pct) / 100               # no rounding

Add-on unit prices (UZS): led_strip 25000, led_rgb 40000, cornice 15000,
chandelier 50000, spot 30000, profile_rounding 80000, two_level_step 200000.

All tests are deterministic and offline: get_base_price / get_district_modifier
are mocked (no Redis), or get_redis is patched with an in-memory fake.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from core.domain.lead import LeadAddons
from core.domain.quote import Quote, QuoteAddonDetail
from core.services.pricing_service import PricingService
from shared.constants.enums import CeilingCategory
from shared.constants.pricing import DEFAULT_BASE_PRICES


def _perimeter(area: str) -> Decimal:
    """Replicate the service's perimeter estimate exactly (side * 4, int 4)."""
    return Decimal(area) ** Decimal("0.5") * 4


async def _quote(
    *,
    category: CeilingCategory = CeilingCategory.HI_TECH,
    base: str = "120000",
    area: str = "20",
    modifier: str = "1.00",
    addons: LeadAddons | None = None,
    discount: str = "0",
    district: str = "testdistrict",
) -> Quote:
    """Build a quote with base price + district modifier mocked (no Redis)."""
    svc = PricingService()
    svc.get_base_price = AsyncMock(return_value=Decimal(base))
    svc.get_district_modifier = AsyncMock(return_value=Decimal(modifier))
    return await svc.calculate_quote(
        lead_id=1,
        category=category,
        area_sqm=Decimal(area),
        district=district,
        addons=addons or LeadAddons(),
        created_by=1,
        discount_pct=Decimal(discount),
    )


def _addon(q: Quote, name: str) -> QuoteAddonDetail:
    return next(a for a in q.addons_detail if a.name == name)


# ── original happy-path smoke (kept) ─────────────────────────────────────────


class TestPricingService:
    def setup_method(self):
        self.svc = PricingService()

    @pytest.mark.asyncio
    async def test_calculate_quote_returns_quote(self):
        self.svc.get_base_price = AsyncMock(return_value=Decimal("120000"))
        self.svc.get_district_modifier = AsyncMock(return_value=Decimal("1.0"))
        result = await self.svc.calculate_quote(
            lead_id=1,
            category=CeilingCategory.HI_TECH,
            area_sqm=Decimal("25"),
            district="Yunusabad",
            addons=LeadAddons(),
            created_by=1,
        )
        assert result.lead_id == 1
        assert result.area_sqm == Decimal("25")


# ── base price + district modifier resolution (cache hit vs default) ──────────


class _FakeRedis:
    def __init__(self, value: str | None):
        self._value = value

    async def get(self, key: str) -> str | None:
        return self._value


class TestPriceResolution:
    async def test_base_price_falls_back_to_default_when_uncached(self, monkeypatch):
        monkeypatch.setattr("core.services.pricing_service.get_redis", lambda: _FakeRedis(None))
        svc = PricingService()
        rate = await svc.get_base_price(CeilingCategory.GULLI)
        assert rate == DEFAULT_BASE_PRICES[CeilingCategory.GULLI] == Decimal("250000")

    async def test_base_price_uses_cached_value(self, monkeypatch):
        monkeypatch.setattr("core.services.pricing_service.get_redis", lambda: _FakeRedis("175000"))
        svc = PricingService()
        assert await svc.get_base_price(CeilingCategory.HI_TECH) == Decimal("175000")

    async def test_district_modifier_defaults_to_one(self, monkeypatch):
        monkeypatch.setattr("core.services.pricing_service.get_redis", lambda: _FakeRedis(None))
        svc = PricingService()
        assert await svc.get_district_modifier("anywhere") == Decimal("1.00")

    async def test_district_modifier_uses_cached_value(self, monkeypatch):
        monkeypatch.setattr("core.services.pricing_service.get_redis", lambda: _FakeRedis("1.30"))
        svc = PricingService()
        assert await svc.get_district_modifier("Qarshi") == Decimal("1.30")


# ── base × area × district modifier ──────────────────────────────────────────


class TestBaseAndDistrictMath:
    async def test_base_happy_path_modifier_one(self):
        q = await _quote(base="120000", area="20", modifier="1.00")
        assert q.base_total == Decimal("2400000")
        assert q.addons_total == 0
        assert q.subtotal == Decimal("2400000")
        assert q.total == Decimal("2400000")

    async def test_district_modifier_scales_base(self):
        q = await _quote(base="120000", area="20", modifier="1.20")
        assert q.base_total == Decimal("2880000")
        assert q.total == Decimal("2880000")

    async def test_district_modifier_below_one(self):
        q = await _quote(base="120000", area="20", modifier="0.90")
        assert q.base_total == Decimal("2160000")

    @pytest.mark.parametrize(
        "category,expected",
        [
            (CeilingCategory.ODNOTONNY, Decimal("120000")),
            (CeilingCategory.GULLI, Decimal("250000")),
            (CeilingCategory.KOSMOS, Decimal("300000")),
        ],
    )
    async def test_base_total_uses_category_rate(self, category, expected):
        q = await _quote(category=category, base=str(expected), area="10", modifier="1.00")
        assert q.base_price_per_sqm == expected
        assert q.base_total == expected * 10


# ── perimeter-based add-ons (linear meters) ──────────────────────────────────


class TestPerimeterAddons:
    async def test_led_strip_priced_per_perimeter(self):
        q = await _quote(area="20", addons=LeadAddons(led_strip=True))
        a = _addon(q, "LED strip")
        assert a.unit_price == Decimal("25000")
        assert a.quantity == _perimeter("20")  # perimeter, not area
        assert a.total == _perimeter("20") * Decimal("25000")
        assert q.addons_total == a.total

    async def test_led_rgb_priced_per_perimeter(self):
        q = await _quote(area="20", addons=LeadAddons(led_rgb=True))
        a = _addon(q, "LED RGB")
        assert a.unit_price == Decimal("40000")
        assert a.total == _perimeter("20") * Decimal("40000")

    async def test_cornice_priced_per_perimeter(self):
        q = await _quote(area="20", addons=LeadAddons(cornice=True))
        a = _addon(q, "Cornice")
        assert a.unit_price == Decimal("15000")
        assert a.total == _perimeter("20") * Decimal("15000")

    async def test_multiple_perimeter_addons_sum(self):
        q = await _quote(area="20", addons=LeadAddons(led_strip=True, cornice=True))
        perim = _perimeter("20")
        assert len(q.addons_detail) == 2
        assert q.addons_total == perim * Decimal("25000") + perim * Decimal("15000")


# ── count-based and flat add-ons ─────────────────────────────────────────────


class TestCountAndFlatAddons:
    async def test_chandelier_holes_priced_per_count(self):
        q = await _quote(addons=LeadAddons(chandelier_holes=3))
        a = _addon(q, "Chandelier holes")
        assert a.quantity == Decimal("3")
        assert a.unit_price == Decimal("50000")
        assert a.total == Decimal("150000")

    async def test_spot_holes_priced_per_count(self):
        q = await _quote(addons=LeadAddons(spot_holes=5))
        a = _addon(q, "Spot light holes")
        assert a.total == Decimal("150000")  # 5 * 30000

    async def test_zero_holes_produce_no_addon(self):
        q = await _quote(addons=LeadAddons(chandelier_holes=0, spot_holes=0))
        assert q.addons_detail == []
        assert q.addons_total == 0

    async def test_profile_rounding_is_flat_fee(self):
        q = await _quote(addons=LeadAddons(profile_rounding=True))
        a = _addon(q, "Profile rounding")
        assert a.quantity == Decimal("1")
        assert a.total == Decimal("80000")

    async def test_two_level_step_is_flat_fee(self):
        q = await _quote(addons=LeadAddons(two_level_step=True))
        a = _addon(q, "Two-level step")
        assert a.quantity == Decimal("1")
        assert a.total == Decimal("200000")

    async def test_all_addons_combined_sum(self):
        q = await _quote(
            area="20",
            addons=LeadAddons(
                led_strip=True,
                led_rgb=True,
                cornice=True,
                chandelier_holes=2,
                spot_holes=4,
                profile_rounding=True,
                two_level_step=True,
            ),
        )
        perim = _perimeter("20")
        expected = (
            perim * Decimal("25000")  # led_strip
            + perim * Decimal("40000")  # led_rgb
            + perim * Decimal("15000")  # cornice
            + Decimal("2") * Decimal("50000")  # chandelier
            + Decimal("4") * Decimal("30000")  # spot
            + Decimal("80000")  # profile_rounding
            + Decimal("200000")  # two_level_step
        )
        assert len(q.addons_detail) == 7
        assert q.addons_total == expected
        assert q.subtotal == q.base_total + expected


# ── discount application ─────────────────────────────────────────────────────


class TestDiscount:
    @pytest.mark.parametrize(
        "discount,factor",
        [("0", "1.0"), ("5", "0.95"), ("10", "0.90"), ("20", "0.80"), ("100", "0.0")],
    )
    async def test_discount_scales_total(self, discount, factor):
        q = await _quote(base="100000", area="10", modifier="1.00", discount=discount)
        # subtotal == base_total == 1,000,000 (no addons)
        assert q.subtotal == Decimal("1000000")
        assert q.total == Decimal("1000000") * Decimal(factor)

    async def test_full_discount_zeroes_total(self):
        q = await _quote(discount="100")
        assert q.total == 0

    async def test_discount_applies_after_addons(self):
        q = await _quote(
            base="100000",
            area="20",
            modifier="1.00",
            addons=LeadAddons(chandelier_holes=1),
            discount="10",
        )
        # subtotal = 2,000,000 + 50,000 = 2,050,000 ; total = *0.9
        assert q.subtotal == Decimal("2050000")
        assert q.total == Decimal("2050000") * Decimal("90") / Decimal("100")


# ── edge / boundary inputs ───────────────────────────────────────────────────


class TestEdgeCases:
    async def test_zero_area_yields_zero_money(self):
        q = await _quote(area="0", addons=LeadAddons(led_strip=True, chandelier_holes=2))
        assert q.base_total == 0
        # perimeter of 0 area is 0 → perimeter add-ons contribute 0; counts still apply
        assert _addon(q, "LED strip").total == 0
        assert _addon(q, "Chandelier holes").total == Decimal("100000")

    async def test_large_area_no_overflow(self):
        q = await _quote(base="300000", area="100000", modifier="1.00")
        assert q.base_total == Decimal("30000000000")  # 3e10, exact Decimal
        assert q.total == Decimal("30000000000")

    async def test_no_addons_subtotal_equals_base(self):
        q = await _quote(area="33")
        assert q.addons_total == 0
        assert q.subtotal == q.base_total


# ── Quote domain formula in isolation (no service / Redis) ───────────────────


class TestQuoteFormulaDirect:
    def test_pure_formula(self):
        q = Quote(
            id=0,
            lead_id=1,
            category=CeilingCategory.HI_TECH,
            base_price_per_sqm=Decimal("120000"),
            area_sqm=Decimal("20"),
            district_modifier=Decimal("1.5"),
            addons_detail=[
                QuoteAddonDetail(
                    name="X",
                    quantity=Decimal("2"),
                    unit_price=Decimal("50000"),
                    total=Decimal("100000"),
                )
            ],
            discount_pct=Decimal("25"),
            created_by=1,
        )
        assert q.base_total == Decimal("3600000")  # 120000*20*1.5
        assert q.addons_total == Decimal("100000")
        assert q.subtotal == Decimal("3700000")
        assert q.total == Decimal("3700000") * Decimal("75") / Decimal("100")

    def test_quote_is_frozen(self):
        q = Quote(
            id=0,
            lead_id=1,
            category=CeilingCategory.HI_TECH,
            base_price_per_sqm=Decimal("1"),
            area_sqm=Decimal("1"),
            created_by=1,
        )
        with pytest.raises(Exception):
            q.area_sqm = Decimal("2")  # type: ignore[misc]


# ── currency / type consistency ──────────────────────────────────────────────


class TestCurrencyAndType:
    async def test_currency_is_uzs(self):
        q = await _quote()
        assert q.currency == "UZS"

    async def test_totals_are_decimal(self):
        q = await _quote(area="20", addons=LeadAddons(led_strip=True), discount="10")
        for value in (q.base_total, q.addons_total, q.subtotal, q.total):
            assert isinstance(value, Decimal)
