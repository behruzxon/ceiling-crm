"""
core.services.agent_effective_settings_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Read-through settings service: runtime DB override → env → safe default.
No writes, no secrets, fail-open to env on DB error.
"""

from __future__ import annotations

import time
from typing import Any

from core.schemas.agent_effective_settings import (
    AgentAdminEscalationSettings,
    AgentAIComposerSettings,
    AgentDecisionSettings,
    AgentEffectiveSettingsSnapshot,
    AgentExecutionSettings,
    AgentFollowupSettings,
    AgentOrchestratorSettings,
    SettingSource,
)
from shared.logging import get_logger

log = get_logger(__name__)

_CACHE: dict[str, Any] = {}
_CACHE_TS: float = 0.0
_CACHE_TTL: float = 30.0


def _env_settings() -> dict[str, Any]:
    try:
        from shared.config import get_settings

        biz = get_settings().business
        return {attr: getattr(biz, attr, None) for attr in dir(biz) if attr.startswith("agent_")}
    except Exception:
        return {}


class AgentEffectiveSettingsService:
    """Read-through agent settings: runtime DB → env → safe defaults."""

    def __init__(self, runtime_overrides: dict[str, Any] | None = None) -> None:
        self._overrides: dict[str, Any] = runtime_overrides or {}
        self._runtime_enabled: bool = False
        try:
            from shared.config import get_settings

            biz = get_settings().business
            self._runtime_enabled = getattr(biz, "agent_runtime_settings_enabled", False)
        except Exception:
            pass

    def get_bool(self, key: str, default: bool = False) -> tuple[bool, str]:
        val, source = self._resolve(key)
        if val is None:
            return default, "default"
        if isinstance(val, bool):
            return val, source
        if isinstance(val, str) and val.lower() in ("true", "false"):
            return val.lower() == "true", source
        return default, "default"

    def get_int(self, key: str, default: int = 0) -> tuple[int, str]:
        val, source = self._resolve(key)
        if val is None:
            return default, "default"
        if isinstance(val, bool):
            return default, "default"
        if isinstance(val, int):
            return val, source
        try:
            return int(val), source
        except (ValueError, TypeError):
            return default, "default"

    def get_str(self, key: str, default: str = "") -> tuple[str, str]:
        val, source = self._resolve(key)
        if val is None:
            return default, "default"
        return str(val), source

    def get_followup_settings(self) -> AgentFollowupSettings:
        return AgentFollowupSettings(
            enabled=self.get_bool("agent_followups_enabled")[0],
            catalog_enabled=self.get_bool("agent_catalog_followup_enabled")[0],
            price_enabled=self.get_bool("agent_price_followup_enabled")[0],
            order_enabled=self.get_bool("agent_order_followup_enabled")[0],
            catalog_delay_minutes=self.get_int("agent_catalog_followup_delay_minutes", 10)[0],
            price_delay_minutes=self.get_int("agent_price_followup_delay_minutes", 10)[0],
            order_delay_minutes=self.get_int("agent_order_followup_delay_minutes", 10)[0],
            max_daily_per_user=self.get_int("agent_execution_max_daily_per_user", 3)[0],
        )

    def get_ai_composer_settings(self) -> AgentAIComposerSettings:
        return AgentAIComposerSettings(
            enabled=self.get_bool("agent_ai_composer_enabled")[0],
            model=self.get_str("agent_ai_composer_model", "gpt-4o-mini")[0],
            timeout_seconds=self.get_int("agent_ai_composer_timeout_seconds", 8)[0],
            max_tokens=self.get_int("agent_ai_composer_max_tokens", 180)[0],
        )

    def get_decision_settings(self) -> AgentDecisionSettings:
        return AgentDecisionSettings(
            decision_enabled=self.get_bool("agent_decision_engine_enabled")[0],
            lead_signal_enabled=self.get_bool("agent_lead_signal_enabled")[0],
            lead_scoring_enabled=self.get_bool("agent_lead_scoring_enabled")[0],
            dynamic_offer_enabled=self.get_bool("agent_dynamic_offer_enabled")[0],
            conversation_policy_enabled=self.get_bool("agent_conversation_policy_enabled")[0],
            min_confidence=self.get_int("agent_decision_min_confidence", 60)[0],
        )

    def get_execution_settings(self) -> AgentExecutionSettings:
        return AgentExecutionSettings(
            sandbox_enabled=self.get_bool("agent_execution_sandbox_enabled")[0],
            execution_mode=self.get_str("agent_execution_mode", "log_only")[0],
            queue_enabled=self.get_bool("agent_execution_queue_enabled")[0],
            api_approval_enabled=self.get_bool("agent_execution_api_approval_enabled")[0],
            live_sender_enabled=self.get_bool("agent_execution_live_sender_enabled")[0],
            auto_execute_approved=self.get_bool("agent_execution_auto_execute_approved")[0],
            batch_limit=self.get_int("agent_execution_live_sender_batch_limit", 10)[0],
            daily_cap=self.get_int("agent_execution_max_daily_per_user", 3)[0],
        )

    def get_orchestrator_settings(self) -> AgentOrchestratorSettings:
        return AgentOrchestratorSettings(
            enabled=self.get_bool("agent_response_orchestrator_enabled")[0],
            log_only=self.get_bool("agent_response_orchestrator_log_only", True)[0],
            min_confidence=self.get_int("agent_response_orchestrator_min_confidence", 60)[0],
            trace_enabled=self.get_bool("agent_response_orchestrator_trace_enabled", True)[0],
        )

    def get_admin_escalation_settings(self) -> AgentAdminEscalationSettings:
        return AgentAdminEscalationSettings(
            enabled=self.get_bool("agent_admin_escalation_enabled")[0],
            after_followups=self.get_int("agent_admin_escalation_after_followups", 2)[0],
            cooldown_minutes=self.get_int("agent_admin_escalation_cooldown_minutes", 60)[0],
        )

    def get_agent_settings_snapshot(self) -> AgentEffectiveSettingsSnapshot:
        sources: list[SettingSource] = []
        for key in sorted(self._overrides):
            sources.append(SettingSource(key=key, value=self._overrides[key], source="runtime"))

        return AgentEffectiveSettingsSnapshot(
            followup=self.get_followup_settings(),
            ai_composer=self.get_ai_composer_settings(),
            decision=self.get_decision_settings(),
            execution=self.get_execution_settings(),
            orchestrator=self.get_orchestrator_settings(),
            escalation=self.get_admin_escalation_settings(),
            sources=sources,
        )

    @staticmethod
    def clear_cache() -> None:
        global _CACHE, _CACHE_TS
        _CACHE = {}
        _CACHE_TS = 0.0

    def _resolve(self, key: str) -> tuple[Any, str]:
        if self._runtime_enabled and key in self._overrides:
            return self._overrides[key], "runtime"
        env = _env_settings()
        if key in env and env[key] is not None:
            return env[key], "env"
        return None, "default"


async def load_runtime_overrides_from_db(session: Any) -> dict[str, Any]:
    """Load active runtime overrides from DB. Returns empty dict on error."""
    global _CACHE, _CACHE_TS
    now = time.monotonic()
    if _CACHE and (now - _CACHE_TS) < _CACHE_TTL:
        return dict(_CACHE)

    try:
        import sqlalchemy as sa

        from infrastructure.database.models.agent_runtime_setting import (
            AgentRuntimeSettingModel,
        )

        stmt = sa.select(AgentRuntimeSettingModel).where(
            AgentRuntimeSettingModel.is_active == sa.true(),
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()

        overrides: dict[str, Any] = {}
        for row in rows:
            val_json = row.value_json or {}
            val = val_json.get("value")
            if val is not None:
                overrides[row.key] = val

        _CACHE = dict(overrides)
        _CACHE_TS = now
        return overrides
    except Exception:
        log.debug("runtime_settings_load_failed")
        return dict(_CACHE) if _CACHE else {}
