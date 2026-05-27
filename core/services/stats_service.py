"""
core.services.stats_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Aggregate statistics for the admin panel (/stats command).

Metrics returned per period (today / 7d / 30d):
  group_joins     — distinct users who joined the tracked Telegram group
  new_leads       — leads created in the period
  hot_leads       — leads with lead_status='hot' OR score >= HOT_SCORE_THRESHOLD
  measurement     — leads whose lead_status='measurement' (kanban column)
  won             — leads with lead_status='won'
  lost            — leads with lead_status='lost'
  conversion_pct  — won / new_leads × 100  (0.0 when no leads)

All lead metrics are queried in a single SQL aggregation pass.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from core.repositories.group_join_repo import AbstractGroupJoinRepository
from infrastructure.database.models.lead import LeadModel
from shared.logging import get_logger

log = get_logger(__name__)

# Keep in sync with lead_notification_service.HOT_SCORE_THRESHOLD
HOT_SCORE_THRESHOLD = 7


def _since_today() -> datetime:
    """Start of today in UTC (midnight)."""
    now = datetime.now(UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _since_days(days: int) -> datetime:
    return datetime.now(UTC) - timedelta(days=days)


class StatsService:
    """
    Provides period-scoped statistics for the admin panel.

    Instantiated per-request via get_stats_service() in di.py.
    """

    def __init__(
        self,
        session: AsyncSession,
        join_repo: AbstractGroupJoinRepository,
        tracked_group_id: int,
    ) -> None:
        self._session = session
        self._join_repo = join_repo
        self._group_id = tracked_group_id

    async def get_stats(self, period: str) -> dict[str, Any]:
        """Return a stats dict for *period* ("today" | "7d" | "30d").

        Keys: period, group_joins, new_leads, hot_leads,
              measurement, won, lost, conversion_pct
        """
        if period == "today":
            since = _since_today()
        elif period == "7d":
            since = _since_days(7)
        else:  # "30d"
            since = _since_days(30)

        group_joins, new_leads, hot_leads, measurement, won, lost = (
            await self._fetch_all(since)
        )
        conversion_pct = round(won / new_leads * 100, 1) if new_leads else 0.0
        join_to_lead = round(new_leads / group_joins * 100, 1) if group_joins else 0.0
        lead_to_won  = round(won / new_leads * 100, 1)        if new_leads  else 0.0
        join_to_won  = round(won / group_joins * 100, 1)      if group_joins else 0.0

        return {
            "period": period,
            "group_joins": group_joins,
            "new_leads": new_leads,
            "hot_leads": hot_leads,
            "measurement": measurement,
            "won": won,
            "lost": lost,
            "conversion_pct": conversion_pct,
            "join_to_lead_conversion": join_to_lead,
            "lead_to_won_conversion": lead_to_won,
            "join_to_won_conversion": join_to_won,
        }

    async def _fetch_all(
        self, since: datetime
    ) -> tuple[int, int, int, int, int, int]:
        """Run join count + single-pass lead aggregation."""
        group_joins = await self._join_repo.count_joins(self._group_id, since)

        # One SQL query covers all lead metrics for the period.
        def _sum(cond: sa.ColumnElement) -> sa.Label:  # type: ignore[type-arg]
            return sa.func.sum(sa.case((cond, 1), else_=0))

        stmt = sa.select(
            sa.func.count().label("new_leads"),
            _sum(
                sa.or_(
                    LeadModel.lead_status == "hot",
                    LeadModel.score >= HOT_SCORE_THRESHOLD,
                )
            ).label("hot_leads"),
            _sum(LeadModel.lead_status == "measurement").label("measurement"),
            _sum(LeadModel.lead_status == "won").label("won"),
            _sum(LeadModel.lead_status == "lost").label("lost"),
        ).where(LeadModel.created_at >= since)

        row = (await self._session.execute(stmt)).one()
        return (
            group_joins,
            int(row.new_leads or 0),
            int(row.hot_leads or 0),
            int(row.measurement or 0),
            int(row.won or 0),
            int(row.lost or 0),
        )
