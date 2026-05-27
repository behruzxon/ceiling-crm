"""Tests for Step N — ConversationPolicyService."""
from __future__ import annotations

import pytest

from core.schemas.conversation_policy import (
    ConversationPolicyContext,
    ConversationPolicyDecision,
)
from core.services.conversation_policy_service import ConversationPolicyService

svc = ConversationPolicyService


# ── Helpers ───────────────────────────────────────────────────────────────────


def _mem(
    *,
    intent: str = "unclear",
    objection: str | None = None,
    urgency: str = "low",
    lead_score: int = 0,
    temp: str = "cold",
    followup_enabled: bool = True,
    followup_count: int = 0,
    phone: bool = False,
    state: str = "new_visitor",
    has_pending: bool = False,
    admin_cooldown: bool = False,
) -> dict:
    md: dict = {
        "last_intent": intent,
        "urgency": urgency,
        "lead_score": lead_score,
        "customer_state": state,
    }
    if objection:
        md["objection_type"] = objection
    if has_pending:
        md["has_pending_followup"] = True
    if admin_cooldown:
        md["admin_escalation_cooldown_active"] = True
    m: dict = {
        "lead_temperature": temp,
        "followup_enabled": followup_enabled,
        "followup_count": followup_count,
        "memory_data": md,
    }
    if phone:
        m["phone_masked"] = "+998**…**00"
    return m


# ─── 1. Stop / disabled → DISABLE_AGENT ─────────────────────────────────────


class TestStopDisable:
    def test_stop_request_disables(self):
        p = svc.evaluate(_mem(intent="stop_request"))
        assert p.policy_action == "disable_agent"
        assert p.channel == "none"
        assert p.allowed is False
        assert p.should_cancel_pending is True

    def test_followup_disabled_disables(self):
        p = svc.evaluate(_mem(followup_enabled=False))
        assert p.policy_action == "disable_agent"
        assert p.allowed is False
        assert "followup_disabled" in p.safety_flags

    def test_stop_wins_over_hot_lead(self):
        p = svc.evaluate(_mem(intent="stop_request", lead_score=90, temp="hot"))
        assert p.policy_action == "disable_agent"

    def test_stop_cancels_pending(self):
        p = svc.evaluate(_mem(intent="stop_request"))
        assert p.should_cancel_pending is True


# ─── 2. Terminal states → NO_ACTION ──────────────────────────────────────────


class TestTerminalStates:
    def test_lost_no_action(self):
        p = svc.evaluate(_mem(state="lost"), decision={"customer_state": "lost"})
        assert p.policy_action in ("no_action", "disable_agent")
        assert p.allowed is False

    def test_closed_no_action(self):
        p = svc.evaluate(_mem(state="closed"), decision={"customer_state": "closed"})
        assert p.allowed is False

    def test_stopped_no_action(self):
        p = svc.evaluate(_mem(state="stopped"), decision={"customer_state": "stopped"})
        assert p.allowed is False


# ─── 3. Operator handoff ────────────────────────────────────────────────────


class TestOperatorHandoff:
    def test_wants_operator(self):
        p = svc.evaluate(_mem(intent="wants_operator", temp="warm"))
        assert p.policy_action == "handoff_operator"

    def test_operator_state(self):
        p = svc.evaluate(
            _mem(state="operator_handoff", temp="warm"),
            decision={"customer_state": "operator_handoff"},
        )
        assert p.policy_action == "handoff_operator"

    def test_operator_cancels_followups(self):
        p = svc.evaluate(_mem(intent="wants_operator", temp="warm"))
        assert p.should_cancel_pending is True

    def test_operator_warm_admin_channel(self):
        p = svc.evaluate(_mem(intent="wants_operator", temp="warm"))
        assert p.channel == "admin_group"

    def test_operator_cold_user_dm(self):
        p = svc.evaluate(_mem(intent="wants_operator", temp="cold"))
        assert p.channel == "user_dm"


# ─── 4. Phone shared / hot lead → ESCALATE_ADMIN ────────────────────────────


class TestPhoneSharedHot:
    def test_phone_shared_hot(self):
        p = svc.evaluate(
            _mem(state="phone_shared_hot", temp="hot", phone=True),
            decision={"customer_state": "phone_shared_hot"},
        )
        assert p.policy_action == "escalate_admin"
        assert p.channel == "admin_group"

    def test_hot_score_escalates(self):
        p = svc.evaluate(_mem(lead_score=75, temp="hot"))
        assert p.policy_action == "escalate_admin"
        assert p.should_notify_admin is True

    def test_hot_score_no_extra_user_dm(self):
        p = svc.evaluate(_mem(lead_score=75, temp="hot"))
        assert p.channel != "user_dm"


