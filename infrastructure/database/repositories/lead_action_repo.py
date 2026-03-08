"""
PostgreSQL repository for lead_actions.

insert()                  — append one action event (caller must commit)
get_operator_stats()      — top-5 operators by action count (legacy, kept for compat)
get_operator_leaderboard()— top-10 by distinct leads handled + HOT conversions
get_first_response_stats()— avg/median seconds from lead creation to first action
get_funnel_stats()        — per-stage and per-status counts for a cohort of leads
get_lead_timeline()       — last N actions for a specific lead
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database.models.lead import LeadModel
from infrastructure.database.models.lead_action import LeadActionModel
from infrastructure.database.models.pipeline_stage import PipelineStageModel
from infrastructure.database.models.user import UserModel
from infrastructure.database.repositories.tenant_scope import TenantScopedRepository
from shared.logging import get_logger

log = get_logger(__name__)

_TZ = ZoneInfo("Asia/Tashkent")


def _since_utc(days: int) -> datetime:
    """Start of window in UTC: now(Tashkent) minus *days* days."""
    now_tz = datetime.now(_TZ)
    return (now_tz - timedelta(days=days)).astimezone(timezone.utc)


class PostgresLeadActionRepository(TenantScopedRepository):
    def __init__(self, session: AsyncSession, tenant_id: int | None = None) -> None:
        super().__init__(session, tenant_id)

    # ── Write ─────────────────────────────────────────────────────────────────

    async def insert(
        self,
        lead_id: int,
        actor_user_id: int,
        action_type: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Append one lead-action event row.

        Caller is responsible for committing the enclosing transaction.
        Never raises — logs and swallows errors so a logging failure never
        aborts the primary business operation.
        """
        try:
            model = LeadActionModel(
                lead_id=lead_id,
                actor_user_id=actor_user_id,
                action_type=action_type,
                payload=payload,
            )
            self._stamp_tenant_id(model)
            self._session.add(model)
        except Exception:
            log.exception(
                "lead_action_insert_error",
                lead_id=lead_id,
                actor_user_id=actor_user_id,
                action_type=action_type,
            )

    # ── Legacy read (kept for backwards-compat) ───────────────────────────────

    async def get_operator_stats(
        self, since_dt: datetime
    ) -> list[dict[str, Any]]:
        """Return top-5 operators by total action count since ``since_dt``.

        Each entry is a dict::

            {
                "actor_user_id": 12345678,
                "first_name": "Ali",
                "username": "ali_ops",   # may be None
                "total": 42,
                "hot": 10, "warm": 8, "cold": 5,
                "phone": 7, "measurement": 5,
                "note": 4, "block": 3,
            }
        """
        def _sum(action: str) -> sa.Label:
            return sa.func.sum(
                sa.case((LeadActionModel.action_type == action, 1), else_=0)
            ).label(action)

        stmt = (
            sa.select(
                LeadActionModel.actor_user_id,
                sa.func.count().label("total"),
                _sum("hot"),
                _sum("warm"),
                _sum("cold"),
                _sum("phone"),
                _sum("measurement"),
                _sum("note"),
                _sum("block"),
            )
            .where(LeadActionModel.created_at >= since_dt)
            .group_by(LeadActionModel.actor_user_id)
            .order_by(sa.desc("total"))
            .limit(5)
        )
        stmt = self._apply_tenant_filter(stmt, LeadActionModel)
        rows = (await self._session.execute(stmt)).mappings().all()
        if not rows:
            return []

        actor_ids = [r["actor_user_id"] for r in rows]
        user_rows = (
            await self._session.execute(
                sa.select(UserModel.id, UserModel.first_name, UserModel.username).where(
                    UserModel.id.in_(actor_ids)
                )
            )
        ).mappings().all()
        user_map: dict[int, Any] = {u["id"]: u for u in user_rows}

        result = []
        for r in rows:
            uid = r["actor_user_id"]
            u = user_map.get(uid, {})
            result.append({
                "actor_user_id": uid,
                "first_name": u.get("first_name") or "—",
                "username": u.get("username"),
                "total": r["total"],
                "hot": r["hot"] or 0,
                "warm": r["warm"] or 0,
                "cold": r["cold"] or 0,
                "phone": r["phone"] or 0,
                "measurement": r["measurement"] or 0,
                "note": r["note"] or 0,
                "block": r["block"] or 0,
            })
        return result

    # ── New analytics queries ─────────────────────────────────────────────────

    async def get_operator_leaderboard(self, days: int) -> list[dict[str, Any]]:
        """Top-10 operators ranked by distinct leads handled in the last *days* days.

        Returns list of dicts::

            {
                "actor_user_id": int,
                "first_name": str,
                "username": str | None,
                "handled_leads": int,   # distinct lead_ids touched
                "total_actions": int,   # total action rows
                "hot_count": int,       # action_type == 'hot'
            }
        """
        since_dt = _since_utc(days)

        stmt = (
            sa.select(
                LeadActionModel.actor_user_id,
                sa.func.count(
                    sa.func.distinct(LeadActionModel.lead_id)
                ).label("handled_leads"),
                sa.func.count().label("total_actions"),
                sa.func.sum(
                    sa.case((LeadActionModel.action_type == "hot", 1), else_=0)
                ).label("hot_count"),
            )
            .where(LeadActionModel.created_at >= since_dt)
            .group_by(LeadActionModel.actor_user_id)
            .order_by(sa.desc("handled_leads"))
            .limit(10)
        )
        stmt = self._apply_tenant_filter(stmt, LeadActionModel)
        rows = (await self._session.execute(stmt)).mappings().all()
        if not rows:
            return []

        actor_ids = [r["actor_user_id"] for r in rows]
        user_rows = (
            await self._session.execute(
                sa.select(UserModel.id, UserModel.first_name, UserModel.username).where(
                    UserModel.id.in_(actor_ids)
                )
            )
        ).mappings().all()
        user_map: dict[int, Any] = {u["id"]: u for u in user_rows}

        result = []
        for r in rows:
            uid = r["actor_user_id"]
            u = user_map.get(uid, {})
            result.append({
                "actor_user_id": uid,
                "first_name": u.get("first_name") or "—",
                "username": u.get("username"),
                "handled_leads": r["handled_leads"],
                "total_actions": r["total_actions"],
                "hot_count": int(r["hot_count"] or 0),
            })
        return result

    async def get_first_response_stats(self, days: int) -> dict[str, Any]:
        """Avg and median seconds from lead creation to first operator action.

        Only counts leads that have at least one action entry.

        Returns::

            {
                "avg_seconds": float | None,
                "median_seconds": float | None,
                "responded_leads": int,
            }
        """
        since_dt = _since_utc(days)

        # Subquery A: leads created in period
        leads_stmt = (
            sa.select(LeadModel.id, LeadModel.created_at)
            .where(LeadModel.created_at >= since_dt)
        )
        leads_stmt = self._apply_tenant_filter(leads_stmt, LeadModel)
        leads_subq = leads_stmt.subquery("leads_in_period")

        # Subquery B: first action timestamp per lead
        first_action_subq = (
            sa.select(
                LeadActionModel.lead_id,
                sa.func.min(LeadActionModel.created_at).label("first_at"),
            )
            .where(LeadActionModel.lead_id.in_(sa.select(leads_subq.c.id)))
            .group_by(LeadActionModel.lead_id)
            .subquery("first_actions")
        )

        # Compute diff in seconds
        diff_expr = sa.func.extract(
            "epoch",
            first_action_subq.c.first_at - leads_subq.c.created_at,
        )

        stmt = (
            sa.select(
                sa.func.avg(diff_expr).label("avg_seconds"),
                sa.func.percentile_cont(0.5)
                .within_group(diff_expr.asc())
                .label("median_seconds"),
                sa.func.count().label("responded_leads"),
            )
            .select_from(leads_subq)
            .join(first_action_subq, leads_subq.c.id == first_action_subq.c.lead_id)
        )

        row = (await self._session.execute(stmt)).mappings().one_or_none()
        if row is None or row["responded_leads"] == 0:
            return {"avg_seconds": None, "median_seconds": None, "responded_leads": 0}

        return {
            "avg_seconds": float(row["avg_seconds"]) if row["avg_seconds"] is not None else None,
            "median_seconds": float(row["median_seconds"]) if row["median_seconds"] is not None else None,
            "responded_leads": int(row["responded_leads"]),
        }

    async def get_funnel_stats(self, days: int) -> dict[str, Any]:
        """Stage and status distribution for leads created in last *days* days.

        Returns::

            {
                "total": int,
                "stage_counts": {"NEW": 10, "MEASUREMENT": 3, ...},
                "status_counts": {"hot": 5, "warm": 8, "cold": 2, "blocked": 1},
            }
        """
        since_dt = _since_utc(days)

        # 1. Total leads created in period
        total_stmt = (
            sa.select(sa.func.count())
            .select_from(LeadModel)
            .where(LeadModel.created_at >= since_dt)
        )
        total_stmt = self._apply_tenant_filter(total_stmt, LeadModel)
        total: int = (
            await self._session.execute(total_stmt)
        ).scalar() or 0

        if total == 0:
            return {"total": 0, "stage_counts": {}, "status_counts": {}}

        # 2. Latest pipeline stage per lead (for leads in cohort)
        lead_ids_stmt = (
            sa.select(LeadModel.id)
            .where(LeadModel.created_at >= since_dt)
        )
        lead_ids_stmt = self._apply_tenant_filter(lead_ids_stmt, LeadModel)
        lead_ids_subq = lead_ids_stmt.subquery("cohort_ids")
        latest_stage_subq = (
            sa.select(
                PipelineStageModel.lead_id,
                PipelineStageModel.stage,
            )
            .where(PipelineStageModel.lead_id.in_(sa.select(lead_ids_subq.c.id)))
            .distinct(PipelineStageModel.lead_id)
            .order_by(
                PipelineStageModel.lead_id,
                PipelineStageModel.created_at.desc(),
            )
            .subquery("latest_stage")
        )
        stage_rows = (
            await self._session.execute(
                sa.select(
                    latest_stage_subq.c.stage,
                    sa.func.count().label("cnt"),
                ).group_by(latest_stage_subq.c.stage)
            )
        ).all()
        stage_counts: dict[str, int] = {r.stage: r.cnt for r in stage_rows}

        # 3. lead_status distribution
        status_stmt = (
            sa.select(
                LeadModel.lead_status,
                sa.func.count().label("cnt"),
            )
            .where(
                LeadModel.created_at >= since_dt,
                LeadModel.lead_status.isnot(None),
            )
            .group_by(LeadModel.lead_status)
        )
        status_stmt = self._apply_tenant_filter(status_stmt, LeadModel)
        status_rows = (
            await self._session.execute(status_stmt)
        ).all()
        status_counts: dict[str, int] = {r.lead_status: r.cnt for r in status_rows}

        return {
            "total": total,
            "stage_counts": stage_counts,
            "status_counts": status_counts,
        }

    async def get_lead_timeline(
        self, lead_id: int, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Last *limit* actions for a specific lead, newest first.

        Each entry::

            {
                "created_at": datetime,
                "action_type": str,
                "actor_user_id": int,
                "payload": dict | None,
                "first_name": str | None,
                "username": str | None,
            }
        """
        stmt = (
            sa.select(
                LeadActionModel.created_at,
                LeadActionModel.action_type,
                LeadActionModel.actor_user_id,
                LeadActionModel.payload,
                UserModel.first_name,
                UserModel.username,
            )
            .outerjoin(UserModel, UserModel.id == LeadActionModel.actor_user_id)
            .where(LeadActionModel.lead_id == lead_id)
            .order_by(LeadActionModel.created_at.desc())
            .limit(limit)
        )
        stmt = self._apply_tenant_filter(stmt, LeadActionModel)
        rows = (await self._session.execute(stmt)).mappings().all()
        return [dict(r) for r in rows]
