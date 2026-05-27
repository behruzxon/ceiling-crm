"""
core.services.agent_response_orchestrator
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Coordinates the full agent response pipeline:
  signal → decision → offer → policy → payload → safety → trace.

Pure static methods for the core logic; async entry points for DB I/O.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from core.schemas.agent_orchestrator import AgentResponsePayload
from shared.constants.enums import (
    AgentOrchestratorAction,
    AgentOrchestratorSource,
)
from shared.logging import get_logger

log = get_logger(__name__)

# ── Reply text templates ──────────────────────────────────────────────────────

_REPLY_TEXTS: dict[str, str] = {
    "stop": "Tushunarli 😊 Sizga boshqa xabar yubormaymiz.",
    "operator": ("Operatorimiz tez orada siz bilan bog'lanadi 👨‍💼"),
    "price_ask_area": ("Kvadratingizni yozsangiz, taxminiy narxni " "hisoblab beraman 📐"),
    "price_ask_design": ("Qaysi turini tanlaysiz: oddiy, gulli yoki premium?"),
    "cheaper_option": (
        "Arzonroq variantdan ham hisoblab berish mumkin. " "Operator bilan kelishiladi 😊"
    ),
    "warranty_trust": ("Bajarilgan ishlar va kafolat bo'yicha " "batafsil ma'lumot beramiz ✅"),
    "design_help": ("Katalogdan mos model tanlashga yordam beraman 🎨"),
    "fast_install": ("Tezkor o'lchov uchun operatorimiz yordam beradi ⚡"),
    "order_continue": "Buyurtmani davom ettiramizmi? 😊",
    "callback_request": (
        "Telefon raqamingizni yuborsangiz, operatorimiz " "siz bilan bog'lanadi 📞"
    ),
    "discount_discuss": ("Chegirma bo'yicha operator bilan kelishiladi 😊"),
    "measurement": ("Usta kelib bepul o'lchov qilib beradi 📏"),
}

_ADMIN_ALERT_TEMPLATE = (
    "🔔 Agent alert\n" "User: {user_id}\n" "Action: {action}\n" "Reason: {reason}"
)

_PHONE_RE = re.compile(r"\+?\d{9,15}")
_TOKEN_RE = re.compile(r"(?:sk-|token[=:]|Bearer\s)\S+", re.IGNORECASE)

# ── Offer-type → reply-key mapping ──────────────────────────────────────────

_OFFER_REPLY_MAP: dict[str, str] = {
    "price_calculation": "price_ask_area",
    "cheaper_option": "cheaper_option",
    "warranty_trust": "warranty_trust",
    "portfolio_social_proof": "warranty_trust",
    "design_help": "design_help",
    "fast_installation": "fast_install",
    "operator_consultation": "operator",
    "order_continue": "order_continue",
    "callback_request": "callback_request",
    "discount_discussion": "discount_discuss",
    "measurement_visit": "measurement",
    "premium_option": "design_help",
}


class AgentResponseOrchestrator:
    """Coordinates signal → decision → offer → policy → payload."""

    @staticmethod
    def run_pipeline(
        memory: dict[str, Any],
        text: str | None = None,
        source: str = AgentOrchestratorSource.USER_MESSAGE.value,
        followup_type: str | None = None,
        event_type: str | None = None,
        event_data: dict[str, Any] | None = None,
    ) -> AgentResponsePayload:
        signal_dict: dict[str, Any] = {}
        if text:
            try:
                from core.services.lead_signal_service import (
                    LeadSignalService,
                )

                sig = LeadSignalService.extract_signals(text)
                signal_dict = {
                    "intent": sig.intent,
                    "objection_type": sig.objection_type,
                    "urgency": sig.urgency,
                    "area_m2": sig.area_m2,
                    "budget_amount": sig.budget_amount,
                    "lead_score_delta": sig.lead_score_delta,
                    "confidence_score": sig.confidence_score,
                }
            except Exception:
                pass

        decision_dict: dict[str, Any] = {}
        offer_dict: dict[str, Any] = {}
        try:
            from core.services import agent_decision_engine as ade

            decision = ade.evaluate(memory, [])
            decision_dict = {
                "customer_state": decision.customer_state,
                "action_type": decision.action_type,
                "priority_score": decision.priority_score,
                "confidence_score": decision.confidence_score,
            }
        except Exception:
            pass

        try:
            from core.services.dynamic_offer_service import (
                DynamicOfferService,
            )

            offer = DynamicOfferService.choose_offer(
                memory=memory,
                lead_signal=signal_dict or None,
                recent_events=[],
            )
            offer_dict = {
                "offer_type": offer.offer_type,
                "cta": offer.cta,
                "priority": offer.priority,
                "message_hint": offer.message_hint,
                "recommended_buttons": offer.recommended_buttons,
                "should_notify_admin": offer.should_notify_admin,
            }
        except Exception:
            pass

        policy_dict: dict[str, Any] = {}
        try:
            from core.services.conversation_policy_service import (
                ConversationPolicyService,
            )

            policy = ConversationPolicyService.evaluate(
                memory=memory,
                decision=decision_dict,
                offer=offer_dict,
                lead_signal=signal_dict or None,
            )
            policy_dict = {
                "policy_action": policy.policy_action,
                "channel": policy.channel,
                "allowed": policy.allowed,
                "risk_level": policy.risk_level,
                "delay_minutes": policy.delay_minutes,
                "should_use_ai_composer": policy.should_use_ai_composer,
                "should_use_dynamic_offer": policy.should_use_dynamic_offer,
                "should_notify_admin": policy.should_notify_admin,
                "should_cancel_pending": policy.should_cancel_pending,
                "safety_flags": policy.safety_flags,
            }
        except Exception:
            pass

        payload = AgentResponseOrchestrator.build_response_payload(
            memory=memory,
            signal=signal_dict,
            decision=decision_dict,
            offer=offer_dict,
            policy=policy_dict,
            source=source,
            followup_type=followup_type,
        )

        payload = AgentResponseOrchestrator.apply_safety(
            payload,
            policy_dict,
        )

        return payload

    @staticmethod
    def build_response_payload(
        memory: dict[str, Any],
        signal: dict[str, Any],
        decision: dict[str, Any],
        offer: dict[str, Any],
        policy: dict[str, Any],
        source: str,
        followup_type: str | None = None,
    ) -> AgentResponsePayload:
        policy_action = policy.get("policy_action", "store_only")
        allowed = policy.get("allowed", True)
        cancel = policy.get("should_cancel_pending", False)
        delay = policy.get("delay_minutes")
        notify_admin = policy.get("should_notify_admin", False)
        flags: list[str] = list(policy.get("safety_flags") or [])

        action = AgentResponseOrchestrator._map_action(
            policy_action,
            signal,
            offer,
            source,
        )
        msg_text = AgentResponseOrchestrator._build_reply_text(
            action,
            signal,
            offer,
        )
        buttons = AgentResponseOrchestrator._build_buttons(offer)
        admin_text = AgentResponseOrchestrator._build_admin_alert(
            action,
            notify_admin,
            memory,
            signal,
        )
        disable = action == AgentOrchestratorAction.DISABLE_AGENT.value

        trace = AgentResponseOrchestrator.build_trace(
            signal,
            decision,
            offer,
            policy,
            action,
            source,
        )

        return AgentResponsePayload(
            action=action,
            source=source,
            allowed=allowed,
            reason=policy.get("reason", ""),
            user_message_text=msg_text,
            user_buttons=buttons,
            admin_alert_text=admin_text,
            followup_type=followup_type or policy.get("followup_type"),
            delay_minutes=delay,
            cancel_pending=cancel,
            disable_agent=disable,
            should_commit_memory=True,
            safety_flags=flags,
            debug_trace=trace,
        )

    @staticmethod
    def apply_safety(
        payload: AgentResponsePayload,
        policy: dict[str, Any],
    ) -> AgentResponsePayload:
        flags = list(payload.safety_flags)
        allowed = payload.allowed
        action = payload.action
        msg = payload.user_message_text

        if not policy.get("allowed", True):
            allowed = False
            if action == AgentOrchestratorAction.SEND_USER_REPLY.value:
                action = AgentOrchestratorAction.STORE_MEMORY_ONLY.value
                flags.append("policy_denied")

        risk = policy.get("risk_level", "none")
        if risk == "high" and action == AgentOrchestratorAction.SEND_USER_REPLY.value:
            action = AgentOrchestratorAction.STORE_MEMORY_ONLY.value
            allowed = False
            flags.append("high_risk_blocked")

        intent = (payload.debug_trace.get("signal") or {}).get("intent")
        if intent == "stop_request":
            action = AgentOrchestratorAction.DISABLE_AGENT.value
            msg = _REPLY_TEXTS["stop"]
            allowed = True
            flags = [
                f
                for f in flags
                if f
                not in (
                    "policy_denied",
                    "high_risk_blocked",
                )
            ]

        if (
            flags != payload.safety_flags
            or allowed != payload.allowed
            or action != payload.action
            or msg != payload.user_message_text
        ):
            return AgentResponsePayload(
                action=action,
                source=payload.source,
                allowed=allowed,
                reason=payload.reason,
                user_message_text=msg,
                user_buttons=payload.user_buttons,
                admin_alert_text=payload.admin_alert_text,
                followup_type=payload.followup_type,
                delay_minutes=payload.delay_minutes,
                cancel_pending=payload.cancel_pending,
                disable_agent=(action == AgentOrchestratorAction.DISABLE_AGENT.value),
                should_commit_memory=payload.should_commit_memory,
                safety_flags=flags,
                debug_trace=payload.debug_trace,
                metadata=payload.metadata,
            )
        return payload

    @staticmethod
    def build_trace(
        signal: dict[str, Any],
        decision: dict[str, Any],
        offer: dict[str, Any],
        policy: dict[str, Any],
        action: str,
        source: str,
    ) -> dict[str, Any]:
        safe_signal = AgentResponseOrchestrator._redact(dict(signal))
        return {
            "source": source,
            "action": action,
            "signal": safe_signal,
            "decision": {
                k: decision[k]
                for k in (
                    "customer_state",
                    "action_type",
                    "priority_score",
                    "confidence_score",
                )
                if k in decision
            },
            "offer": {k: offer[k] for k in ("offer_type", "cta", "priority") if k in offer},
            "policy": {
                k: policy[k]
                for k in (
                    "policy_action",
                    "channel",
                    "allowed",
                    "risk_level",
                )
                if k in policy
            },
            "created_at": datetime.now(UTC).isoformat(),
        }

    @staticmethod
    def persist_trace(
        memory_data: dict[str, Any],
        payload: AgentResponsePayload,
    ) -> dict[str, Any]:
        updated = dict(memory_data)
        updated["last_orchestrator_trace"] = {
            "source": payload.source,
            "action": payload.action,
            "allowed": payload.allowed,
            "reason": payload.reason,
            "safety_flags": payload.safety_flags,
            "created_at": datetime.now(UTC).isoformat(),
        }
        return updated

    @staticmethod
    def fallback_payload(
        reason: str,
        source: str = AgentOrchestratorSource.USER_MESSAGE.value,
    ) -> AgentResponsePayload:
        return AgentResponsePayload(
            action=AgentOrchestratorAction.STORE_MEMORY_ONLY.value,
            source=source,
            allowed=False,
            reason=f"fallback: {reason}",
            safety_flags=["orchestrator_fallback"],
        )

    # ── Private helpers ───────────────────────────────────────────────────

    @staticmethod
    def _map_action(
        policy_action: str,
        signal: dict[str, Any],
        offer: dict[str, Any],
        source: str,
    ) -> str:
        action_map = {
            "disable_agent": AgentOrchestratorAction.DISABLE_AGENT.value,
            "no_action": AgentOrchestratorAction.NO_ACTION.value,
            "handoff_operator": AgentOrchestratorAction.HANDOFF_OPERATOR.value,
            "escalate_admin": AgentOrchestratorAction.SEND_ADMIN_ALERT.value,
            "cancel_followups": AgentOrchestratorAction.CANCEL_FOLLOWUPS.value,
            "wait_and_observe": AgentOrchestratorAction.STORE_MEMORY_ONLY.value,
            "store_only": AgentOrchestratorAction.STORE_MEMORY_ONLY.value,
        }
        if policy_action in action_map:
            return action_map[policy_action]

        if policy_action == "reply_now":
            return AgentOrchestratorAction.SEND_USER_REPLY.value
        if policy_action == "schedule_followup":
            return AgentOrchestratorAction.SCHEDULE_FOLLOWUP.value

        return AgentOrchestratorAction.STORE_MEMORY_ONLY.value

    @staticmethod
    def _build_reply_text(
        action: str,
        signal: dict[str, Any],
        offer: dict[str, Any],
    ) -> str | None:
        if action == AgentOrchestratorAction.DISABLE_AGENT.value:
            return _REPLY_TEXTS["stop"]

        if action == AgentOrchestratorAction.HANDOFF_OPERATOR.value:
            return _REPLY_TEXTS["operator"]

        if action not in (
            AgentOrchestratorAction.SEND_USER_REPLY.value,
            AgentOrchestratorAction.SCHEDULE_FOLLOWUP.value,
        ):
            return None

        offer_type = offer.get("offer_type", "")
        hint = offer.get("message_hint", "")

        if offer_type == "price_calculation":
            area = signal.get("area_m2")
            if area:
                return _REPLY_TEXTS["price_ask_design"]
            return _REPLY_TEXTS["price_ask_area"]

        key = _OFFER_REPLY_MAP.get(offer_type)
        if key and key in _REPLY_TEXTS:
            return _REPLY_TEXTS[key]

        if hint:
            return hint

        return None

    @staticmethod
    def _build_buttons(
        offer: dict[str, Any],
    ) -> list[tuple[str, str]] | None:
        btns = offer.get("recommended_buttons")
        if btns and isinstance(btns, list) and len(btns) > 0:
            return btns
        return None

    @staticmethod
    def _build_admin_alert(
        action: str,
        notify: bool,
        memory: dict[str, Any],
        signal: dict[str, Any],
    ) -> str | None:
        if action == AgentOrchestratorAction.SEND_ADMIN_ALERT.value:
            return _ADMIN_ALERT_TEMPLATE.format(
                user_id=memory.get("telegram_user_id", "?"),
                action=action,
                reason=signal.get("intent", "escalation"),
            )
        if notify and action in (
            AgentOrchestratorAction.HANDOFF_OPERATOR.value,
            AgentOrchestratorAction.SEND_USER_REPLY.value,
        ):
            return _ADMIN_ALERT_TEMPLATE.format(
                user_id=memory.get("telegram_user_id", "?"),
                action=action,
                reason=signal.get("intent", "notify"),
            )
        return None

    @staticmethod
    def _redact(data: dict[str, Any]) -> dict[str, Any]:
        for key, val in data.items():
            if isinstance(val, str):
                val = _PHONE_RE.sub("[REDACTED_PHONE]", val)
                val = _TOKEN_RE.sub("[REDACTED_TOKEN]", val)
                data[key] = val
        return data