# ─── 5. Direct price question → REPLY_NOW ───────────────────────────────────


class TestReplyNow:
    def test_wants_price_reply(self):
        p = svc.evaluate(_mem(intent="wants_price", temp="warm"))
        assert p.policy_action == "reply_now"
        assert p.channel == "user_dm"

    def test_wants_catalog_reply(self):
        p = svc.evaluate(_mem(intent="wants_catalog", temp="warm"))
        assert p.policy_action == "reply_now"

    def test_wants_order_reply(self):
        p = svc.evaluate(_mem(intent="wants_order", temp="warm"))
        assert p.policy_action == "reply_now"

    def test_wants_measurement_reply(self):
        p = svc.evaluate(_mem(intent="wants_measurement", temp="warm"))
        assert p.policy_action == "reply_now"

    def test_wants_discount_reply(self):
        p = svc.evaluate(_mem(intent="wants_discount", temp="warm"))
        assert p.policy_action == "reply_now"

    def test_reply_uses_dynamic_offer_if_enabled(self):
        p = svc.evaluate(_mem(intent="wants_price", temp="warm"))
        # dynamic_offer_enabled depends on settings, default False
        # but structure is correct
        assert isinstance(p.should_use_dynamic_offer, bool)


# ─── 6. Browsing catalog → SCHEDULE_FOLLOWUP ────────────────────────────────


class TestScheduleFollowup:
    def test_browsing_catalog(self):
        p = svc.evaluate(
            _mem(state="browsing_catalog", temp="warm"),
            decision={"customer_state": "browsing_catalog"},
        )
        assert p.policy_action == "schedule_followup"
        assert p.delay_minutes == 10

    def test_price_considering(self):
        p = svc.evaluate(
            _mem(state="price_considering", temp="warm"),
            decision={"customer_state": "price_considering"},
        )
        assert p.policy_action == "schedule_followup"

    def test_order_abandoned(self):
        p = svc.evaluate(
            _mem(state="order_abandoned", temp="warm"),
            decision={"customer_state": "order_abandoned"},
        )
        assert p.policy_action == "schedule_followup"

    def test_order_abandoned_risk_medium(self):
        p = svc.evaluate(
            _mem(state="order_abandoned", temp="warm"),
            decision={"customer_state": "order_abandoned"},
        )
        assert p.risk_level == "medium"


# ─── 7. High urgency ────────────────────────────────────────────────────────


class TestHighUrgency:
    def test_high_urgency_warm_escalates(self):
        p = svc.evaluate(_mem(urgency="high", temp="warm"))
        assert p.policy_action == "escalate_admin"

    def test_high_urgency_cold_no_escalation(self):
        p = svc.evaluate(_mem(urgency="high", temp="cold"))
        assert p.policy_action != "escalate_admin"


# ─── 8. Objection policies ──────────────────────────────────────────────────


class TestObjectionPolicies:
    def test_price_objection_reply(self):
        p = svc.evaluate(_mem(objection="price", temp="warm"))
        assert p.policy_action == "reply_now"

    def test_price_objection_risk_medium(self):
        p = svc.evaluate(_mem(objection="price", temp="warm"))
        assert p.risk_level == "medium"

    def test_trust_objection_reply(self):
        p = svc.evaluate(_mem(objection="trust", temp="warm"))
        assert p.policy_action == "reply_now"

    def test_not_ready_wait(self):
        p = svc.evaluate(_mem(objection="not_ready", temp="warm"))
        assert p.policy_action in ("wait_and_observe", "schedule_followup")


# ─── 9. Cold unclear → WAIT_AND_OBSERVE ─────────────────────────────────────


class TestColdUnclear:
    def test_cold_unclear_wait(self):
        p = svc.evaluate(_mem())
        assert p.policy_action == "wait_and_observe"
        assert p.channel in ("internal_only", "none")

    def test_cold_unclear_risk_none(self):
        p = svc.evaluate(_mem())
        assert p.risk_level == "none"


# ─── 10. Spam limits ────────────────────────────────────────────────────────


