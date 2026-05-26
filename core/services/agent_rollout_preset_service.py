"""
core.services.agent_rollout_preset_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Staged rollout preset definitions and safe preview/apply logic.
Pure functions — no I/O.
"""
from __future__ import annotations

import hashlib
import secrets
from typing import Any

from core.schemas.agent_rollout_preset import (
    AgentRolloutPresetDefinition,
    AgentRolloutPresetDiff,
    AgentRolloutPresetPreviewResponse,
)

_PRESETS: dict[str, AgentRolloutPresetDefinition] = {
    "off": AgentRolloutPresetDefinition(
        name="off", label="OFF", description="Barcha agent flaglar o'chiq",
        risk_level="low",
        settings={
            "agent_followups_enabled": False,
            "agent_catalog_followup_enabled": False,
            "agent_price_followup_enabled": False,
            "agent_order_followup_enabled": False,
            "agent_admin_escalation_enabled": False,
            "agent_ai_composer_enabled": False,
            "agent_decision_engine_enabled": False,
            "agent_lead_signal_enabled": False,
            "agent_lead_scoring_enabled": False,
            "agent_dynamic_offer_enabled": False,
            "agent_conversation_policy_enabled": False,
            "agent_response_orchestrator_enabled": False,
            "agent_response_orchestrator_log_only": True,
            "agent_execution_sandbox_enabled": False,
            "agent_execution_queue_enabled": False,
            "agent_execution_api_approval_enabled": False,
            "agent_execution_live_sender_enabled": False,
            "agent_execution_auto_execute_approved": False,
            "agent_execution_mode": "log_only",
        },
    ),
    "log_only": AgentRolloutPresetDefinition(
        name="log_only", label="LOG ONLY",
        description="Agent kuzatadi, trace yozadi, user behavior o'zgarmaydi",
        risk_level="medium",
        settings={
            "agent_lead_signal_enabled": True,
            "agent_lead_scoring_enabled": True,
            "agent_decision_engine_enabled": True,
            "agent_dynamic_offer_enabled": True,
            "agent_conversation_policy_enabled": True,
            "agent_response_orchestrator_enabled": True,
            "agent_response_orchestrator_log_only": True,
            "agent_execution_sandbox_enabled": False,
            "agent_execution_queue_enabled": False,
            "agent_execution_live_sender_enabled": False,
            "agent_execution_auto_execute_approved": False,
            "agent_followups_enabled": False,
            "agent_execution_mode": "log_only",
        },
    ),
    "dry_run": AgentRolloutPresetDefinition(
        name="dry_run", label="DRY RUN",
        description="Payloadlar validate qilinadi, real send yo'q",
        risk_level="medium",
        settings={
            "agent_lead_signal_enabled": True,
            "agent_lead_scoring_enabled": True,
            "agent_decision_engine_enabled": True,
            "agent_dynamic_offer_enabled": True,
            "agent_conversation_policy_enabled": True,
            "agent_response_orchestrator_enabled": True,
            "agent_response_orchestrator_log_only": True,
            "agent_execution_sandbox_enabled": True,
            "agent_execution_mode": "dry_run",
            "agent_execution_queue_enabled": False,
            "agent_execution_live_sender_enabled": False,
            "agent_execution_auto_execute_approved": False,
            "agent_followups_enabled": False,
        },
    ),
    "canary": AgentRolloutPresetDefinition(
        name="canary", label="CANARY",
        description="Faqat canary userlar uchun",
        risk_level="high",
        settings={
            "agent_lead_signal_enabled": True,
            "agent_lead_scoring_enabled": True,
            "agent_decision_engine_enabled": True,
            "agent_dynamic_offer_enabled": True,
            "agent_conversation_policy_enabled": True,
            "agent_response_orchestrator_enabled": True,
            "agent_response_orchestrator_log_only": True,
            "agent_execution_sandbox_enabled": True,
            "agent_execution_mode": "canary",
            "agent_execution_queue_enabled": False,
            "agent_execution_live_sender_enabled": False,
            "agent_execution_auto_execute_approved": False,
            "agent_followups_enabled": True,
            "agent_catalog_followup_enabled": True,
            "agent_price_followup_enabled": True,
            "agent_order_followup_enabled": True,
        },
    ),
    "approval_required": AgentRolloutPresetDefinition(
        name="approval_required", label="APPROVAL REQUIRED",
        description="Agent proposal yaratadi, admin approve/reject qiladi",
        risk_level="high",
        settings={
            "agent_lead_signal_enabled": True,
            "agent_lead_scoring_enabled": True,
            "agent_decision_engine_enabled": True,
            "agent_dynamic_offer_enabled": True,
            "agent_conversation_policy_enabled": True,
            "agent_response_orchestrator_enabled": True,
            "agent_response_orchestrator_log_only": True,
            "agent_execution_sandbox_enabled": True,
            "agent_execution_mode": "approval_required",
            "agent_execution_queue_enabled": True,
            "agent_execution_api_approval_enabled": True,
            "agent_execution_auto_execute_approved": False,
            "agent_execution_live_sender_enabled": False,
        },
    ),
    "approved_live_send": AgentRolloutPresetDefinition(
        name="approved_live_send", label="APPROVED LIVE SEND",
        description="Faqat admin approved payloadlar yuboriladi",
        risk_level="critical",
        settings={
            "agent_lead_signal_enabled": True,
            "agent_lead_scoring_enabled": True,
            "agent_decision_engine_enabled": True,
            "agent_dynamic_offer_enabled": True,
            "agent_conversation_policy_enabled": True,
            "agent_response_orchestrator_enabled": True,
            "agent_response_orchestrator_log_only": True,
            "agent_execution_sandbox_enabled": True,
            "agent_execution_mode": "approval_required",
            "agent_execution_queue_enabled": True,
            "agent_execution_api_approval_enabled": True,
            "agent_execution_live_sender_enabled": True,
            "agent_execution_auto_execute_approved": True,
        },
    ),
}


