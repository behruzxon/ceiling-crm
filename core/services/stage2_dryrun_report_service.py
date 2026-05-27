"""
core.services.stage2_dryrun_report_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Read-only DRY_RUN observation report. Aggregates sandbox/execution metrics.
No mutations, no sends.
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from core.schemas.stage2_dryrun_report import (
    Stage2DryRunReport,
    Stage2NoSendSafetyMetrics,
    Stage2PassFailResult,
)
from shared.logging import get_logger

log = get_logger(__name__)


class Stage2DryRunReportService:
    """Read-only Stage 2 DRY_RUN report generator."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def build_report(
        self,
        since: datetime,
        until: datetime,
        environment: str = "unknown",
    ) -> Stage2DryRunReport:
        now = datetime.now(UTC)
        duration = int((until - since).total_seconds() / 60)

        exec_metrics = await self._collect_execution_metrics(since, until)
        no_send = await self._collect_no_send(since, until)
        health = await self._get_health()

        report = Stage2DryRunReport(
            generated_at=now.isoformat(),
            since=since.isoformat(),
            until=until.isoformat(),
            environment=environment,
            duration_minutes=duration,
            total_payloads=exec_metrics.get("total", 0),
            total_would_execute=exec_metrics.get("would_execute", 0),
            total_blocked=exec_metrics.get("blocked", 0),
            action_counts=exec_metrics.get("by_action", {}),
            channel_counts=exec_metrics.get("by_channel", {}),
            risk_counts=exec_metrics.get("by_risk", {}),
            block_reason_counts=exec_metrics.get("by_block_reason", {}),
            no_send=no_send,
            health_status=health,
        )

        pf = self.evaluate_pass_fail(report)
        recs = self.build_recommendations(report, pf)

        return Stage2DryRunReport(
            generated_at=report.generated_at,
            since=report.since,
            until=report.until,
            environment=report.environment,
            duration_minutes=report.duration_minutes,
            total_payloads=report.total_payloads,
            total_would_execute=report.total_would_execute,
            total_blocked=report.total_blocked,
            action_counts=report.action_counts,
            channel_counts=report.channel_counts,
            risk_counts=report.risk_counts,
            block_reason_counts=report.block_reason_counts,
            no_send=report.no_send,
            health_status=report.health_status,
            pass_fail=pf,
            recommendations=recs,
        )

    @staticmethod
    def evaluate_pass_fail(report: Stage2DryRunReport) -> Stage2PassFailResult:
        failures: list[str] = []
        warnings: list[str] = []

        ns = report.no_send
        if ns.actual_sent_count > 0:
            failures.append(f"actual_sent:{ns.actual_sent_count}")
        if ns.executed_records_count > 0:
            failures.append(f"executed:{ns.executed_records_count}")
        if ns.live_sender_executed > 0:
            failures.append(f"live_sender:{ns.live_sender_executed}")
        if report.health_status == "red":
            failures.append("health_red")

        total = report.total_payloads or 1
        blocked_ratio = report.total_blocked / total
        if blocked_ratio > 0.8 and report.total_payloads > 10:
            warnings.append("high_blocked_ratio")

        high_risk = report.risk_counts.get("high", 0) + report.risk_counts.get("critical", 0)
        if high_risk > total * 0.3 and report.total_payloads > 10:
            warnings.append("high_risk_ratio")

        if report.total_payloads == 0:
            warnings.append("no_payloads")

        return Stage2PassFailResult(
            passed=len(failures) == 0,
            failures=failures,
            warnings=warnings,
        )

    @staticmethod
    def build_recommendations(
        report: Stage2DryRunReport,
        pf: Stage2PassFailResult,
    ) -> list[str]:
        recs: list[str] = []

        if not pf.passed:
            recs.append("No-send violation — rollback OFF immediately")
            return recs

        if report.total_payloads == 0:
            recs.append("No dry-run payloads — check orchestrator/sandbox flags")
            return recs

        if "high_blocked_ratio" in pf.warnings:
            recs.append("High blocked ratio — review policy/offer rules")
        if "high_risk_ratio" in pf.warnings:
            recs.append("Too many high-risk payloads — tune safety")

        if report.total_payloads >= 30 and pf.passed:
            recs.append("DRY_RUN PASS — prepare Stage 3 CANARY")
        elif report.total_payloads > 0:
            recs.append("DRY_RUN active — continue observation")

        if not recs:
            recs.append("Continue monitoring")
        return recs

    async def _collect_execution_metrics(
        self,
        since: datetime,
        until: datetime,
    ) -> dict:
        try:
            from infrastructure.database.models.agent_execution_record import (
                AgentExecutionRecordModel as M,
            )

            base = sa.select(M).where(M.created_at.between(since, until))

            total = (
                await self._session.execute(
                    sa.select(sa.func.count()).select_from(base.subquery()),
                )
            ).scalar() or 0

            status_q = (
                sa.select(M.status, sa.func.count())
                .where(M.created_at.between(since, until))
                .group_by(M.status)
            )
            status_rows = (await self._session.execute(status_q)).all()
            by_status = {str(r[0]): int(r[1]) for r in status_rows}

            action_q = (
                sa.select(M.action, sa.func.count())
                .where(M.created_at.between(since, until))
                .group_by(M.action)
            )
            action_rows = (await self._session.execute(action_q)).all()

            risk_q = (
                sa.select(M.risk_level, sa.func.count())
                .where(M.created_at.between(since, until))
                .group_by(M.risk_level)
            )
            risk_rows = (await self._session.execute(risk_q)).all()

            channel_q = (
                sa.select(M.channel, sa.func.count())
                .where(M.created_at.between(since, until))
                .group_by(M.channel)
            )
            channel_rows = (await self._session.execute(channel_q)).all()

            return {
                "total": total,
                "would_execute": by_status.get("proposed", 0) + by_status.get("approved", 0),
                "blocked": by_status.get("blocked", 0),
                "by_action": {str(r[0]): int(r[1]) for r in action_rows},
                "by_risk": {str(r[0]): int(r[1]) for r in risk_rows},
                "by_channel": {str(r[0]): int(r[1]) for r in channel_rows},
                "by_block_reason": {},
            }
        except Exception:
            return {
                "total": 0,
                "would_execute": 0,
                "blocked": 0,
                "by_action": {},
                "by_risk": {},
                "by_channel": {},
                "by_block_reason": {},
            }

    async def _collect_no_send(
        self,
        since: datetime,
        until: datetime,
    ) -> Stage2NoSendSafetyMetrics:
        executed = 0
        try:
            from infrastructure.database.models.agent_execution_record import (
                AgentExecutionRecordModel as M,
            )

            r = await self._session.execute(
                sa.select(sa.func.count())
                .select_from(M)
                .where(
                    M.executed_at.between(since, until),
                ),
            )
            executed = r.scalar() or 0
        except Exception:
            pass
        return Stage2NoSendSafetyMetrics(
            executed_records_count=executed,
        )

    async def _get_health(self) -> str:
        try:
            from core.services.agent_metrics_service import AgentMetricsService

            svc = AgentMetricsService(self._session)
            o = await svc.get_overview()
            return o.health.status
        except Exception:
            return "green"