class TestSpamLimits:
    def test_lifetime_cap(self):
        p = svc.evaluate(_mem(followup_count=5, temp="warm", intent="wants_price"))
        assert p.policy_action == "no_action"
        assert p.risk_level == "high"
        assert "lifetime_cap" in p.safety_flags

    def test_daily_cap(self):
        p = svc.evaluate(_mem(followup_count=3, temp="warm", intent="wants_price"))
        assert p.policy_action == "no_action"
        assert p.risk_level == "high"

    def test_normal_count_allowed(self):
        p = svc.evaluate(_mem(followup_count=1, temp="warm", intent="wants_price"))
        assert p.allowed is True


# ─── 11. Admin cooldown ─────────────────────────────────────────────────────


class TestAdminCooldown:
    def test_admin_cooldown_prevents_escalation(self):
        p = svc.evaluate(_mem(
            lead_score=80, temp="hot", admin_cooldown=True,
        ))
        assert p.policy_action != "escalate_admin"
        assert "admin_escalation_cooldown" in p.safety_flags

    def test_no_cooldown_allows_escalation(self):
        p = svc.evaluate(_mem(lead_score=80, temp="hot"))
        assert p.policy_action == "escalate_admin"


# ─── 12. Pending followup ───────────────────────────────────────────────────


class TestPendingFollowup:
    def test_pending_prevents_new_schedule(self):
        p = svc.evaluate(
            _mem(state="browsing_catalog", temp="warm", has_pending=True),
            decision={"customer_state": "browsing_catalog"},
        )
        assert p.policy_action != "schedule_followup"
        assert "pending_followup_exists" in p.safety_flags


# ─── 13. Channel selection ──────────────────────────────────────────────────


class TestChannelSelection:
    def test_escalate_admin_group(self):
        c = svc.choose_channel("escalate_admin", ConversationPolicyContext())
        assert c == "admin_group"

    def test_reply_user_dm(self):
        c = svc.choose_channel("reply_now", ConversationPolicyContext())
        assert c == "user_dm"

    def test_disable_none(self):
        c = svc.choose_channel("disable_agent", ConversationPolicyContext())
        assert c == "none"

    def test_wait_internal(self):
        c = svc.choose_channel("wait_and_observe", ConversationPolicyContext())
        assert c == "internal_only"

    def test_followup_user_dm(self):
        c = svc.choose_channel("schedule_followup", ConversationPolicyContext())
        assert c == "user_dm"


# ─── 14. Risk assessment ────────────────────────────────────────────────────


class TestRiskAssessment:
    def test_stop_risk_none(self):
        ctx = ConversationPolicyContext(intent="stop_request")
        assert svc.assess_risk(ctx) == "none"

    def test_terminal_risk_none(self):
        ctx = ConversationPolicyContext(customer_state="closed")
        assert svc.assess_risk(ctx) == "none"

    def test_price_objection_medium(self):
        ctx = ConversationPolicyContext(objection_type="price")
        assert svc.assess_risk(ctx) == "medium"

    def test_order_abandoned_medium(self):
        ctx = ConversationPolicyContext(customer_state="order_abandoned")
        assert svc.assess_risk(ctx) == "medium"

    def test_lifetime_cap_high(self):
        ctx = ConversationPolicyContext(lifetime_followup_count=5)
        assert svc.assess_risk(ctx) == "high"

    def test_daily_cap_high(self):
        ctx = ConversationPolicyContext(followup_count=3)
        assert svc.assess_risk(ctx) == "high"

    def test_normal_low(self):
        ctx = ConversationPolicyContext(lead_temperature="warm")
        assert svc.assess_risk(ctx) == "low"

    def test_cold_unclear_none(self):
        ctx = ConversationPolicyContext(lead_temperature="cold", intent="unclear")
        assert svc.assess_risk(ctx) == "none"


# ─── 15. Should helpers ─────────────────────────────────────────────────────


