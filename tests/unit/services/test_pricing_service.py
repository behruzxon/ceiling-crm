"""Unit tests for PricingService quote calculation."""
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, patch
from decimal import Decimal
from core.services.pricing_service import PricingService
from core.domain.lead import LeadAddons
from shared.constants.enums import CeilingCategory


class TestPricingService:

    def setup_method(self):
        self.svc = PricingService()

    @pytest.mark.asyncio
    async def test_calculate_quote_raises_not_implemented(self):
        with pytest.raises(NotImplementedError):
            await self.svc.calculate_quote(
                lead_id=1,
                category=CeilingCategory.HI_TECH,
                area_sqm=Decimal("25"),
                district="Yunusabad",
                addons=LeadAddons(),
                created_by=1,
            )
