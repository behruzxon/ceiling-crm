"""
core.services.stage_transition_gate_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Evaluates readiness to transition between rollout stages.
Pure functions — no I/O, no mutations.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.schemas.stage1_observation_report import Stage1ObservationReport
from core.schemas.stage_transition_gate import StageTransitionGateResult


class StageTransitionGateService:
    """Pure readiness gate evaluation."""

    @staticmethod
    def evaluate_stage1_to_dry_run(
        report: Stage1ObservationReport,
        current_settings: dict[str, Any] | None = None,
    ) -> StageTransitionGateResult:
        cs = current_settings or {}
        blockers = StageTransitionGateService.build_blockers(report, cs)
        warnings = StageTransitionGateService.build_warnings(report)
        score = StageTransitionGateService.calculate_readiness_score(
            report, blockers, warnings,
        )
        recs = StageTransitionGateService.build_recommendations(
            report, blockers, warnings, score,
        )

        if blockers:
            verdict = "not_ready"
            allowed = False
        elif score >= 85:
            verdict = "ready"
            allowed = True
        elif score >= 65:
            verdict = "conditional"
            allowed = True
        else:
            verdict = "not_ready"
            allowed = False

        return StageTransitionGateResult(
            from_stage="log_only",
            to_stage="dry_run",
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
        report: Stage1ObservationReport,
        settings: dict[str, Any],
    ) -> list[str]:
        blockers: list[str] = []

        if not report.pass_fail.passed:
            blockers.append("stage1_report_failed")

        ns = report.no_send
        if ns.followups_sent > 0:
            blockers.append("followups_sent_violation")
        if ns.admin_escalations_sent > 0:
            blockers.append("admin_escalation_violation")
        if ns.execution_records_executed > 0:
            blockers.append("execution_violation")
        if ns.live_sender_executed > 0:
            blockers.append("live_sender_violation")

        if report.health_status == "red":
            blockers.append("health_red")

        from core.services.agent_rollout_preset_service import (
            AgentRolloutPresetService,
        )
        preview = AgentRolloutPresetService.preview_preset("dry_run", settings)
        if not preview.allowed:
            blockers.append("dry_run_preset_blocked")

        return blockers

    @staticmethod
    def build_warnings(report: Stage1ObservationReport) -> list[str]:
        warnings: list[str] = []

        if report.total_orchestrator_traces < 20 and report.total_journey_events > 0:
            warnings.append("low_traces")
        if report.total_journey_events == 0:
            warnings.append("no_traffic")
        if report.health_status == "yellow":
            warnings.append("health_yellow")
        if report.duration_minutes < 30:
            warnings.append("short_observation")

        total_intents = sum(report.intent_counts.values()) or 1
        unclear = report.intent_counts.get("unclear", 0)
        if total_intents > 5 and unclear / total_intents > 0.4:
            warnings.append("high_unclear_ratio")

        total_obj = sum(report.objection_counts.values()) or 1
        price_obj = report.objection_counts.get("price", 0)
        if total_obj > 5 and price_obj / total_obj > 0.5:
            warnings.append("high_price_objection")

        stop = report.intent_counts.get("stop_request", 0)
        if total_intents > 10 and stop / total_intents > 0.3:
            warnings.append("high_stop_rate")

        return warnings

    @staticmethod
    def calculate_readiness_score(
        report: Stage1ObservationReport,
        blockers: list[str],
        warnings: list[str],
    ) -> int:
        if blockers:
            return min(40, 100 - len(blockers) * 20)

        score = 100
        penalty_map: dict[str, int] = {
            "low_traces": 15,
            "no_traffic": 20,
            "health_yellow": 10,
            "short_observation": 10,
            "high_unclear_ratio": 15,
            "high_price_objection": 5,
            "high_stop_rate": 5,
        }
        for w in warnings:
            score -= penalty_map.get(w, 5)

        return max(0, min(score, 100))

    @staticmethod
    def build_recommendations(
        report: Stage1ObservationReport,
        blockers: list[str],
        warnings: list[str],
        score: int,
    ) -> list[str]:
        recs: list[str] = []

        if blockers:
            if "stage1_report_failed" in blockers:
                recs.append("Stage 1 FAIL — fix violations before proceeding")
            if any("violation" in b for b in blockers):
                recs.append("No-send violation — rollback OFF and investigate")
            if "health_red" in blockers:
                recs.append("Health RED — resolve before stage transition")
            if "dry_run_preset_blocked" in blockers:
                recs.append("DRY_RUN preset has blockers — check settings")
            return recs

        if "no_traffic" in warnings:
            recs.append("No traffic — wait for real user activity")
        if "low_traces" in warnings:
            recs.append("Low traces — continue LOG_ONLY observation")
        if "high_unclear_ratio" in warnings:
            recs.append("High unclear — improve keyword/fuzzy rules")
        if "short_observation" in warnings:
            recs.append("Short observation — extend to 24h+")

        if score >= 85:
            recs.append("READY — safe to preview DRY_RUN preset")
        elif score >= 65:
            recs.append("CONDITIONAL — address warnings before DRY_RUN")

        if not recs:
            recs.append("Continue monitoring")

        return recs
