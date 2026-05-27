"""
core.services.stage5_live_send_readiness_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Strictest gate: evaluates readiness for APPROVED_LIVE_SEND.
Approved payloads will be sent to real users. Pure functions.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.schemas.stage4_approval_report import Stage4ApprovalReport
from core.schemas.stage5_live_send_readiness import Stage5LiveSendReadinessResult


class Stage5LiveSendReadinessService:
    """Strictest readiness gate — first real public send."""

    @staticmethod
    def evaluate_approval_to_live_send(
        report: Stage4ApprovalReport,
        current_settings: dict[str, Any] | None = None,
    ) -> Stage5LiveSendReadinessResult:
        cs = current_settings or {}
        blockers = Stage5LiveSendReadinessService.build_blockers(report, cs)
        warnings = Stage5LiveSendReadinessService.build_warnings(report, cs)
        score = Stage5LiveSendReadinessService.calculate_readiness_score(blockers, warnings)
        recs = Stage5LiveSendReadinessService.build_recommendations(report, blockers, warnings, score, cs)

        if blockers:
            verdict, allowed = "not_ready", False
        elif score >= 95:
            verdict, allowed = "ready", True
        elif score >= 80:
            verdict, allowed = "conditional", True
        else:
            verdict, allowed = "not_ready", False

        return Stage5LiveSendReadinessResult(
            from_stage="approval_required", to_stage="approved_live_send",
            allowed=allowed, readiness_score=score, verdict=verdict,
            blockers=blockers, warnings=warnings, recommendations=recs,
            generated_at=datetime.now(UTC).isoformat(),
        )

    @staticmethod
    def build_blockers(report: Stage4ApprovalReport, settings: dict[str, Any]) -> list[str]:
        blockers: list[str] = []

        if not report.pass_fail.passed:
            blockers.append("approval_report_failed")

        ns = report.no_send
        if ns.executed_records_count > 0:
            blockers.append("execution_during_approval")
        if ns.live_sender_executed > 0:
            blockers.append("live_sender_during_approval")
        if ns.auto_execute_count > 0:
            blockers.append("auto_execute_during_approval")
        if ns.user_dm_sent_count > 0:
            blockers.append("user_dm_during_approval")

        if report.health_status == "red":
            blockers.append("health_red")

        if report.total_proposals == 0:
            blockers.append("no_proposals")
        elif report.approved_count == 0:
            blockers.append("no_approved_samples")

        if report.stale_pending_count > 20:
            blockers.append("stale_pending_excessive")

        if not settings.get("agent_settings_allow_live_flags"):
            blockers.append("allow_live_flags_false")

        mode = settings.get("agent_execution_mode", "log_only")
        if mode == "live":
            blockers.append("execution_mode_already_live")

        from core.services.agent_rollout_preset_service import AgentRolloutPresetService
        allow_live = bool(settings.get("agent_settings_allow_live_flags"))
        preview = AgentRolloutPresetService.preview_preset(
            "approved_live_send", settings, allow_live,
        )
        if not preview.allowed:
            blockers.append("live_send_preset_blocked")

        return blockers

    @staticmethod
    def build_warnings(report: Stage4ApprovalReport, settings: dict[str, Any]) -> list[str]:
        warnings: list[str] = []
        if 0 < report.total_proposals < 20:
            warnings.append("low_proposal_count")
        if 0 < report.approved_count < 5:
            warnings.append("low_approved_count")

        total = report.total_proposals or 1
        if report.rejected_count / total > 0.7 and report.total_proposals > 10:
            warnings.append("high_rejection_rate")
        if report.expired_count / total > 0.5 and report.total_proposals > 10:
            warnings.append("high_expiration_rate")

        if report.pending_count > 20:
            warnings.append("pending_count_high")
        if report.health_status == "yellow":
            warnings.append("health_yellow")
        if report.duration_minutes < 30:
            warnings.append("short_observation")

        return warnings

    @staticmethod
    def calculate_readiness_score(blockers: list[str], warnings: list[str]) -> int:
        if blockers:
            return min(40, 100 - len(blockers) * 10)
        score = 100
        penalty = {
            "low_proposal_count": 10, "low_approved_count": 15,
            "high_rejection_rate": 10, "high_expiration_rate": 10,
            "pending_count_high": 10, "health_yellow": 10,
            "short_observation": 10,
        }
        for w in warnings:
            score -= penalty.get(w, 5)
        return max(0, min(score, 100))

    @staticmethod
    def build_recommendations(
        report: Stage4ApprovalReport, blockers: list[str],
        warnings: list[str], score: int, settings: dict[str, Any],
    ) -> list[str]:
        if blockers:
            recs: list[str] = []
            if any("during_approval" in b for b in blockers):
                recs.append("Send violation during approval — rollback OFF immediately")
            if "allow_live_flags_false" in blockers:
                recs.append("Set AGENT_SETTINGS_ALLOW_LIVE_FLAGS=true to unlock live presets")
            if "no_proposals" in blockers:
                recs.append("No proposals — continue approval stage")
            if "no_approved_samples" in blockers:
                recs.append("No approved samples — admin must approve at least one proposal")
            if "approval_report_failed" in blockers:
                recs.append("Approval report FAIL — fix issues first")
            return recs or ["Fix blockers before live send"]

        if score >= 95:
            return ["READY — preview APPROVED_LIVE_SEND preset (requires allow_live_flags)"]
        if score >= 80:
            return ["CONDITIONAL — address warnings before live send"]
        return ["Continue approval observation"]
