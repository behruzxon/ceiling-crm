"""
core.services.lead_analytics_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Read-only analytics service combining lead_action_repo and lead_repo queries.

Wired by infrastructure/di.py::get_lead_analytics_service(session).
Does not import infrastructure directly — uses duck-typed Any repos so the
core layer stays free of infrastructure dependencies.
"""

from __future__ import annotations

from typing import Any


class LeadAnalyticsService:
    """Aggregates analytics queries from action repo + lead repo."""

    def __init__(self, action_repo: Any, lead_repo: Any) -> None:
        self._actions = action_repo
        self._leads = lead_repo

    async def opstats(self, days: int) -> dict[str, Any]:
        """Full operator stats for the last *days* days.

        Returns::

            {
                "days": int,
                "leaderboard": [...],   # list[dict] from get_operator_leaderboard
                "resp_stats": {...},    # dict from get_first_response_stats
                "funnel": {...},        # dict from get_funnel_stats
            }
        """
        leaderboard = await self._actions.get_operator_leaderboard(days)
        resp_stats = await self._actions.get_first_response_stats(days)
        funnel = await self._actions.get_funnel_stats(days)
        return {
            "days": days,
            "leaderboard": leaderboard,
            "resp_stats": resp_stats,
            "funnel": funnel,
        }

    async def funnel(self, days: int) -> dict[str, Any]:
        """Funnel stage/status distribution for the last *days* days."""
        return await self._actions.get_funnel_stats(days)

    async def lead_card(self, lead_id: int) -> tuple[Any, list[dict[str, Any]]]:
        """Lead domain object + last 10 action timeline entries.

        Returns (None, []) if the lead does not exist.
        """
        lead = await self._leads.get_by_id(lead_id)
        timeline = await self._actions.get_lead_timeline(lead_id, limit=10)
        return lead, timeline
