"""
core.services.agent_metrics_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Read-only metrics aggregation for the agent system.
No mutations, no sends, no AI calls.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from core.schemas.agent_metrics import (
    AdminEscalationMetrics,
    AgentHealthMetrics,
    AgentMetricsOverview,
    ExecutionMetrics,
    FollowupMetrics,
    JourneyMetrics,
    LeadMetrics,
    SafetyMetrics,
)
from shared.logging import get_logger

log = get_logger(__name__)


class AgentMetricsService:
    """Read-only agent system metrics."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_overview(
        self,
        now: datetime | None = None,
        since: datetime | None = None,
    ) -> AgentMetricsOverview:
        if now is None:
            now = datetime.now(UTC)
        journey = await self.get_journey_metrics(since)
        leads = await self.get_lead_metrics()
        followups = await self.get_followup_metrics(now)
        escalations = await self.get_admin_escalation_metrics(since)
        executions = await self.get_execution_metrics()
        safety = await self.get_safety_metrics()
        health = self.compute_health(
            pending_due=followups.due_count,
            failed_24h=followups.failed,
            expired_approvals=executions.expired,
            execution_failures=executions.by_status.get("failed", 0),
        )
        return AgentMetricsOverview(
            journey=journey,
            leads=leads,
            followups=followups,
            escalations=escalations,
            executions=executions,
            safety=safety,
            health=health,
        )

    async def get_journey_metrics(
        self,
        since: datetime | None = None,
    ) -> JourneyMetrics:
        try:
            from infrastructure.database.models.journey_event import (
                JourneyEventModel,
            )

            base = sa.select(JourneyEventModel)
            if since:
                base = base.where(JourneyEventModel.created_at >= since)

            total_q = sa.select(sa.func.count()).select_from(
                base.subquery(),
            )
            total = (await self._session.execute(total_q)).scalar() or 0

            active_q = sa.select(
                sa.func.count(sa.distinct(JourneyEventModel.user_id)),
            )
            if since:
                active_q = active_q.where(JourneyEventModel.created_at >= since)
            active = (await self._session.execute(active_q)).scalar() or 0

            type_q = sa.select(JourneyEventModel.event_type, sa.func.count()).group_by(
                JourneyEventModel.event_type
            )
            if since:
                type_q = type_q.where(JourneyEventModel.created_at >= since)
            type_rows = (await self._session.execute(type_q)).all()
            by_type = {str(r[0]): int(r[1]) for r in type_rows}

            return JourneyMetrics(
                total_events=total,
                events_by_type=by_type,
                active_users=active,
                catalog_opened=by_type.get("opened_catalog", 0),
                price_calculated=by_type.get("price_calculated", 0),
                order_started=by_type.get("order_form_started", 0),
                phone_shared=by_type.get("phone_shared", 0),
                operator_requested=by_type.get("operator_requested", 0),
            )
        except Exception:
            return JourneyMetrics()

    async def get_lead_metrics(self) -> LeadMetrics:
        try:
            from infrastructure.database.models.agent_memory import (
                AgentMemoryModel,
            )

            total = (
                await self._session.execute(
                    sa.select(sa.func.count()).select_from(AgentMemoryModel),
                )
            ).scalar() or 0

            temp_q = sa.select(AgentMemoryModel.lead_temperature, sa.func.count()).group_by(
                AgentMemoryModel.lead_temperature
            )
            temp_rows = (await self._session.execute(temp_q)).all()
            temp_map = {str(r[0]): int(r[1]) for r in temp_rows}

            stopped = (
                await self._session.execute(
                    sa.select(sa.func.count())
                    .select_from(AgentMemoryModel)
                    .where(
                        AgentMemoryModel.followup_enabled == sa.false(),
                    ),
                )
            ).scalar() or 0

            return LeadMetrics(
                total_memories=total,
                hot_count=temp_map.get("hot", 0),
                warm_count=temp_map.get("warm", 0),
                cold_count=temp_map.get("cold", 0),
                stopped_count=stopped,
            )
        except Exception:
            return LeadMetrics()

    async def get_followup_metrics(
        self,
        now: datetime | None = None,
    ) -> FollowupMetrics:
        try:
            from infrastructure.database.models.scheduled_followup import (
                ScheduledFollowupModel,
            )

            if now is None:
                now = datetime.now(UTC)

            status_q = sa.select(ScheduledFollowupModel.status, sa.func.count()).group_by(
                ScheduledFollowupModel.status
            )
            status_rows = (await self._session.execute(status_q)).all()
            by_status = {str(r[0]): int(r[1]) for r in status_rows}

            type_q = sa.select(ScheduledFollowupModel.followup_type, sa.func.count()).group_by(
                ScheduledFollowupModel.followup_type
            )
            type_rows = (await self._session.execute(type_q)).all()
            by_type = {str(r[0]): int(r[1]) for r in type_rows}

            due = (
                await self._session.execute(
                    sa.select(sa.func.count())
                    .select_from(ScheduledFollowupModel)
                    .where(
                        ScheduledFollowupModel.status == "pending",
                        ScheduledFollowupModel.scheduled_at <= now,
                    ),
                )
            ).scalar() or 0

            total = sum(by_status.values())

            return FollowupMetrics(
                total=total,
                pending=by_status.get("pending", 0),
                sent=by_status.get("sent", 0),
                cancelled=by_status.get("cancelled", 0),
                failed=by_status.get("failed", 0),
                skipped=by_status.get("skipped", 0),
                by_type=by_type,
                due_count=due,
            )
        except Exception:
            return FollowupMetrics()

    async def get_admin_escalation_metrics(
        self,
        since: datetime | None = None,
    ) -> AdminEscalationMetrics:
        try:
            from infrastructure.database.models.agent_memory import (
                AgentMemoryModel,
            )

            total = (
                await self._session.execute(
                    sa.select(sa.func.sum(AgentMemoryModel.admin_escalation_count)),
                )
            ).scalar() or 0

            cutoff = datetime.now(UTC) - timedelta(hours=24)
            last_24h = (
                await self._session.execute(
                    sa.select(sa.func.count())
                    .select_from(AgentMemoryModel)
                    .where(
                        AgentMemoryModel.last_admin_escalation_at >= cutoff,
                    ),
                )
            ).scalar() or 0

            return AdminEscalationMetrics(
                total=int(total),
                last_24h=last_24h,
            )
        except Exception:
            return AdminEscalationMetrics()

    async def get_execution_metrics(self) -> ExecutionMetrics:
        try:
            from infrastructure.database.models.agent_execution_record import (
                AgentExecutionRecordModel,
            )

            status_q = sa.select(AgentExecutionRecordModel.status, sa.func.count()).group_by(
                AgentExecutionRecordModel.status
            )
            status_rows = (await self._session.execute(status_q)).all()
            by_status = {str(r[0]): int(r[1]) for r in status_rows}

            mode_q = sa.select(AgentExecutionRecordModel.mode, sa.func.count()).group_by(
                AgentExecutionRecordModel.mode
            )
            mode_rows = (await self._session.execute(mode_q)).all()
            by_mode = {str(r[0]): int(r[1]) for r in mode_rows}

            pending = by_status.get("proposed", 0)
            expired = by_status.get("expired", 0)
            blocked = by_status.get("blocked", 0)
            total = sum(by_status.values())

            return ExecutionMetrics(
                total=total,
                by_status=by_status,
                by_mode=by_mode,
                pending_approval=pending,
                expired=expired,
                blocked=blocked,
            )
        except Exception:
            return ExecutionMetrics()

    async def get_safety_metrics(self) -> SafetyMetrics:
        try:
            from infrastructure.database.models.agent_memory import (
                AgentMemoryModel,
            )

            stop_count = (
                await self._session.execute(
                    sa.select(sa.func.count())
                    .select_from(AgentMemoryModel)
                    .where(
                        AgentMemoryModel.stop_reason.isnot(None),
                    ),
                )
            ).scalar() or 0

            blocked = 0
            try:
                from infrastructure.database.models.agent_execution_record import (
                    AgentExecutionRecordModel,
                )

                blocked = (
                    await self._session.execute(
                        sa.select(sa.func.count())
                        .select_from(
                            AgentExecutionRecordModel,
                        )
                        .where(AgentExecutionRecordModel.status == "blocked"),
                    )
                ).scalar() or 0
            except Exception:
                pass

            return SafetyMetrics(
                stop_signals=stop_count,
                sandbox_blocked=blocked,
            )
        except Exception:
            return SafetyMetrics()

    @staticmethod
    def compute_health(
        *,
        pending_due: int = 0,
        failed_24h: int = 0,
        expired_approvals: int = 0,
        execution_failures: int = 0,
        stale_followups: int = 0,
    ) -> AgentHealthMetrics:
        warnings: list[str] = []
        status = "green"

        if failed_24h > 20 or stale_followups > 0 or execution_failures > 10:
            status = "red"
            if failed_24h > 20:
                warnings.append("failed_followups_critical")
            if stale_followups > 0:
                warnings.append("stale_followups_detected")
            if execution_failures > 10:
                warnings.append("execution_failures_high")
        elif pending_due > 20 or failed_24h > 5 or expired_approvals > 10:
            status = "yellow"
            if pending_due > 20:
                warnings.append("pending_followups_high")
            if failed_24h > 5:
                warnings.append("failed_followups_elevated")
            if expired_approvals > 10:
                warnings.append("expired_approvals_high")

        return AgentHealthMetrics(
            status=status,
            pending_followups_due=pending_due,
            failed_followups_24h=failed_24h,
            stale_followups=stale_followups,
            expired_approvals=expired_approvals,
            execution_failures=execution_failures,
            warnings=warnings,
        )