class TestShouldHelpers:
    def test_should_reply_price(self):
        ctx = ConversationPolicyContext(intent="wants_price", followup_enabled=True)
        assert svc.should_reply_now(ctx) is True

    def test_should_reply_disabled(self):
        ctx = ConversationPolicyContext(intent="wants_price", followup_enabled=False)
        assert svc.should_reply_now(ctx) is False

    def test_should_schedule_catalog(self):
        ctx = ConversationPolicyContext(
            customer_state="browsing_catalog", followup_enabled=True,
        )
        assert svc.should_schedule_followup(ctx) is True

    def test_should_schedule_pending_blocks(self):
        ctx = ConversationPolicyContext(
            customer_state="browsing_catalog",
            followup_enabled=True,
            has_pending_followup=True,
        )
        assert svc.should_schedule_followup(ctx) is False

    def test_should_schedule_operator_blocks(self):
        ctx = ConversationPolicyContext(
            intent="wants_operator", followup_enabled=True,
        )
        assert svc.should_schedule_followup(ctx) is False

    def test_should_escalate_hot(self):
        ctx = ConversationPolicyContext(
            lead_score=80, lead_temperature="hot",
        )
        assert svc.should_escalate_admin(ctx) is True

    def test_should_escalate_cold_no(self):
        ctx = ConversationPolicyContext(
            lead_score=80, lead_temperature="cold",
        )
        assert svc.should_escalate_admin(ctx) is False

    def test_should_escalate_cooldown_no(self):
        ctx = ConversationPolicyContext(
            lead_score=80, lead_temperature="hot",
            admin_escalation_cooldown_active=True,
        )
        assert svc.should_escalate_admin(ctx) is False

    def test_should_handoff(self):
        ctx = ConversationPolicyContext(intent="wants_operator")
        assert svc.should_handoff_operator(ctx) is True

    def test_should_cancel_stop(self):
        ctx = ConversationPolicyContext(intent="stop_request")
        assert svc.should_cancel_pending(ctx) is True

    def test_should_cancel_operator(self):
        ctx = ConversationPolicyContext(intent="wants_operator")
        assert svc.should_cancel_pending(ctx) is True


# ─── 16. Validation ─────────────────────────────────────────────────────────


class TestValidation:
    def test_valid_policy(self):
        p = svc.evaluate(_mem(intent="wants_price", temp="warm"))
        ok, reason = svc.validate_policy(p)
        assert ok is True

    def test_high_risk_user_dm_invalid(self):
        p = ConversationPolicyDecision(
            policy_action="reply_now",
            channel="user_dm",
            allowed=True,
            reason="test",
            risk_level="high",
        )
        ok, reason = svc.validate_policy(p)
        assert ok is False
        assert reason == "high_risk_user_dm_not_allowed"


# ─── 17. Memory storage ─────────────────────────────────────────────────────


class TestMemoryStorage:
    def test_store_policy(self):
        p = svc.evaluate(_mem(intent="wants_price", temp="warm"))
        md = svc.store_policy_to_memory({}, p)
        stored = md["last_conversation_policy"]
        assert stored["policy_action"] == p.policy_action
        assert stored["channel"] == p.channel
        assert "created_at" in stored

    def test_store_preserves_existing(self):
        p = svc.evaluate(_mem())
        md = svc.store_policy_to_memory({"key": 42}, p)
        assert md["key"] == 42
        assert "last_conversation_policy" in md


# ─── 18. Decision engine integration ────────────────────────────────────────


class TestDecisionEngineIntegration:
    def test_evaluate_full_returns_triple(self):
        from core.services.agent_decision_engine import evaluate_full
        memory = {"followup_enabled": True, "memory_data": {}}
        decision, offer, policy = evaluate_full(memory, [])
        assert decision is not None
        # offer and policy are None because feature flags are off
        assert offer is None
        assert policy is None

    def test_evaluate_still_works(self):
        from core.services.agent_decision_engine import evaluate
        memory = {"followup_enabled": True, "memory_data": {}}
        decision = evaluate(memory, [])
        assert decision.customer_state is not None


# ─── 19. Schema immutability ────────────────────────────────────────────────


class TestImmutability:
    def test_decision_frozen(self):
        p = svc.evaluate(_mem())
        with pytest.raises(AttributeError):
            p.policy_action = "other"  # type: ignore[misc]

    def test_context_frozen(self):
        ctx = ConversationPolicyContext()
        with pytest.raises(AttributeError):
            ctx.intent = "other"  # type: ignore[misc]


# ─── 20. Not-ready delay ────────────────────────────────────────────────────


class TestNotReadyDelay:
    def test_not_ready_long_delay(self):
        p = svc.evaluate(
            _mem(objection="not_ready", state="price_considering", temp="warm"),
            decision={"customer_state": "price_considering"},
        )
        if p.policy_action == "schedule_followup":
            assert p.delay_minutes == 1440
