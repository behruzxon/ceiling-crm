"""
core.services.stage4_approval_report_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Read-only APPROVAL_REQUIRED observation report. No mutations, no sends.
"""
from __future__ import annotations
from datetime import UTC, datetime
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from core.schemas.stage4_approval_report import (
    Stage4ApprovalReport, Stage4NoSendSafetyMetrics, Stage4PassFailResult,
)
from shared.logging import get_logger

log = get_logger(__name__)


class Stage4ApprovalReportService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def build_report(
        self, since: datetime, until: datetime, environment: str = "unknown",
    ) -> Stage4ApprovalReport:
        now = datetime.now(UTC)
        duration = int((until - since).total_seconds() / 60)
        m = await self._collect_metrics(since, until)
        ns = await self._collect_no_send(since, until)
        health = await self._get_health()

        report = Stage4ApprovalReport(
            generated_at=now.isoformat(), since=since.isoformat(),
            until=until.isoformat(), environment=environment,
            duration_minutes=duration, **m, no_send=ns, health_status=health,
        )
        pf = self.evaluate_pass_fail(report)
        recs = self.build_recommendations(report, pf)
        return Stage4ApprovalReport(
            generated_at=report.generated_at, since=report.since,
            until=report.until, environment=report.environment,
            duration_minutes=report.duration_minutes,
            total_proposals=report.total_proposals,
            proposed_count=report.proposed_count,
            approved_count=report.approved_count,
            rejected_count=report.rejected_count,
            expired_count=report.expired_count,
            blocked_count=report.blocked_count,
            executed_count=report.executed_count,
            pending_count=report.pending_count,
            stale_pending_count=report.stale_pending_count,
            no_send=report.no_send, health_status=report.health_status,
            pass_fail=pf, recommendations=recs,
        )

    @staticmethod
    def evaluate_pass_fail(report: Stage4ApprovalReport) -> Stage4PassFailResult:
        failures: list[str] = []
        warnings: list[str] = []
        ns = report.no_send
        if ns.executed_records_count > 0:
            failures.append(f"executed:{ns.executed_records_count}")
        if ns.live_sender_executed > 0:
            failures.append(f"live_sender:{ns.live_sender_executed}")
        if ns.auto_execute_count > 0:
            failures.append(f"auto_execute:{ns.auto_execute_count}")
        if ns.user_dm_sent_count > 0:
            failures.append(f"user_dm_sent:{ns.user_dm_sent_count}")
        if report.health_status == "red":
            failures.append("health_red")
        if report.stale_pending_count > 10:
            warnings.append("stale_pending_high")
        if report.total_proposals == 0:
            warnings.append("no_proposals")
        total = report.total_proposals or 1
        if report.rejected_count / total > 0.5 and report.total_proposals > 10:
            warnings.append("high_rejection_rate")
        if report.expired_count / total > 0.3 and report.total_proposals > 10:
            warnings.append("high_expiration_rate")
        return Stage4PassFailResult(passed=len(failures) == 0, failures=failures, warnings=warnings)

    @staticmethod
    def build_recommendations(
        report: Stage4ApprovalReport, pf: Stage4PassFailResult,
    ) -> list[str]:
        if not pf.passed:
            if any("executed" in f or "live_sender" in f or "auto_execute" in f for f in pf.failures):
                return ["Executed records detected — rollback OFF immediately"]
            return ["APPROVAL FAIL — investigate and rollback"]
        if report.total_proposals == 0:
            return ["No proposals yet — continue approval testing"]
        if "high_rejection_rate" in pf.warnings:
            return ["High rejection rate — inspect offer/policy quality"]
        if "stale_pending_high" in pf.warnings:
            return ["Too many stale pending — improve operator workflow"]
        if report.total_proposals >= 20 and pf.passed:
            return ["APPROVAL_REQUIRED PASS — prepare Stage 5 Approved Live Send"]
        return ["APPROVAL active — continue testing"]

    async def _collect_metrics(self, since: datetime, until: datetime) -> dict:
        try:
            from infrastructure.database.models.agent_execution_record import (
                AgentExecutionRecordModel as M,
            )
            status_q = (
                sa.select(M.status, sa.func.count())
                .where(M.created_at.between(since, until))
                .group_by(M.status)
            )
            rows = (await self._session.execute(status_q)).all()
            by = {str(r[0]): int(r[1]) for r in rows}
            total = sum(by.values())
            return {
                "total_proposals": total, "proposed_count": by.get("proposed", 0),
                "approved_count": by.get("approved", 0), "rejected_count": by.get("rejected", 0),
                "expired_count": by.get("expired", 0), "blocked_count": by.get("blocked", 0),
                "executed_count": by.get("executed", 0), "pending_count": by.get("proposed", 0),
                "stale_pending_count": 0,
            }
        except Exception:
            return {"total_proposals": 0, "proposed_count": 0, "approved_count": 0,
                    "rejected_count": 0, "expired_count": 0, "blocked_count": 0,
                    "executed_count": 0, "pending_count": 0, "stale_pending_count": 0}

    async def _collect_no_send(self, since: datetime, until: datetime) -> Stage4NoSendSafetyMetrics:
        executed = 0
        try:
            from infrastructure.database.models.agent_execution_record import (
                AgentExecutionRecordModel as M,
            )
            r = await self._session.execute(
                sa.select(sa.func.count()).select_from(M).where(M.executed_at.between(since, until)),
            )
            executed = r.scalar() or 0
        except Exception:
            pass
        return Stage4NoSendSafetyMetrics(executed_records_count=executed)

    async def _get_health(self) -> str:
        try:
            from core.services.agent_metrics_service import AgentMetricsService
            return (await AgentMetricsService(self._session).get_overview()).health.status
        except Exception:
            return "green"
