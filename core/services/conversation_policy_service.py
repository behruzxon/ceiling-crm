"""
core.services.conversation_policy_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Deterministic conversation policy engine.

Decides when the bot should reply, stay silent, schedule a follow-up,
escalate to admin, or hand off to an operator.  Pure functions — no I/O.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.schemas.conversation_policy import (
    ConversationPolicyContext,
    ConversationPolicyDecision,
)
from shared.constants.enums import (
    ConversationChannel,
    ConversationPolicyAction,
    ConversationRiskLevel,
)

# ── Terminal states ───────────────────────────────────────────────────────────

_TERMINAL_STATES: frozenset[str] = frozenset(
    {
        "stopped",
        "lost",
        "closed",
    }
)

_MAX_DAILY_FOLLOWUPS = 3
_MAX_LIFETIME_FOLLOWUPS = 5
_NOT_READY_DELAY_MINUTES = 1440  # 24h


class ConversationPolicyService:
    """Rule-based conversation policy engine."""

    @staticmethod
    def evaluate(
        memory: dict[str, Any],
        decision: dict[str, Any] | None = None,
        offer: dict[str, Any] | None = None,
        lead_signal: dict[str, Any] | None = None,
        recent_events: list[dict[str, Any]] | None = None,
        now: datetime | None = None,
    ) -> ConversationPolicyDecision:
        ctx = ConversationPolicyService._build_context(
            memory,
            decision or {},
            offer or {},
            lead_signal or {},
        )
        safety = ConversationPolicyService._check_terminal(ctx)
        if safety is not None:
            return safety

        spam = ConversationPolicyService._check_spam_limits(ctx)
        if spam is not None:
            return spam

        return ConversationPolicyService._select_policy(ctx)

    @staticmethod
    def choose_policy_action(ctx: ConversationPolicyContext) -> str:
        if not ctx.followup_enabled:
            return ConversationPolicyAction.DISABLE_AGENT.value
        if ctx.customer_state in _TERMINAL_STATES:
            return ConversationPolicyAction.NO_ACTION.value
        if ctx.intent == "stop_request":
            return ConversationPolicyAction.DISABLE_AGENT.value
        if ctx.customer_state == "operator_handoff" or ctx.intent == "wants_operator":
            return ConversationPolicyAction.HANDOFF_OPERATOR.value
        if ctx.customer_state == "phone_shared_hot" or ctx.lead_score >= 70:
            return ConversationPolicyAction.ESCALATE_ADMIN.value
        if ctx.urgency == "high" and ctx.lead_temperature in ("warm", "hot"):
            return ConversationPolicyAction.ESCALATE_ADMIN.value
        if ctx.intent in (
            "wants_price",
            "wants_catalog",
            "wants_order",
            "wants_measurement",
            "wants_discount",
        ):
            return ConversationPolicyAction.REPLY_NOW.value
        if ctx.objection_type in ("price", "trust"):
            return ConversationPolicyAction.REPLY_NOW.value
        if ctx.objection_type == "not_ready":
            return ConversationPolicyAction.WAIT_AND_OBSERVE.value
        if ctx.customer_state in ("browsing_catalog", "design_interested"):
            return ConversationPolicyAction.SCHEDULE_FOLLOWUP.value
        if ctx.customer_state == "price_considering":
            return ConversationPolicyAction.SCHEDULE_FOLLOWUP.value
        if ctx.customer_state == "order_abandoned":
            return ConversationPolicyAction.SCHEDULE_FOLLOWUP.value
        if ctx.lead_temperature == "cold" and ctx.intent == "unclear":
            return ConversationPolicyAction.WAIT_AND_OBSERVE.value
        if ctx.lead_temperature == "warm":
            return ConversationPolicyAction.SCHEDULE_FOLLOWUP.value
        return ConversationPolicyAction.WAIT_AND_OBSERVE.value

    @staticmethod
    def choose_channel(
        action: str,
        ctx: ConversationPolicyContext,
    ) -> str:
        if action == ConversationPolicyAction.DISABLE_AGENT.value:
            return ConversationChannel.NONE.value
        if action == ConversationPolicyAction.NO_ACTION.value:
            return ConversationChannel.NONE.value
        if action == ConversationPolicyAction.WAIT_AND_OBSERVE.value:
            return ConversationChannel.INTERNAL_ONLY.value
        if action == ConversationPolicyAction.STORE_ONLY.value:
            return ConversationChannel.INTERNAL_ONLY.value
        if action == ConversationPolicyAction.ESCALATE_ADMIN.value:
            return ConversationChannel.ADMIN_GROUP.value
        if action == ConversationPolicyAction.HANDOFF_OPERATOR.value:
            if ctx.lead_temperature in ("warm", "hot"):
                return ConversationChannel.ADMIN_GROUP.value
            return ConversationChannel.USER_DM.value
        if action == ConversationPolicyAction.REPLY_NOW.value:
            return ConversationChannel.USER_DM.value
        if action == ConversationPolicyAction.SCHEDULE_FOLLOWUP.value:
            return ConversationChannel.USER_DM.value
        return ConversationChannel.INTERNAL_ONLY.value

    @staticmethod
    def assess_risk(ctx: ConversationPolicyContext) -> str:
        if ctx.intent == "stop_request":
            return ConversationRiskLevel.NONE.value
        if ctx.customer_state in _TERMINAL_STATES:
            return ConversationRiskLevel.NONE.value
        if ctx.lifetime_followup_count >= _MAX_LIFETIME_FOLLOWUPS:
            return ConversationRiskLevel.HIGH.value
        if ctx.followup_count >= _MAX_DAILY_FOLLOWUPS:
            return ConversationRiskLevel.HIGH.value
        if ctx.objection_type == "price":
            return ConversationRiskLevel.MEDIUM.value
        if ctx.customer_state == "order_abandoned":
            return ConversationRiskLevel.MEDIUM.value
        if ctx.lead_temperature == "cold" and ctx.intent == "unclear":
            return ConversationRiskLevel.NONE.value
        return ConversationRiskLevel.LOW.value

    @staticmethod
    def should_reply_now(ctx: ConversationPolicyContext) -> bool:
        if not ctx.followup_enabled:
            return False
        if ctx.customer_state in _TERMINAL_STATES:
            return False
        return ctx.intent in (
            "wants_price",
            "wants_catalog",
            "wants_order",
            "wants_measurement",
            "wants_discount",
        ) or ctx.objection_type in ("price", "trust")

    @staticmethod
    def should_schedule_followup(ctx: ConversationPolicyContext) -> bool:
        if not ctx.followup_enabled:
            return False
        if ctx.has_pending_followup:
            return False
        if ctx.lifetime_followup_count >= _MAX_LIFETIME_FOLLOWUPS:
            return False
        if ctx.followup_count >= _MAX_DAILY_FOLLOWUPS:
            return False
        if ctx.intent == "wants_operator":
            return False
        return ctx.customer_state in (
            "browsing_catalog",
            "design_interested",
            "price_considering",
            "order_abandoned",
        ) or (ctx.lead_temperature == "warm" and ctx.intent == "unclear")

    @staticmethod
    def should_escalate_admin(ctx: ConversationPolicyContext) -> bool:
        if ctx.lead_temperature == "cold":
            return False
        if ctx.admin_escalation_cooldown_active:
            return False
        if ctx.customer_state == "phone_shared_hot":
            return True
        if ctx.lead_score >= 70:
            return True
        if ctx.urgency == "high" and ctx.lead_temperature in ("warm", "hot"):
            return True
        return False

    @staticmethod
    def should_handoff_operator(ctx: ConversationPolicyContext) -> bool:
        return ctx.customer_state == "operator_handoff" or ctx.intent == "wants_operator"

    @staticmethod
    def should_cancel_pending(ctx: ConversationPolicyContext) -> bool:
        if ctx.intent == "stop_request":
            return True
        if not ctx.followup_enabled:
            return True
        if ctx.customer_state in _TERMINAL_STATES:
            return True
        if ctx.intent == "wants_operator":
            return True
        return False

    @staticmethod
    def validate_policy(
        policy: ConversationPolicyDecision,
    ) -> tuple[bool, str]:
        if not policy.policy_action:
            return False, "missing_action"
        if not policy.channel:
            return False, "missing_channel"
        if (
            policy.risk_level == ConversationRiskLevel.HIGH.value
            and policy.allowed
            and policy.channel == ConversationChannel.USER_DM.value
        ):
            return False, "high_risk_user_dm_not_allowed"
        return True, "ok"

    @staticmethod
    def store_policy_to_memory(
        memory_data: dict[str, Any],
        policy: ConversationPolicyDecision,
    ) -> dict[str, Any]:
        updated = dict(memory_data)
        updated["last_conversation_policy"] = {
            "policy_action": policy.policy_action,
            "channel": policy.channel,
            "allowed": policy.allowed,
            "reason": policy.reason,
            "risk_level": policy.risk_level,
            "delay_minutes": policy.delay_minutes,
            "should_use_ai_composer": policy.should_use_ai_composer,
            "should_use_dynamic_offer": policy.should_use_dynamic_offer,
            "should_notify_admin": policy.should_notify_admin,
            "created_at": datetime.now(UTC).isoformat(),
        }
        return updated

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _build_context(
        memory: dict[str, Any],
        decision: dict[str, Any],
        offer: dict[str, Any],
        signal: dict[str, Any],
    ) -> ConversationPolicyContext:
        md = memory.get("memory_data") or {}
        intent = signal.get("intent") or md.get("last_intent") or "unclear"
        objection = signal.get("objection_type") or md.get("objection_type")
        urgency = signal.get("urgency") or md.get("urgency") or "low"
        lead_score = md.get("lead_score", 0)
        temp = memory.get("lead_temperature") or "cold"
        state = decision.get("customer_state") or md.get("customer_state") or "new_visitor"
        followup_enabled = memory.get("followup_enabled", True)
        followup_count = memory.get("followup_count", 0)
        lifetime = memory.get("followup_count", 0)
        has_phone = bool(memory.get("phone_masked"))
        has_pending = bool(md.get("has_pending_followup"))
        cooldown = bool(md.get("admin_escalation_cooldown_active"))

        try:
            from shared.config import get_settings

            biz = get_settings().business
            ai_composer = biz.agent_ai_composer_enabled
            dynamic_offer = biz.agent_dynamic_offer_enabled
        except Exception:
            ai_composer = False
            dynamic_offer = False

        return ConversationPolicyContext(
            customer_state=state,
            intent=intent,
            objection_type=objection,
            urgency=urgency,
            lead_score=lead_score,
            lead_temperature=temp,
            followup_enabled=followup_enabled,
            followup_count=followup_count,
            lifetime_followup_count=lifetime,
            has_phone=has_phone,
            has_pending_followup=has_pending,
            admin_escalation_cooldown_active=cooldown,
            offer_type=offer.get("offer_type", "no_offer"),
            ai_composer_enabled=ai_composer,
            dynamic_offer_enabled=dynamic_offer,
        )

    @staticmethod
    def _check_terminal(
        ctx: ConversationPolicyContext,
    ) -> ConversationPolicyDecision | None:
        flags: list[str] = []

        if ctx.intent == "stop_request":
            flags.append("stop_request")
        if not ctx.followup_enabled:
            flags.append("followup_disabled")
        if ctx.customer_state in _TERMINAL_STATES:
            flags.append("terminal_state")

        if not flags:
            return None

        is_stop = "stop_request" in flags or "followup_disabled" in flags
        action = (
            ConversationPolicyAction.DISABLE_AGENT.value
            if is_stop
            else ConversationPolicyAction.NO_ACTION.value
        )

        return ConversationPolicyDecision(
            policy_action=action,
            channel=ConversationChannel.NONE.value,
            allowed=False,
            reason="; ".join(flags),
            risk_level=ConversationRiskLevel.NONE.value,
            should_cancel_pending=is_stop,
            safety_flags=flags,
        )

    @staticmethod
    def _check_spam_limits(
        ctx: ConversationPolicyContext,
    ) -> ConversationPolicyDecision | None:
        if ctx.lifetime_followup_count >= _MAX_LIFETIME_FOLLOWUPS:
            return ConversationPolicyDecision(
                policy_action=ConversationPolicyAction.NO_ACTION.value,
                channel=ConversationChannel.NONE.value,
                allowed=False,
                reason="lifetime_cap_reached",
                risk_level=ConversationRiskLevel.HIGH.value,
                safety_flags=["lifetime_cap"],
            )
        if ctx.followup_count >= _MAX_DAILY_FOLLOWUPS:
            return ConversationPolicyDecision(
                policy_action=ConversationPolicyAction.NO_ACTION.value,
                channel=ConversationChannel.NONE.value,
                allowed=False,
                reason="daily_cap_reached",
                risk_level=ConversationRiskLevel.HIGH.value,
                safety_flags=["daily_cap"],
            )
        return None

    @staticmethod
    def _select_policy(
        ctx: ConversationPolicyContext,
    ) -> ConversationPolicyDecision:
        action = ConversationPolicyService.choose_policy_action(ctx)
        channel = ConversationPolicyService.choose_channel(action, ctx)
        risk = ConversationPolicyService.assess_risk(ctx)

        allowed = True
        flags: list[str] = []

        is_high_risk_dm = (
            risk == ConversationRiskLevel.HIGH.value
            and channel == ConversationChannel.USER_DM.value
        )
        if is_high_risk_dm:
            allowed = False
            flags.append("high_risk_user_dm_blocked")

        escalate = ConversationPolicyAction.ESCALATE_ADMIN.value
        if ctx.lead_temperature == "cold" and action == escalate:
            action = ConversationPolicyAction.WAIT_AND_OBSERVE.value
            channel = ConversationChannel.INTERNAL_ONLY.value
            flags.append("cold_lead_no_escalation")

        if ctx.admin_escalation_cooldown_active and action == escalate:
            action = ConversationPolicyAction.STORE_ONLY.value
            channel = ConversationChannel.INTERNAL_ONLY.value
            flags.append("admin_escalation_cooldown")

        if ctx.has_pending_followup and action == ConversationPolicyAction.SCHEDULE_FOLLOWUP.value:
            action = ConversationPolicyAction.STORE_ONLY.value
            channel = ConversationChannel.INTERNAL_ONLY.value
            flags.append("pending_followup_exists")

        cancel = ConversationPolicyService.should_cancel_pending(ctx)
        notify = ConversationPolicyService.should_escalate_admin(ctx)
        use_ai = ctx.ai_composer_enabled and action == ConversationPolicyAction.REPLY_NOW.value
        use_offer = ctx.dynamic_offer_enabled and action in (
            ConversationPolicyAction.REPLY_NOW.value,
            ConversationPolicyAction.SCHEDULE_FOLLOWUP.value,
        )

        delay: int | None = None
        if action == ConversationPolicyAction.SCHEDULE_FOLLOWUP.value:
            if ctx.objection_type == "not_ready":
                delay = _NOT_READY_DELAY_MINUTES
            else:
                delay = 10

        reason = ConversationPolicyService._build_reason(action, ctx)

        return ConversationPolicyDecision(
            policy_action=action,
            channel=channel,
            allowed=allowed,
            reason=reason,
            risk_level=risk,
            delay_minutes=delay,
            max_retries=1 if action == ConversationPolicyAction.SCHEDULE_FOLLOWUP.value else 0,
            should_use_ai_composer=use_ai,
            should_use_dynamic_offer=use_offer,
            should_notify_admin=notify,
            should_cancel_pending=cancel,
            safety_flags=flags,
        )

    @staticmethod
    def _build_reason(action: str, ctx: ConversationPolicyContext) -> str:
        parts: list[str] = [action]
        if ctx.intent != "unclear":
            parts.append(f"intent={ctx.intent}")
        if ctx.objection_type:
            parts.append(f"objection={ctx.objection_type}")
        if ctx.urgency != "low":
            parts.append(f"urgency={ctx.urgency}")
        parts.append(f"state={ctx.customer_state}")
        parts.append(f"temp={ctx.lead_temperature}")
        return "; ".join(parts)