class AgentRolloutPresetService:
    """Staged rollout preset management."""

    @staticmethod
    def list_presets() -> list[AgentRolloutPresetDefinition]:
        return list(_PRESETS.values())

    @staticmethod
    def get_preset(name: str) -> AgentRolloutPresetDefinition | None:
        return _PRESETS.get(name.lower())

    @staticmethod
    def build_preset_settings(name: str) -> dict[str, Any] | None:
        preset = _PRESETS.get(name.lower())
        if preset is None:
            return None
        return dict(preset.settings)

    @staticmethod
    def diff_settings(
        current: dict[str, Any],
        target: dict[str, Any],
    ) -> list[AgentRolloutPresetDiff]:
        from core.services.agent_settings_service import AgentSettingsService
        diffs: list[AgentRolloutPresetDiff] = []
        for key, target_val in sorted(target.items()):
            current_val = current.get(key)
            if current_val != target_val:
                risk = AgentSettingsService.calculate_risk(key, target_val)
                diffs.append(AgentRolloutPresetDiff(
                    key=key,
                    current_value=current_val,
                    target_value=target_val,
                    risk_level=risk,
                ))
        return diffs

    @staticmethod
    def detect_blockers(
        name: str,
        current_settings: dict[str, Any] | None = None,
        allow_live_flags: bool = False,
    ) -> list[str]:
        blockers: list[str] = []
        cs = current_settings or {}

        if name == "canary":
            ids = cs.get("agent_execution_canary_user_ids", "")
            if not str(ids).strip():
                blockers.append("canary_requires_user_ids")

        if name == "approved_live_send":
            if not allow_live_flags:
                blockers.append("live_send_requires_allow_live_flags")

        return blockers

    @staticmethod
    def calculate_preset_risk(name: str) -> str:
        preset = _PRESETS.get(name.lower())
        if preset is None:
            return "none"
        return preset.risk_level

    @staticmethod
    def preview_preset(
        name: str,
        current_settings: dict[str, Any] | None = None,
        allow_live_flags: bool = False,
    ) -> AgentRolloutPresetPreviewResponse:
        preset = _PRESETS.get(name.lower())
        if preset is None:
            return AgentRolloutPresetPreviewResponse(
                preset=name, allowed=False, risk_level="none",
                blockers=[f"unknown_preset:{name}"],
            )

        cs = current_settings or {}
        target = dict(preset.settings)
        blockers = AgentRolloutPresetService.detect_blockers(
            name, cs, allow_live_flags,
        )
        diff = AgentRolloutPresetService.diff_settings(cs, target)
        risk = preset.risk_level

        requires_conf = risk in ("medium", "high", "critical") and not blockers
        token = None
        if requires_conf:
            raw = f"preset:{name}:{secrets.token_hex(8)}"
            token = hashlib.sha256(raw.encode()).hexdigest()[:24]

        return AgentRolloutPresetPreviewResponse(
            preset=name,
            allowed=not blockers,
            risk_level=risk,
            blockers=blockers,
            diff=diff,
            requires_confirmation=requires_conf,
            confirmation_token=token,
        )
