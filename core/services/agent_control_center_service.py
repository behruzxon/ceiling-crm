"""
core.services.agent_control_center_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Read-only control center for the agent system.
Detects rollout stage, runs preflight checks, and builds status snapshots.
No mutations, no sends. Pure functions where possible.
"""

from __future__ import annotations

from typing import Any

from core.schemas.agent_control_center import (
    AgentCanaryStatus,
    AgentControlCenterSnapshot,
    AgentControlSummary,
    AgentFeatureFlagStatus,
    AgentLastDecisionView,
    AgentPreflightStatus,
    AgentRolloutStageStatus,
    AgentSafetySummary,
)

_LAST_DECISION_SAFE_KEYS: tuple[str, ...] = (
    "decision_id",
    "timestamp",
    "intent",
    "safety_flags",
    "execution_mode",
)

_FLAG_DEFS: list[tuple[str, str, str]] = [
    ("agent_followups_enabled", "3", "medium"),
    ("agent_catalog_followup_enabled", "3", "medium"),
    ("agent_price_followup_enabled", "3", "medium"),
    ("agent_order_followup_enabled", "3", "medium"),
    ("agent_admin_escalation_enabled", "3", "low"),
    ("agent_ai_composer_enabled", "4", "medium"),
    ("agent_decision_engine_enabled", "1", "none"),
    ("agent_lead_signal_enabled", "1", "none"),
    ("agent_lead_scoring_enabled", "1", "none"),
    ("agent_dynamic_offer_enabled", "1", "none"),
    ("agent_conversation_policy_enabled", "1", "none"),
    ("agent_response_orchestrator_enabled", "1", "none"),
    ("agent_execution_sandbox_enabled", "2", "none"),
    ("agent_execution_queue_enabled", "4", "low"),
    ("agent_execution_live_sender_enabled", "5", "high"),
    ("agent_execution_api_approval_enabled", "4", "low"),
    ("agent_execution_auto_execute_approved", "5", "high"),
]


class AgentControlCenterService:
    """Read-only agent control center."""

    @staticmethod
    def build_control_center_snapshot(
        settings: Any | None = None,
    ) -> AgentControlCenterSnapshot:
        if settings is None:
            try:
                from shared.config import get_settings

                settings = get_settings()
            except Exception:
                return AgentControlCenterSnapshot()

        biz = settings.business
        flags = AgentControlCenterService.get_feature_flags_status(biz)
        stage = AgentControlCenterService.detect_rollout_stage(biz)
        preflight = AgentControlCenterService.get_preflight_status(biz, settings)
        canary = AgentControlCenterService.get_canary_status(biz)
        safety = AgentControlCenterService.get_safety_summary(biz, settings)

        return AgentControlCenterSnapshot(
            rollout_stage=stage,
            preflight=preflight,
            canary=canary,
            safety=safety,
            flags=flags,
            health_status=preflight.status,
        )

    @staticmethod
    def get_feature_flags_status(biz: Any) -> list[AgentFeatureFlagStatus]:
        flags: list[AgentFeatureFlagStatus] = []
        for attr, stage, risk in _FLAG_DEFS:
            val = getattr(biz, attr, False)
            flags.append(
                AgentFeatureFlagStatus(
                    name=attr,
                    enabled=bool(val),
                    stage=stage,
                    risk=risk,
                )
            )
        return flags

    @staticmethod
    def detect_rollout_stage(biz: Any) -> AgentRolloutStageStatus:
        orch = getattr(biz, "agent_response_orchestrator_enabled", False)
        orch_log = getattr(biz, "agent_response_orchestrator_log_only", True)
        sandbox = getattr(biz, "agent_execution_sandbox_enabled", False)
        mode = getattr(biz, "agent_execution_mode", "log_only")
        queue = getattr(biz, "agent_execution_queue_enabled", False)
        live_sender = getattr(biz, "agent_execution_live_sender_enabled", False)
        auto_exec = getattr(biz, "agent_execution_auto_execute_approved", False)

        if live_sender and auto_exec:
            return AgentRolloutStageStatus(
                stage="approved_live_send",
                label="APPROVED LIVE SEND",
                description="Admin approved payloads are sent automatically",
            )
        if queue and mode == "approval_required":
            return AgentRolloutStageStatus(
                stage="approval_required",
                label="APPROVAL REQUIRED",
                description="Executions require admin approval",
            )
        if sandbox and mode == "canary":
            return AgentRolloutStageStatus(
                stage="canary",
                label="CANARY",
                description="Only canary users affected",
            )
        if sandbox and mode == "dry_run":
            return AgentRolloutStageStatus(
                stage="dry_run",
                label="DRY RUN",
                description="Full validation, no real sends",
            )
        if orch and orch_log:
            return AgentRolloutStageStatus(
                stage="log_only",
                label="LOG ONLY",
                description="Traces written, no user impact",
            )
        if orch and not orch_log:
            return AgentRolloutStageStatus(
                stage="custom",
                label="CUSTOM",
                description="Orchestrator active, non-standard config",
            )
        if not orch and not sandbox:
            return AgentRolloutStageStatus(
                stage="off",
                label="OFF",
                description="All agent features disabled",
            )
        return AgentRolloutStageStatus(
            stage="mixed",
            label="MIXED",
            description="Non-standard flag combination",
        )

    @staticmethod
    def get_preflight_status(
        biz: Any,
        settings: Any,
    ) -> AgentPreflightStatus:
        warnings: list[str] = []
        blockers: list[str] = []

        mode = getattr(biz, "agent_execution_mode", "log_only")
        canary_ids = getattr(biz, "agent_execution_canary_user_ids", "")
        queue = getattr(biz, "agent_execution_queue_enabled", False)
        live_sender = getattr(biz, "agent_execution_live_sender_enabled", False)
        auto_exec = getattr(biz, "agent_execution_auto_execute_approved", False)
        ai_composer = getattr(biz, "agent_ai_composer_enabled", False)
        admin_notify = getattr(biz, "agent_execution_approval_admin_notify", False)

        admin_group = ""
        openai_key = False
        try:
            admin_group = str(getattr(settings.bot, "admin_group_id", "") or "")
            key = getattr(settings.openai, "api_key", None)
            openai_key = bool(key and str(key) not in ("", "None"))
        except Exception:
            pass

        if mode == "canary" and not canary_ids.strip():
            blockers.append("Canary mode but no CANARY_USER_IDS")
        if live_sender and not queue:
            blockers.append("Live sender without queue enabled")
        if auto_exec and not live_sender:
            blockers.append("Auto execute without live sender")
        if ai_composer and not openai_key:
            warnings.append("AI composer without OpenAI key")
        if admin_notify and not admin_group:
            warnings.append("Admin notify without admin group ID")

        status = "green"
        if blockers:
            status = "red"
        elif warnings:
            status = "yellow"

        return AgentPreflightStatus(
            status=status,
            warnings=warnings,
            blockers=blockers,
        )

    _STAGE_ORDER = [
        "off",
        "log_only",
        "dry_run",
        "canary",
        "approval_required",
        "approved_live_send",
    ]

    @staticmethod
    def recommend_next_stage(current_stage: str) -> str | None:
        order = AgentControlCenterService._STAGE_ORDER
        if current_stage not in order:
            return "off"
        idx = order.index(current_stage)
        if idx + 1 < len(order):
            return order[idx + 1]
        return None

    @staticmethod
    def get_canary_status(biz: Any) -> AgentCanaryStatus:
        mode = getattr(biz, "agent_execution_mode", "log_only")
        canary_ids = getattr(biz, "agent_execution_canary_user_ids", "")
        count = len([x for x in canary_ids.split(",") if x.strip()]) if canary_ids else 0

        return AgentCanaryStatus(
            mode=mode,
            canary_user_count=count,
            approval_required=(mode == "approval_required"),
            auto_execute=getattr(biz, "agent_execution_auto_execute_approved", False),
            batch_limit=getattr(biz, "agent_execution_live_sender_batch_limit", 10),
            daily_cap=getattr(biz, "agent_execution_max_daily_per_user", 3),
        )

    @staticmethod
    def get_safety_summary(biz: Any, settings: Any) -> AgentSafetySummary:
        preflight = AgentControlCenterService.get_preflight_status(biz, settings)
        return AgentSafetySummary(
            status=preflight.status,
            dangerous_combos=preflight.blockers,
            missing_configs=preflight.warnings,
        )


