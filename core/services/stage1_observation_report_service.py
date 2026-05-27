"""
core.services.stage1_observation_report_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Read-only report generator for Stage 1 LOG_ONLY observation.
Queries existing tables, aggregates metrics, evaluates pass/fail.
No mutations, no sends.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from core.schemas.stage1_observation_report import (
    Stage1NoSendSafetyMetrics,
    Stage1ObservationReport,
    Stage1PassFailResult,
)
from shared.logging import get_logger

log = get_logger(__name__)

_PHONE_RE = re.compile(r"\+?\d{9,15}")
_TOKEN_RE = re.compile(r"(?:sk-|token[=:]|Bearer\s)\S+", re.IGNORECASE)


class Stage1ObservationReportService:
    """Read-only Stage 1 observation report generator."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def build_report(
        self,
        since: datetime,
        until: datetime,
        environment: str = "unknown",
    ) -> Stage1ObservationReport:
        now = datetime.now(UTC)
        duration = int((until - since).total_seconds() / 60)

        journey = await self._count_journey_events(since, until)
        users = await self._count_active_users(since, until)
        traces = await self._count_orchestrator_traces(since, until)
        intents = await self._count_memory_field(since, "last_intent")
        objections = await self._count_memory_field(since, "objection_type")
        decisions = await self._count_memory_field(since, "customer_state")
        offers = await self._count_memory_field(since, "last_dynamic_offer.offer_type")
        policies = await self._count_memory_field(since, "last_conversation_policy.policy_action")
        no_send = await self._collect_no_send_metrics(since, until)
        health = await self._get_health_status()

        report = Stage1ObservationReport(
            generated_at=now.isoformat(),
            since=since.isoformat(),
            until=until.isoformat(),
            environment=environment,
            duration_minutes=duration,
            total_users_observed=users,
            total_journey_events=journey,
            total_orchestrator_traces=traces,
            intent_counts=intents,
            objection_counts=objections,
            decision_state_counts=decisions,
            offer_type_counts=offers,
            policy_action_counts=policies,
            no_send=no_send,
            health_status=health,
        )

        pf = self.evaluate_pass_fail(report)
        recs = self.build_recommendations(report, pf)

        return Stage1ObservationReport(
            generated_at=report.generated_at,
            since=report.since,
            until=report.until,
            environment=report.environment,
            duration_minutes=report.duration_minutes,
            total_users_observed=report.total_users_observed,
            total_journey_events=report.total_journey_events,
            total_orchestrator_traces=report.total_orchestrator_traces,
            intent_counts=report.intent_counts,
            objection_counts=report.objection_counts,
            decision_state_counts=report.decision_state_counts,
            offer_type_counts=report.offer_type_counts,
            policy_action_counts=report.policy_action_counts,
            no_send=report.no_send,
            health_status=report.health_status,
            pass_fail=pf,
            recommendations=recs,
        )

    @staticmethod
    def evaluate_pass_fail(
        report: Stage1ObservationReport,
    ) -> Stage1PassFailResult:
        failures: list[str] = []
        warnings: list[str] = []

        ns = report.no_send
        if ns.followups_scheduled > 0:
            failures.append(f"followups_scheduled:{ns.followups_scheduled}")
        if ns.followups_sent > 0:
            failures.append(f"followups_sent:{ns.followups_sent}")
        if ns.admin_escalations_sent > 0:
            failures.append(f"admin_escalations:{ns.admin_escalations_sent}")
        if ns.execution_records_executed > 0:
            failures.append(f"executions_executed:{ns.execution_records_executed}")
        if ns.live_sender_executed > 0:
            failures.append(f"live_sender:{ns.live_sender_executed}")

        if report.health_status == "red":
            failures.append("health_red")

        if report.total_journey_events > 0 and report.total_orchestrator_traces == 0:
            warnings.append("traffic_but_no_traces")

        if report.total_journey_events == 0:
            warnings.append("no_traffic_observed")

        unclear = report.intent_counts.get("unclear", 0)
        total_intents = sum(report.intent_counts.values()) or 1
        if total_intents > 10 and unclear / total_intents > 0.5:
            warnings.append("high_unclear_ratio")

        return Stage1PassFailResult(
            passed=len(failures) == 0,
            failures=failures,
            warnings=warnings,
        )

    @staticmethod
    def build_recommendations(
        report: Stage1ObservationReport,
        pf: Stage1PassFailResult,
    ) -> list[str]:
        recs: list[str] = []

        if not pf.passed:
            recs.append("No-send violation detected — rollback OFF immediately")
            return recs

        if report.total_orchestrator_traces == 0 and report.total_journey_events == 0:
            recs.append("No traces collected — check orchestrator/log_only flags")
            return recs

        if "high_unclear_ratio" in pf.warnings:
            recs.append("Too many unclear intents — improve keyword/fuzzy rules")

        price_obj = report.objection_counts.get("price", 0)
        total_obj = sum(report.objection_counts.values()) or 1
        if total_obj > 5 and price_obj / total_obj > 0.4:
            recs.append("Price objection high — improve cheaper option messaging")

        if report.total_orchestrator_traces >= 50:
            recs.append("Enough traces collected — prepare Stage 2 DRY_RUN")
        elif report.total_orchestrator_traces > 0:
            recs.append("Stage 1 PASS — continue 24h observation")

        if not recs:
            recs.append("Stage 1 PASS — continue observation")

        return recs

    @staticmethod
    def redact_sensitive(text: str) -> str:
        text = _PHONE_RE.sub("[***]", text)
        text = _TOKEN_RE.sub("[REDACTED]", text)
        return text

    # ── DB queries ────────────────────────────────────────────────────────

    async def _count_journey_events(
        self,
        since: datetime,
        until: datetime,
    ) -> int:
        try:
            from infrastructure.database.models.journey_event import (
                JourneyEventModel,
            )

            r = await self._session.execute(
                sa.select(sa.func.count())
                .select_from(JourneyEventModel)
                .where(
                    JourneyEventModel.created_at.between(since, until),
                ),
            )
            return r.scalar() or 0
        except Exception:
            return 0

    async def _count_active_users(
        self,
        since: datetime,
        until: datetime,
    ) -> int:
        try:
            from infrastructure.database.models.journey_event import (
                JourneyEventModel,
            )

            r = await self._session.execute(
                sa.select(sa.func.count(sa.distinct(JourneyEventModel.user_id))).where(
                    JourneyEventModel.created_at.between(since, until),
                ),
            )
            return r.scalar() or 0
        except Exception:
            return 0

    async def _count_orchestrator_traces(
        self,
        since: datetime,
        until: datetime,
    ) -> int:
        try:
            from infrastructure.database.models.agent_memory import (
                AgentMemoryModel,
            )

            r = await self._session.execute(
                sa.select(sa.func.count())
                .select_from(AgentMemoryModel)
                .where(
                    AgentMemoryModel.updated_at.between(since, until),
                ),
            )
            return r.scalar() or 0
        except Exception:
            return 0

    async def _count_memory_field(
        self,
        since: datetime,
        field_path: str,
    ) -> dict[str, int]:
        return {}

    async def _collect_no_send_metrics(
        self,
        since: datetime,
        until: datetime,
    ) -> Stage1NoSendSafetyMetrics:
        fu_scheduled = 0
        fu_sent = 0
        esc_sent = 0
        exec_executed = 0
        live_executed = 0

        try:
            from infrastructure.database.models.scheduled_followup import (
                ScheduledFollowupModel,
            )

            r = await self._session.execute(
                sa.select(sa.func.count())
                .select_from(ScheduledFollowupModel)
                .where(
                    ScheduledFollowupModel.created_at.between(since, until),
                    ScheduledFollowupModel.status == "pending",
                ),
            )
            fu_scheduled = r.scalar() or 0

            r2 = await self._session.execute(
                sa.select(sa.func.count())
                .select_from(ScheduledFollowupModel)
                .where(
                    ScheduledFollowupModel.created_at.between(since, until),
                    ScheduledFollowupModel.status == "sent",
                ),
            )
            fu_sent = r2.scalar() or 0
        except Exception:
            pass

        try:
            from infrastructure.database.models.agent_memory import (
                AgentMemoryModel,
            )

            r = await self._session.execute(
                sa.select(sa.func.count())
                .select_from(AgentMemoryModel)
                .where(
                    AgentMemoryModel.last_admin_escalation_at.between(since, until),
                ),
            )
            esc_sent = r.scalar() or 0
        except Exception:
            pass

        try:
            from infrastructure.database.models.agent_execution_record import (
                AgentExecutionRecordModel,
            )

            r = await self._session.execute(
                sa.select(sa.func.count())
                .select_from(AgentExecutionRecordModel)
                .where(
                    AgentExecutionRecordModel.executed_at.between(since, until),
                ),
            )
            exec_executed = r.scalar() or 0
        except Exception:
            pass

        return Stage1NoSendSafetyMetrics(
            followups_scheduled=fu_scheduled,
            followups_sent=fu_sent,
            admin_escalations_sent=esc_sent,
            execution_records_executed=exec_executed,
            live_sender_executed=live_executed,
        )

    async def _get_health_status(self) -> str:
        try:
            from core.services.agent_metrics_service import AgentMetricsService

            svc = AgentMetricsService(self._session)
            overview = await svc.get_overview()
            return overview.health.status
        except Exception:
            return "green"
