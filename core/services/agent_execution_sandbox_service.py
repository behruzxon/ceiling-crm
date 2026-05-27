"""
core.services.agent_execution_sandbox_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Validates, gates, and traces agent execution payloads before any real
action is taken.  Supports log_only, dry_run, canary, approval_required,
and live modes.  Pure functions — no I/O, no Telegram sends.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from core.schemas.agent_execution import AgentExecutionPayload, AgentExecutionResult
from shared.constants.enums import (
    AgentExecutionMode,
    AgentExecutionRisk,
    AgentExecutionStatus,
)

_PHONE_RE = re.compile(r"\+?\d{9,15}")
_TOKEN_RE = re.compile(r"(?:sk-|token[=:]|Bearer\s)\S+", re.IGNORECASE)
_FAKE_DISCOUNT_RE = re.compile(r"\d+\s*%")
_SAME_DAY_RE = re.compile(r"bugun qilamiz", re.IGNORECASE)
_ENG_ARZON_RE = re.compile(r"eng arzon", re.IGNORECASE)

_TERMINAL_STOP_REASONS: frozenset[str] = frozenset(
    {
        "lost_lead",
        "deal_closed",
        "user_opted_out",
        "user_stop_signal",
    }
)

_DEFAULT_MAX_DAILY = 3


class AgentExecutionSandboxService:
    """Validates and gates agent executions."""

    @staticmethod
    def prepare_execution(
        payload: dict[str, Any],
        memory: dict[str, Any],
        mode: str = AgentExecutionMode.LOG_ONLY.value,
    ) -> AgentExecutionPayload:
        action = payload.get("action", "no_action")
        channel = payload.get("channel", "none")
        target = payload.get("target_user_id") or memory.get("telegram_user_id")
        msg = payload.get("user_message_text")
        buttons = payload.get("user_buttons")
        admin_text = payload.get("admin_alert_text")
        risk = AgentExecutionSandboxService._assess_risk(action, channel, memory)

        return AgentExecutionPayload(
            execution_id=str(uuid.uuid4())[:12],
            mode=mode,
            status=AgentExecutionStatus.PROPOSED.value,
            action=action,
            target_user_id=target,
            channel=channel,
            message_text=msg,
            buttons=buttons,
            admin_alert_text=admin_text,
            risk_level=risk,
            approval_required=AgentExecutionSandboxService.requires_approval(
                action,
                channel,
                mode,
            ),
        )

    @staticmethod
    def validate_execution(
        execution: AgentExecutionPayload,
        memory: dict[str, Any],
        canary_user_ids: list[int] | None = None,
        max_daily: int = _DEFAULT_MAX_DAILY,
    ) -> AgentExecutionResult:
        blocked, reason = AgentExecutionSandboxService.should_block(
            execution,
            memory,
            max_daily,
        )
        if blocked:
            return AgentExecutionResult(
                would_execute=False,
                blocked=True,
                blocked_reason=reason,
                mode=execution.mode,
                risk_level=execution.risk_level,
                safe_to_execute=False,
                status=AgentExecutionStatus.BLOCKED.value,
            )

        if execution.mode == AgentExecutionMode.LOG_ONLY.value:
            return AgentExecutionResult(
                would_execute=False,
                blocked=False,
                mode=execution.mode,
                risk_level=execution.risk_level,
                safe_to_execute=True,
                status=AgentExecutionStatus.PROPOSED.value,
            )

        if execution.mode == AgentExecutionMode.DRY_RUN.value:
            return AgentExecutionResult(
                would_execute=True,
                blocked=False,
                mode=execution.mode,
                risk_level=execution.risk_level,
                safe_to_execute=True,
                status=AgentExecutionStatus.PROPOSED.value,
            )

        if execution.mode == AgentExecutionMode.CANARY.value:
            is_canary = AgentExecutionSandboxService.is_canary_user(
                execution.target_user_id,
                canary_user_ids,
            )
            if not is_canary:
                return AgentExecutionResult(
                    would_execute=False,
                    blocked=True,
                    blocked_reason="non_canary_user",
                    mode=execution.mode,
                    risk_level=execution.risk_level,
                    safe_to_execute=False,
                    status=AgentExecutionStatus.BLOCKED.value,
                )
            return AgentExecutionResult(
                would_execute=True,
                blocked=False,
                mode=execution.mode,
                risk_level=execution.risk_level,
                safe_to_execute=True,
                status=AgentExecutionStatus.APPROVED.value,
            )

        if execution.mode == AgentExecutionMode.APPROVAL_REQUIRED.value:
            return AgentExecutionResult(
                would_execute=False,
                blocked=False,
                requires_approval=True,
                mode=execution.mode,
                risk_level=execution.risk_level,
                safe_to_execute=False,
                status=AgentExecutionStatus.PROPOSED.value,
            )

        if execution.mode == AgentExecutionMode.LIVE.value:
            return AgentExecutionResult(
                would_execute=True,
                blocked=False,
                mode=execution.mode,
                risk_level=execution.risk_level,
                safe_to_execute=True,
                status=AgentExecutionStatus.APPROVED.value,
            )

        return AgentExecutionResult(
            would_execute=False,
            blocked=True,
            blocked_reason="unknown_mode",
            mode=execution.mode,
            risk_level=execution.risk_level,
            safe_to_execute=False,
            status=AgentExecutionStatus.BLOCKED.value,
        )

    @staticmethod
    def should_block(
        execution: AgentExecutionPayload,
        memory: dict[str, Any],
        max_daily: int = _DEFAULT_MAX_DAILY,
    ) -> tuple[bool, str | None]:
        if not memory.get("followup_enabled", True):
            sr = memory.get("stop_reason", "")
            if sr in _TERMINAL_STOP_REASONS:
                return True, f"terminal_stop:{sr}"
            return True, "followup_disabled"

        md = memory.get("memory_data") or {}
        state = md.get("customer_state", "")
        if state in ("stopped", "lost", "closed"):
            return True, f"terminal_state:{state}"

        action = execution.action
        channel = execution.channel
        msg = execution.message_text or ""

        if action == "send_user_reply" and not msg.strip():
            return True, "empty_message"

        if action == "send_user_reply" and not execution.target_user_id:
            return True, "missing_target_user"

        if msg and _TOKEN_RE.search(msg):
            return True, "token_in_message"

        if msg and _PHONE_RE.search(msg):
            return True, "raw_phone_in_message"

        if msg and _FAKE_DISCOUNT_RE.search(msg):
            return True, "fake_discount_in_message"

        if msg and _SAME_DAY_RE.search(msg):
            return True, "same_day_promise"

        if msg and _ENG_ARZON_RE.search(msg):
            return True, "eng_arzon_claim"

        risk = execution.risk_level
        if risk in ("high", "critical") and channel == "user_dm":
            return True, "high_risk_user_dm"

        daily_count = md.get("daily_action_count", 0)
        if daily_count >= max_daily and action == "send_user_reply":
            return True, "daily_cap_reached"

        return False, None

    @staticmethod
    def requires_approval(
        action: str,
        channel: str,
        mode: str,
    ) -> bool:
        if mode != AgentExecutionMode.APPROVAL_REQUIRED.value:
            return False
        if action == "send_user_reply" and channel == "user_dm":
            return True
        return False

    @staticmethod
    def is_canary_user(
        user_id: int | None,
        canary_ids: list[int] | None = None,
    ) -> bool:
        if not canary_ids or user_id is None:
            return False
        return user_id in canary_ids

    @staticmethod
    def execute_dry_run(
        execution: AgentExecutionPayload,
        memory: dict[str, Any],
    ) -> AgentExecutionResult:
        return AgentExecutionSandboxService.validate_execution(
            execution,
            memory,
        )

    @staticmethod
    def approve_execution(
        execution: AgentExecutionPayload,
        admin_id: int,
    ) -> AgentExecutionPayload:
        return AgentExecutionPayload(
            execution_id=execution.execution_id,
            mode=execution.mode,
            status=AgentExecutionStatus.APPROVED.value,
            action=execution.action,
            target_user_id=execution.target_user_id,
            channel=execution.channel,
            message_text=execution.message_text,
            buttons=execution.buttons,
            admin_alert_text=execution.admin_alert_text,
            risk_level=execution.risk_level,
            approval_required=False,
            approved_by=admin_id,
        )

    @staticmethod
    def reject_execution(
        execution: AgentExecutionPayload,
        admin_id: int,
        reason: str = "",
    ) -> AgentExecutionPayload:
        return AgentExecutionPayload(
            execution_id=execution.execution_id,
            mode=execution.mode,
            status=AgentExecutionStatus.REJECTED.value,
            action=execution.action,
            target_user_id=execution.target_user_id,
            channel=execution.channel,
            message_text=execution.message_text,
            risk_level=execution.risk_level,
            approval_required=False,
            blocked_reason=reason or "admin_rejected",
        )

    @staticmethod
    def rollback_execution(
        execution: AgentExecutionPayload,
    ) -> AgentExecutionPayload:
        return AgentExecutionPayload(
            execution_id=execution.execution_id,
            mode=execution.mode,
            status=AgentExecutionStatus.ROLLED_BACK.value,
            action=execution.action,
            target_user_id=execution.target_user_id,
            channel=execution.channel,
            risk_level=execution.risk_level,
            rollback_action="noop",
        )

    @staticmethod
    def store_execution_trace(
        memory_data: dict[str, Any],
        execution: AgentExecutionPayload,
        result: AgentExecutionResult,
    ) -> dict[str, Any]:
        updated = dict(memory_data)
        updated["last_execution_sandbox"] = {
            "mode": execution.mode,
            "status": result.status,
            "action": execution.action,
            "would_execute": result.would_execute,
            "blocked": result.blocked,
            "blocked_reason": result.blocked_reason,
            "risk_level": result.risk_level,
            "created_at": datetime.now(UTC).isoformat(),
        }
        return updated

    # ── Private helpers ───────────────────────────────────────────────────

    @staticmethod
    def _assess_risk(
        action: str,
        channel: str,
        memory: dict[str, Any],
    ) -> str:
        followup_count = memory.get("followup_count", 0)

        if followup_count >= 5:
            return AgentExecutionRisk.HIGH.value

        if action == "send_user_reply" and channel == "user_dm":
            temp = memory.get("lead_temperature", "cold")
            if temp == "cold":
                return AgentExecutionRisk.MEDIUM.value
            return AgentExecutionRisk.LOW.value

        if action == "send_admin_alert":
            return AgentExecutionRisk.NONE.value

        if action in ("disable_agent", "cancel_followups"):
            return AgentExecutionRisk.NONE.value

        return AgentExecutionRisk.LOW.value
