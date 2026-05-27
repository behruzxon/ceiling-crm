"""Unit tests for PricingService quote calculation."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from core.domain.lead import LeadAddons
from core.services.pricing_service import PricingService
from shared.constants.enums import CeilingCategory


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
