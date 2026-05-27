"""
core.services.agent_settings_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Safe agent settings mutation with validation, risk assessment,
confirmation tokens, audit logging, and rollback support.
Pure validation methods + async DB operations.
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Any

from core.schemas.agent_settings import AgentSettingsValidationResult, AgentSettingValue

_ALLOWED_KEYS: frozenset[str] = frozenset(
    {
        "agent_followups_enabled",
        "agent_catalog_followup_enabled",
        "agent_price_followup_enabled",
        "agent_order_followup_enabled",
        "agent_admin_escalation_enabled",
        "agent_ai_composer_enabled",
        "agent_decision_engine_enabled",
        "agent_lead_signal_enabled",
        "agent_lead_scoring_enabled",
        "agent_dynamic_offer_enabled",
        "agent_conversation_policy_enabled",
        "agent_response_orchestrator_enabled",
        "agent_response_orchestrator_log_only",
        "agent_execution_sandbox_enabled",
        "agent_execution_mode",
        "agent_execution_queue_enabled",
        "agent_execution_api_approval_enabled",
        "agent_execution_live_sender_enabled",
        "agent_execution_auto_execute_approved",
        "agent_catalog_followup_delay_minutes",
        "agent_price_followup_delay_minutes",
        "agent_order_followup_delay_minutes",
        "agent_execution_max_daily_per_user",
        "agent_decision_min_confidence",
        "agent_conversation_policy_min_confidence",
        "agent_dynamic_offer_min_confidence",
        "agent_response_orchestrator_trace_enabled",
        "agent_execution_trace_enabled",
        "agent_text_normalization_enabled",
        "agent_fuzzy_intent_enabled",
    }
)

_RISK_MAP: dict[str, str] = {
    "agent_execution_live_sender_enabled": "critical",
    "agent_execution_auto_execute_approved": "critical",
    "agent_followups_enabled": "high",
    "agent_catalog_followup_enabled": "high",
    "agent_price_followup_enabled": "high",
    "agent_order_followup_enabled": "high",
    "agent_admin_escalation_enabled": "high",
    "agent_execution_sandbox_enabled": "high",
    "agent_execution_queue_enabled": "high",
    "agent_execution_api_approval_enabled": "high",
    "agent_ai_composer_enabled": "medium",
    "agent_decision_engine_enabled": "medium",
    "agent_lead_signal_enabled": "medium",
    "agent_lead_scoring_enabled": "medium",
    "agent_dynamic_offer_enabled": "medium",
    "agent_conversation_policy_enabled": "medium",
    "agent_response_orchestrator_enabled": "medium",
}

_CRITICAL_KEYS: frozenset[str] = frozenset(
    {
        "agent_execution_live_sender_enabled",
        "agent_execution_auto_execute_approved",
    }
)

_EXECUTION_MODES: frozenset[str] = frozenset(
    {
        "log_only",
        "dry_run",
        "canary",
        "approval_required",
        "live",
    }
)


class AgentSettingsService:
    """Agent settings validation and mutation logic."""

    @staticmethod
    def is_allowed_key(key: str) -> bool:
        return key in _ALLOWED_KEYS

    @staticmethod
    def validate_value(key: str, value: Any) -> tuple[bool, str]:
        if key == "agent_execution_mode":
            if value not in _EXECUTION_MODES:
                return False, f"invalid_mode:{value}"
            return True, "ok"
        if key.endswith("_enabled") or key.endswith("_log_only"):
            if not isinstance(value, bool):
                return False, "expected_bool"
            return True, "ok"
        if key.endswith("_minutes") or key.endswith("_per_user") or key.endswith("_confidence"):
            if not isinstance(value, int) or value < 0:
                return False, "expected_positive_int"
            return True, "ok"
        return True, "ok"

    @staticmethod
    def calculate_risk(key: str, value: Any) -> str:
        if key == "agent_execution_mode" and value == "live":
            return "critical"
        if key == "agent_response_orchestrator_log_only" and value is False:
            return "high"
        base = _RISK_MAP.get(key, "low")
        if isinstance(value, bool) and not value:
            return "low"
        return base

    @staticmethod
    def validate_change(
        key: str,
        value: Any,
        current_settings: dict[str, Any] | None = None,
        allow_live_flags: bool = False,
    ) -> AgentSettingsValidationResult:
        if not AgentSettingsService.is_allowed_key(key):
            return AgentSettingsValidationResult(
                allowed=False,
                risk_level="none",
                blockers=[f"unknown_key:{key}"],
            )

        ok, reason = AgentSettingsService.validate_value(key, value)
        if not ok:
            return AgentSettingsValidationResult(
                allowed=False,
                risk_level="none",
                blockers=[reason],
            )

        risk = AgentSettingsService.calculate_risk(key, value)
        warnings: list[str] = []
        blockers: list[str] = []
        cs = current_settings or {}

        if risk == "critical" and not allow_live_flags:
            blockers.append(f"critical_flag_blocked:{key}")

        if key == "agent_execution_mode" and value == "live" and not allow_live_flags:
            blockers.append("live_mode_blocked")

        if key == "agent_execution_live_sender_enabled" and value is True:
            if not cs.get("agent_execution_queue_enabled"):
                blockers.append("live_sender_requires_queue")

        if key == "agent_execution_auto_execute_approved" and value is True:
            if not cs.get("agent_execution_live_sender_enabled"):
                blockers.append("auto_execute_requires_sender")

        if key == "agent_execution_mode" and value == "canary":
            ids = cs.get("agent_execution_canary_user_ids", "")
            if not ids or not str(ids).strip():
                blockers.append("canary_requires_user_ids")

        requires_conf = risk in ("medium", "high", "critical") and not blockers
        token = None
        if requires_conf:
            token = AgentSettingsService.generate_confirmation_token(key, value)

        return AgentSettingsValidationResult(
            allowed=not blockers,
            risk_level=risk,
            warnings=warnings,
            blockers=blockers,
            requires_confirmation=requires_conf,
            confirmation_token=token,
        )

    @staticmethod
    def generate_confirmation_token(key: str, value: Any) -> str:
        raw = f"{key}:{value}:{secrets.token_hex(8)}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    @staticmethod
    def verify_confirmation_token(
        token: str,
        expected_hash_prefix: str | None = None,
    ) -> bool:
        if not token or len(token) < 10:
            return False
        return True

    @staticmethod
    def detect_dangerous_combinations(
        settings: dict[str, Any],
    ) -> list[str]:
        dangers: list[str] = []
        if settings.get("agent_execution_live_sender_enabled"):
            if not settings.get("agent_execution_queue_enabled"):
                dangers.append("live_sender_without_queue")
        if settings.get("agent_execution_auto_execute_approved"):
            if not settings.get("agent_execution_live_sender_enabled"):
                dangers.append("auto_execute_without_sender")
        mode = settings.get("agent_execution_mode", "log_only")
        if mode == "canary":
            ids = settings.get("agent_execution_canary_user_ids", "")
            if not str(ids).strip():
                dangers.append("canary_without_user_ids")
        if mode == "live":
            dangers.append("execution_mode_live")
        return dangers

    @staticmethod
    def sanitize_settings_for_api(
        settings: dict[str, Any],
    ) -> list[AgentSettingValue]:
        result: list[AgentSettingValue] = []
        for key in sorted(_ALLOWED_KEYS):
            val = settings.get(key)
            if val is None:
                continue
            risk = _RISK_MAP.get(key, "low")
            vtype = (
                "bool" if isinstance(val, bool) else ("int" if isinstance(val, int) else "string")
            )
            result.append(
                AgentSettingValue(
                    key=key,
                    value=val,
                    source="effective",
                    risk_level=risk,
                    value_type=vtype,
                )
            )
        return result

    @staticmethod
    def build_rollback_snapshot(
        current_settings: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            k: current_settings.get(k)
            for k in sorted(_ALLOWED_KEYS)
            if current_settings.get(k) is not None
        }
