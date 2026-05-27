"""
core.services.stage3_canary_readiness_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Evaluates readiness to transition from DRY_RUN to CANARY.
CANARY is the first real-send stage — stricter criteria.
Pure functions — no I/O.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.schemas.stage2_dryrun_report import Stage2DryRunReport
from core.schemas.stage3_canary_readiness import Stage3CanaryReadinessResult


class Stage3CanaryReadinessService:
    """Pure CANARY readiness gate evaluation."""

    @staticmethod
    def evaluate_dryrun_to_canary(
        report: Stage2DryRunReport,
        current_settings: dict[str, Any] | None = None,
    ) -> Stage3CanaryReadinessResult:
        cs = current_settings or {}
        blockers = Stage3CanaryReadinessService.build_blockers(report, cs)
        warnings = Stage3CanaryReadinessService.build_warnings(report, cs)
        score = Stage3CanaryReadinessService.calculate_readiness_score(
            blockers,
            warnings,
        )
        recs = Stage3CanaryReadinessService.build_recommendations(
            report,
            blockers,
            warnings,
            score,
            cs,
        )

        if blockers:
            verdict = "not_ready"
            allowed = False
        elif score >= 90:
            verdict = "ready"
            allowed = True
        elif score >= 70:
            verdict = "conditional"
            allowed = True
        else:
            verdict = "not_ready"
            allowed = False

        return Stage3CanaryReadinessResult(
            from_stage="dry_run",
            to_stage="canary",
            allowed=allowed,
            readiness_score=score,
            verdict=verdict,
            blockers=blockers,
            warnings=warnings,
            recommendations=recs,
            generated_at=datetime.now(UTC).isoformat(),
        )

    @staticmethod
    def build_blockers(
        report: Stage2DryRunReport,
        settings: dict[str, Any],
    ) -> list[str]:
        blockers: list[str] = []

        if not report.pass_fail.passed:
            blockers.append("dryrun_report_failed")

        ns = report.no_send
        if ns.actual_sent_count > 0:
            blockers.append("actual_send_violation")
        if ns.executed_records_count > 0:
            blockers.append("execution_violation")
        if ns.live_sender_executed > 0:
            blockers.append("live_sender_violation")

        if report.health_status == "red":
            blockers.append("health_red")

        canary_ids = str(settings.get("agent_execution_canary_user_ids", "")).strip()
        if not canary_ids:
            blockers.append("missing_canary_user_ids")

        if settings.get("agent_execution_live_sender_enabled"):
            blockers.append("live_sender_already_enabled")
        if settings.get("agent_execution_auto_execute_approved"):
            blockers.append("auto_execute_already_enabled")
        mode = settings.get("agent_execution_mode", "log_only")
        if mode == "live":
            blockers.append("execution_mode_live")

        high = report.risk_counts.get("high", 0)
        critical = report.risk_counts.get("critical", 0)
        if critical > 0:
            blockers.append("critical_risk_payloads_exist")

        from core.services.agent_rollout_preset_service import (
            AgentRolloutPresetService,
        )

        preview = AgentRolloutPresetService.preview_preset("canary", settings)
        if not preview.allowed:
            blockers.append("canary_preset_blocked")

        return blockers

    @staticmethod
    def build_warnings(
        report: Stage2DryRunReport,
        settings: dict[str, Any],
    ) -> list[str]:
        warnings: list[str] = []

        if report.total_payloads < 20 and report.total_payloads > 0:
            warnings.append("low_payload_count")
        if report.total_payloads == 0:
            warnings.append("no_payloads")

        total = report.total_payloads or 1
        we_ratio = report.total_would_execute / total
        if we_ratio < 0.2 and report.total_payloads > 10:
            warnings.append("low_would_execute_ratio")

        blocked_ratio = report.total_blocked / total
        if blocked_ratio > 0.7 and report.total_payloads > 10:
            warnings.append("high_blocked_ratio")

        high = report.risk_counts.get("high", 0)
        if high / total > 0.2 and report.total_payloads > 10:
            warnings.append("high_risk_ratio")

        if report.health_status == "yellow":
            warnings.append("health_yellow")

        if report.duration_minutes < 30:
            warnings.append("short_observation")

        actions = report.action_counts
        if not actions.get("handoff_operator"):
            warnings.append("no_operator_scenarios")
        if not report.block_reason_counts:
            pass

        return warnings

    @staticmethod
    def calculate_readiness_score(
        blockers: list[str],
        warnings: list[str],
    ) -> int:
        if blockers:
            return min(40, 100 - len(blockers) * 15)

        score = 100
        penalty: dict[str, int] = {
            "low_payload_count": 10,
            "no_payloads": 20,
            "low_would_execute_ratio": 10,
            "high_blocked_ratio": 15,
            "high_risk_ratio": 20,
            "health_yellow": 10,
            "short_observation": 10,
            "no_operator_scenarios": 5,
        }
        for w in warnings:
            score -= penalty.get(w, 5)
        return max(0, min(score, 100))

    @staticmethod
    def build_recommendations(
        report: Stage2DryRunReport,
        blockers: list[str],
        warnings: list[str],
        score: int,
        settings: dict[str, Any],
    ) -> list[str]:
        recs: list[str] = []

        if blockers:
            if "dryrun_report_failed" in blockers:
                recs.append("DRY_RUN FAIL — fix violations first")
            if "missing_canary_user_ids" in blockers:
                recs.append("Configure CANARY_USER_IDS with test admin IDs")
            if any("violation" in b for b in blockers):
                recs.append("No-send violation — rollback OFF immediately")
            if "critical_risk_payloads_exist" in blockers:
                recs.append("Critical risk payloads detected — review policy")
            return recs

        if "high_blocked_ratio" in warnings:
            recs.append("High blocked ratio — review offer/policy rules")
        if "no_payloads" in warnings:
            recs.append("No payloads — extend DRY_RUN observation")

        if score >= 90:
            recs.append("READY — configure canary IDs and preview CANARY preset")
        elif score >= 70:
            recs.append("CONDITIONAL — address warnings before CANARY")

        if not recs:
            recs.append("Continue DRY_RUN observation")
        return recs
