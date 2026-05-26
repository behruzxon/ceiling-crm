"""
core.services.stage4_approval_readiness_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Evaluates readiness from CANARY to APPROVAL_REQUIRED.
APPROVAL is human-in-the-loop before public sends. Pure functions.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.schemas.stage3_canary_report import Stage3CanaryReport
from core.schemas.stage4_approval_readiness import Stage4ApprovalReadinessResult


class Stage4ApprovalReadinessService:
    """Pure APPROVAL_REQUIRED readiness gate."""

    @staticmethod
    def evaluate_canary_to_approval(
        report: Stage3CanaryReport,
        current_settings: dict[str, Any] | None = None,
    ) -> Stage4ApprovalReadinessResult:
        cs = current_settings or {}
        blockers = Stage4ApprovalReadinessService.build_blockers(report, cs)
        warnings = Stage4ApprovalReadinessService.build_warnings(report, cs)
        score = Stage4ApprovalReadinessService.calculate_readiness_score(
            blockers, warnings,
        )
        recs = Stage4ApprovalReadinessService.build_recommendations(
            report, blockers, warnings, score, cs,
        )

        if blockers:
            verdict, allowed = "not_ready", False
        elif score >= 90:
            verdict, allowed = "ready", True
        elif score >= 70:
            verdict, allowed = "conditional", True
        else:
            verdict, allowed = "not_ready", False

        return Stage4ApprovalReadinessResult(
            from_stage="canary", to_stage="approval_required",
            allowed=allowed, readiness_score=score, verdict=verdict,
            blockers=blockers, warnings=warnings, recommendations=recs,
            generated_at=datetime.now(UTC).isoformat(),
        )

    @staticmethod
    def build_blockers(
        report: Stage3CanaryReport, settings: dict[str, Any],
    ) -> list[str]:
        blockers: list[str] = []

        if not report.pass_fail.passed:
            blockers.append("canary_report_failed")

        ps = report.public_safety
        if ps.public_user_send_count > 0:
            blockers.append("public_send_violation")
        if ps.non_canary_allowed_count > 0:
            blockers.append("non_canary_allowed_violation")
        if ps.high_risk_sent_count > 0:
            blockers.append("high_risk_sent")
        if ps.critical_risk_sent_count > 0:
            blockers.append("critical_risk_sent")
        if ps.duplicate_sent_count > 0:
            blockers.append("duplicate_sent")
        if ps.sensitive_leak_count > 0:
            blockers.append("sensitive_leak")

        if report.health_status == "red":
            blockers.append("health_red")

        if settings.get("agent_execution_live_sender_enabled"):
            blockers.append("live_sender_enabled")
        if settings.get("agent_execution_auto_execute_approved"):
            blockers.append("auto_execute_enabled")
        if settings.get("agent_execution_mode") == "live":
            blockers.append("execution_mode_live")
        if not settings.get("agent_execution_queue_enabled", True):
            if "agent_execution_queue_enabled" in settings and not settings["agent_execution_queue_enabled"]:
                blockers.append("queue_disabled")
        if not settings.get("agent_execution_api_approval_enabled", True):
            if "agent_execution_api_approval_enabled" in settings and not settings["agent_execution_api_approval_enabled"]:
                blockers.append("api_approval_disabled")

        from core.services.agent_rollout_preset_service import (
            AgentRolloutPresetService,
        )
        preview = AgentRolloutPresetService.preview_preset(
            "approval_required", settings,
        )
        if not preview.allowed:
            blockers.append("approval_preset_blocked")

        return blockers

    @staticmethod
    def build_warnings(
        report: Stage3CanaryReport, settings: dict[str, Any],
    ) -> list[str]:
        warnings: list[str] = []

        if 0 < report.canary_payload_count < 10:
            warnings.append("low_canary_sends")
        if report.canary_payload_count == 0:
            warnings.append("no_canary_sends")

        total = report.canary_payload_count or 1
        if report.canary_blocked_count / total > 0.7 and report.canary_payload_count > 10:
            warnings.append("high_blocked_ratio")

        if report.health_status == "yellow":
            warnings.append("health_yellow")
        if report.duration_minutes < 30:
            warnings.append("short_observation")

        return warnings

    @staticmethod
    def calculate_readiness_score(
        blockers: list[str], warnings: list[str],
    ) -> int:
        if blockers:
            return min(40, 100 - len(blockers) * 12)
        score = 100
        penalty = {
            "low_canary_sends": 10, "no_canary_sends": 20,
            "high_blocked_ratio": 15, "health_yellow": 10,
            "short_observation": 10,
        }
        for w in warnings:
            score -= penalty.get(w, 5)
        return max(0, min(score, 100))

    @staticmethod
    def build_recommendations(
        report: Stage3CanaryReport, blockers: list[str],
        warnings: list[str], score: int, settings: dict[str, Any],
    ) -> list[str]:
        recs: list[str] = []
        if blockers:
            if any("violation" in b or "leak" in b for b in blockers):
                recs.append("Safety violation — rollback OFF immediately")
            if "queue_disabled" in blockers:
                recs.append("Enable execution queue for approval mode")
            if "api_approval_disabled" in blockers:
                recs.append("Enable API approval endpoint")
            if "canary_report_failed" in blockers:
                recs.append("CANARY FAIL — fix issues first")
            return recs or ["Fix blockers before proceeding"]

        if "no_canary_sends" in warnings:
            recs.append("No canary sends — continue CANARY testing")
        if score >= 90:
            recs.append("READY — preview APPROVAL_REQUIRED preset")
        elif score >= 70:
            recs.append("CONDITIONAL — address warnings first")
        if not recs:
            recs.append("Continue CANARY observation")
        return recs
