"""
AnalyticsService — business metrics and reporting.
"""
from __future__ import annotations
from datetime import date
from shared.logging import get_logger

log = get_logger(__name__)


class AnalyticsService:
    """
    Aggregates business metrics from pipeline data.
    Used by admin dashboard and export service.
    """

    async def get_daily_summary(self, target_date: date) -> dict:
        """Return daily lead/conversion/revenue summary. TODO: implement."""
        raise NotImplementedError

    async def get_category_breakdown(self) -> dict:
        """Return lead counts per category. TODO: implement."""
        raise NotImplementedError

    async def get_conversion_funnel(self) -> dict:
        """Return conversion rates between pipeline stages. TODO: implement."""
        raise NotImplementedError

    async def get_district_distribution(self) -> dict:
        """Return geographic distribution of leads. TODO: implement."""
        raise NotImplementedError

    async def get_revenue_estimate(self, month: int, year: int) -> dict:
        """Estimate revenue from DEAL+ stage quotes. TODO: implement."""
        raise NotImplementedError