def _safe_last_decision_view(
    last_decision: dict[str, Any] | None,
) -> AgentLastDecisionView | None:
    if not last_decision:
        return None
    raw_flags = last_decision.get("safety_flags", ()) or ()
    if isinstance(raw_flags, (list, tuple)):
        safety_flags = tuple(str(f) for f in raw_flags)
    else:
        safety_flags = (str(raw_flags),)
    return AgentLastDecisionView(
        decision_id=str(last_decision.get("decision_id", "") or ""),
        timestamp=str(last_decision.get("timestamp", "") or ""),
        intent=str(last_decision.get("intent", "") or ""),
        safety_flags=safety_flags,
        execution_mode=str(last_decision.get("execution_mode", "") or ""),
    )


def build_agent_control_summary(
    settings: Any,
    last_decision: dict[str, Any] | None = None,
) -> AgentControlSummary:
    """Build a read-only summary for the Agent Control Center pill + card.

    Pure function: takes the settings object (with ``.business`` attribute)
    and an optional last_decision dict. Returns a frozen
    ``AgentControlSummary``. Never reads prompts, tokens, or session
    hashes from the input; only whitelisted decision keys are copied
    into the view.
    """
    biz = getattr(settings, "business", None)
    if biz is None:
        biz = settings

    orch_on = bool(getattr(biz, "agent_response_orchestrator_enabled", False))
    engine_on = bool(getattr(biz, "agent_decision_engine_enabled", False))
    overall_on = orch_on or engine_on

    log_only = bool(
        getattr(biz, "agent_response_orchestrator_log_only", True)
        and getattr(biz, "agent_decision_log_only", True)
    )

    live_sender = bool(getattr(biz, "agent_execution_live_sender_enabled", False))
    auto_exec = bool(getattr(biz, "agent_execution_auto_execute_approved", False))
    live_send_safe = not (live_sender or auto_exec)

    if not overall_on:
        label = "ENGINE OFF"
        color = "gray"
    elif log_only:
        label = "ENGINE ON · LOG_ONLY"
        color = "blue"
    elif live_send_safe:
        label = "ENGINE ON · SAFE"
        color = "green"
    else:
        label = "ENGINE ON · LIVE"
        color = "red"

    safe_text = "Safe / No live send" if live_send_safe else "LIVE SEND ACTIVE"

    return AgentControlSummary(
        engine_on=overall_on,
        log_only=log_only,
        live_send_safe=live_send_safe,
        status_pill_label=label,
        status_pill_color=color,
        safe_text=safe_text,
        last_decision=_safe_last_decision_view(last_decision),
    )
