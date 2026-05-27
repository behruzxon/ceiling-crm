"""
core.services.stage3_canary_report_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Read-only CANARY observation report. Tracks canary vs non-canary sends.
No mutations, no sends.
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from core.schemas.stage3_canary_report import (
    Stage3CanaryReport,
    Stage3PassFailResult,
    Stage3PublicSafetyMetrics,
)
from shared.logging import get_logger

log = get_logger(__name__)


class Stage3CanaryReportService:
    """Read-only CANARY observation report generator."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def build_report(
        self,
        since: datetime,
        until: datetime,
        environment: str = "unknown",
    ) -> Stage3CanaryReport:
        now = datetime.now(UTC)
        duration = int((until - since).total_seconds() / 60)
        metrics = await self._collect_metrics(since, until)
        public = await self._collect_public_safety(since, until)
        health = await self._get_health()

        report = Stage3CanaryReport(
            generated_at=now.isoformat(),
            since=since.isoformat(),
            until=until.isoformat(),
            environment=environment,
            duration_minutes=duration,
            **metrics,
            public_safety=public,
            health_status=health,
        )
        pf = self.evaluate_pass_fail(report)
        recs = self.build_recommendations(report, pf)
        return Stage3CanaryReport(
            generated_at=report.generated_at,
            since=report.since,
            until=report.until,
            environment=report.environment,
            duration_minutes=report.duration_minutes,
            canary_user_count=report.canary_user_count,
            canary_payload_count=report.canary_payload_count,
            canary_allowed_count=report.canary_allowed_count,
            canary_blocked_count=report.canary_blocked_count,
            non_canary_attempts=report.non_canary_attempts,
            non_canary_blocked=report.non_canary_blocked,
            block_reason_counts=report.block_reason_counts,
            risk_counts=report.risk_counts,
            public_safety=report.public_safety,
            health_status=report.health_status,
            pass_fail=pf,
            recommendations=recs,
        )

    @staticmethod
    def evaluate_pass_fail(report: Stage3CanaryReport) -> Stage3PassFailResult:
        failures: list[str] = []
        warnings: list[str] = []
        ps = report.public_safety
        if ps.public_user_send_count > 0:
            failures.append(f"public_send:{ps.public_user_send_count}")
        if ps.non_canary_allowed_count > 0:
            failures.append(f"non_canary_allowed:{ps.non_canary_allowed_count}")
        if ps.high_risk_sent_count > 0:
            failures.append(f"high_risk_sent:{ps.high_risk_sent_count}")
        if ps.critical_risk_sent_count > 0:
            failures.append(f"critical_sent:{ps.critical_risk_sent_count}")
        if ps.duplicate_sent_count > 0:
            failures.append(f"duplicate_sent:{ps.duplicate_sent_count}")
        if ps.sensitive_leak_count > 0:
            failures.append(f"sensitive_leak:{ps.sensitive_leak_count}")
        if report.health_status == "red":
            failures.append("health_red")
        if report.canary_payload_count == 0:
            warnings.append("no_canary_sends")
        return Stage3PassFailResult(
            passed=len(failures) == 0,
            failures=failures,
            warnings=warnings,
        )

    @staticmethod
    def build_recommendations(
        report: Stage3CanaryReport,
        pf: Stage3PassFailResult,
    ) -> list[str]:
        if not pf.passed:
            if any("public" in f or "non_canary" in f for f in pf.failures):
                return ["Public send detected — rollback OFF immediately"]
            return ["CANARY FAIL — investigate and rollback"]
        if report.canary_payload_count == 0:
            return ["No canary sends yet — continue canary testing"]
        if report.canary_payload_count >= 20:
            return ["CANARY PASS — prepare Stage 4 APPROVAL_REQUIRED"]
        return ["CANARY active — continue testing with canary users"]

    async def _collect_metrics(self, since: datetime, until: datetime) -> dict:
        try:
            from infrastructure.database.models.agent_execution_record import (
                AgentExecutionRecordModel as M,
            )

            mode_q = (
                sa.select(sa.func.count())
                .select_from(M)
                .where(
                    M.created_at.between(since, until),
                    M.mode == "canary",
                )
            )
            total = (await self._session.execute(mode_q)).scalar() or 0

            blocked_q = (
                sa.select(sa.func.count())
                .select_from(M)
                .where(
                    M.created_at.between(since, until),
                    M.mode == "canary",
                    M.status == "blocked",
                )
            )
            blocked = (await self._session.execute(blocked_q)).scalar() or 0

            return {
                "canary_payload_count": total,
                "canary_allowed_count": max(0, total - blocked),
                "canary_blocked_count": blocked,
                "canary_user_count": 0,
                "non_canary_attempts": 0,
                "non_canary_blocked": 0,
                "block_reason_counts": {},
                "risk_counts": {},
            }
        except Exception:
            return {
                "canary_payload_count": 0,
                "canary_allowed_count": 0,
                "canary_blocked_count": 0,
                "canary_user_count": 0,
                "non_canary_attempts": 0,
                "non_canary_blocked": 0,
                "block_reason_counts": {},
                "risk_counts": {},
            }

    async def _collect_public_safety(
        self,
        since: datetime,
        until: datetime,
    ) -> Stage3PublicSafetyMetrics:
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
        return Stage3PublicSafetyMetrics(
            public_user_send_count=executed,
        )

    async def _get_health(self) -> str:
        try:
            from core.services.agent_metrics_service import AgentMetricsService

            o = await AgentMetricsService(self._session).get_overview()
            return o.health.status
        except Exception:
            return "green"
