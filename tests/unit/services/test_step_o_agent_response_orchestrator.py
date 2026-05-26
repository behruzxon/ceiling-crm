"""Tests for Step O — AgentResponseOrchestrator."""
from __future__ import annotations

import pytest

from core.schemas.agent_orchestrator import AgentResponsePayload
from core.services.agent_response_orchestrator import AgentResponseOrchestrator
from shared.constants.enums import AgentOrchestratorAction, AgentOrchestratorSource

orch = AgentResponseOrchestrator


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
) -> dict:
    md: dict = {
        "last_intent": intent,
        "urgency": urgency,
        "lead_score": lead_score,
        "customer_state": state,
    }
    if objection:
        md["objection_type"] = objection
    m: dict = {
        "lead_temperature": temp,
        "followup_enabled": followup_enabled,
        "followup_count": followup_count,
        "memory_data": md,
        "telegram_user_id": 12345,
    }
    if phone:
        m["phone_masked"] = "+998**…**00"
    return m


# ─── 1. run_pipeline full integration ───────────────────────────────────────


class TestRunPipeline:
    def test_stop_request(self):
        p = orch.run_pipeline(_mem(), text="kerak emas")
        assert p.action == "disable_agent"
        assert p.cancel_pending is True
        assert p.allowed is True
        assert "yubormaymiz" in (p.user_message_text or "").lower()

    def test_price_question_no_area(self):
        p = orch.run_pipeline(_mem(temp="warm"), text="narxi qancha")
        assert p.action == "send_user_reply"
        assert p.user_message_text is not None
        assert "kvadrat" in p.user_message_text.lower()

    def test_price_question_with_area(self):
        p = orch.run_pipeline(_mem(temp="warm"), text="20 kv qancha")
        assert p.action == "send_user_reply"
        assert "turini" in (p.user_message_text or "").lower()

    def test_price_objection(self):
        p = orch.run_pipeline(_mem(temp="warm"), text="qimmat ekan")
        assert p.action == "send_user_reply"
        assert "arzon" in (p.user_message_text or "").lower()

    def test_trust_objection(self):
        p = orch.run_pipeline(_mem(temp="warm"), text="kafolat bormi")
        assert p.action == "send_user_reply"
        assert p.user_message_text is not None

    def test_operator_request(self):
        p = orch.run_pipeline(_mem(temp="warm"), text="operator chaqiring")
        assert p.action in ("handoff_operator", "send_user_reply")
        assert p.cancel_pending is True

    def test_cold_unclear(self):
        p = orch.run_pipeline(_mem(), text="salom")
        assert p.action in ("store_memory_only", "no_action")

    def test_hot_lead(self):
        p = orch.run_pipeline(
            _mem(lead_score=80, temp="hot"),
            text="salom",
        )
        assert p.action == "send_admin_alert"
        assert p.admin_alert_text is not None

    def test_wants_catalog(self):
        p = orch.run_pipeline(_mem(temp="warm"), text="katalog bormi")
        assert p.action == "send_user_reply"

    def test_wants_order(self):
        p = orch.run_pipeline(_mem(temp="warm"), text="zakaz beraman")
        assert p.action == "send_user_reply"

    def test_wants_discount(self):
        p = orch.run_pipeline(_mem(temp="warm"), text="chegirma bormi")
        assert p.action == "send_user_reply"
        assert "operator" in (p.user_message_text or "").lower()

    def test_wants_measurement(self):
        p = orch.run_pipeline(_mem(temp="warm"), text="usta chaqiring")
        assert p.action in ("send_user_reply", "handoff_operator")


# ─── 2. build_response_payload ──────────────────────────────────────────────


class TestBuildPayload:
    def test_reply_now_produces_send(self):
        p = orch.build_response_payload(
            memory=_mem(),
            signal={"intent": "wants_price"},
            decision={"customer_state": "price_checking"},
            offer={"offer_type": "price_calculation", "cta": "ask_area"},
            policy={"policy_action": "reply_now", "allowed": True},
            source="user_message",
        )
        assert p.action == "send_user_reply"
        assert p.allowed is True

    def test_disable_agent_payload(self):
        p = orch.build_response_payload(
            memory=_mem(),
            signal={"intent": "stop_request"},
            decision={},
            offer={},
            policy={
                "policy_action": "disable_agent",
                "allowed": False,
                "should_cancel_pending": True,
            },
            source="user_message",
        )
        assert p.action == "disable_agent"
        assert p.disable_agent is True
        assert p.cancel_pending is True

    def test_escalate_produces_admin_alert(self):
        p = orch.build_response_payload(
            memory=_mem(temp="hot"),
            signal={"intent": "unclear"},
            decision={"customer_state": "phone_shared_hot"},
            offer={"should_notify_admin": True},
            policy={
                "policy_action": "escalate_admin",
                "allowed": True,
                "should_notify_admin": True,
            },
            source="user_message",
        )
        assert p.action == "send_admin_alert"
        assert p.admin_alert_text is not None

    def test_schedule_followup(self):
        p = orch.build_response_payload(
            memory=_mem(temp="warm"),
            signal={},
            decision={"customer_state": "browsing_catalog"},
            offer={"offer_type": "design_help"},
            policy={
                "policy_action": "schedule_followup",
                "allowed": True,
                "delay_minutes": 10,
            },
            source="user_message",
        )
        assert p.action == "schedule_followup"
        assert p.delay_minutes == 10

    def test_store_only_for_wait(self):
        p = orch.build_response_payload(
            memory=_mem(),
            signal={},
            decision={},
            offer={},
            policy={"policy_action": "wait_and_observe", "allowed": True},
            source="user_message",
        )
        assert p.action == "store_memory_only"

    def test_handoff_operator(self):
        p = orch.build_response_payload(
            memory=_mem(),
            signal={"intent": "wants_operator"},
            decision={},
            offer={},
            policy={
                "policy_action": "handoff_operator",
                "allowed": True,
                "should_cancel_pending": True,
            },
            source="user_message",
        )
        assert p.action == "handoff_operator"
        assert "operator" in (p.user_message_text or "").lower()


# ─── 3. apply_safety ────────────────────────────────────────────────────────


class TestApplySafety:
    def test_policy_denied_blocks_reply(self):
        payload = AgentResponsePayload(
            action="send_user_reply",
            source="user_message",
            allowed=True,
            reason="test",
            user_message_text="hello",
        )
        result = orch.apply_safety(payload, {"allowed": False})
        assert result.allowed is False
        assert result.action == "store_memory_only"
        assert "policy_denied" in result.safety_flags

    def test_high_risk_blocks_user_dm(self):
        payload = AgentResponsePayload(
            action="send_user_reply",
            source="user_message",
            allowed=True,
            reason="test",
        )
        result = orch.apply_safety(
            payload, {"allowed": True, "risk_level": "high"},
        )
        assert result.allowed is False
        assert "high_risk_blocked" in result.safety_flags

    def test_stop_overrides_policy_denied(self):
        payload = AgentResponsePayload(
            action="send_user_reply",
            source="user_message",
            allowed=True,
            reason="test",
            debug_trace={"signal": {"intent": "stop_request"}},
        )
        result = orch.apply_safety(
            payload, {"allowed": False, "risk_level": "high"},
        )
        assert result.action == "disable_agent"
        assert result.allowed is True

    def test_safe_payload_unchanged(self):
        payload = AgentResponsePayload(
            action="send_user_reply",
            source="user_message",
            allowed=True,
            reason="test",
        )
        result = orch.apply_safety(payload, {"allowed": True})
        assert result.action == "send_user_reply"
        assert result.allowed is True


# ─── 4. Reply text generation ───────────────────────────────────────────────


class TestReplyText:
    def test_stop_text(self):
        t = orch._build_reply_text("disable_agent", {}, {})
        assert "xabar yubormaymiz" in (t or "").lower()

    def test_operator_text(self):
        t = orch._build_reply_text("handoff_operator", {}, {})
        assert "operator" in (t or "").lower()

    def test_price_no_area_text(self):
        t = orch._build_reply_text(
            "send_user_reply", {}, {"offer_type": "price_calculation"},
        )
        assert "kvadrat" in (t or "").lower()

    def test_price_with_area_text(self):
        t = orch._build_reply_text(
            "send_user_reply",
            {"area_m2": 20.0},
            {"offer_type": "price_calculation"},
        )
        assert "turini" in (t or "").lower()

    def test_cheaper_option_text(self):
        t = orch._build_reply_text(
            "send_user_reply", {}, {"offer_type": "cheaper_option"},
        )
        assert "arzon" in (t or "").lower()

    def test_warranty_text(self):
        t = orch._build_reply_text(
            "send_user_reply", {}, {"offer_type": "warranty_trust"},
        )
        assert "kafolat" in (t or "").lower()

    def test_design_help_text(self):
        t = orch._build_reply_text(
            "send_user_reply", {}, {"offer_type": "design_help"},
        )
        assert "katalog" in (t or "").lower()

    def test_no_action_none(self):
        t = orch._build_reply_text("no_action", {}, {})
        assert t is None

    def test_store_only_none(self):
        t = orch._build_reply_text("store_memory_only", {}, {})
        assert t is None

    def test_fallback_hint(self):
        t = orch._build_reply_text(
            "send_user_reply", {},
            {"offer_type": "unknown", "message_hint": "Custom hint"},
        )
        assert t == "Custom hint"

    def test_no_offer_no_hint_none(self):
        t = orch._build_reply_text(
            "send_user_reply", {}, {"offer_type": "no_offer"},
        )
        assert t is None


# ─── 5. Buttons ──────────────────────────────────────────────────────────────


class TestButtons:
    def test_offer_buttons_passed(self):
        btns = orch._build_buttons({
            "recommended_buttons": [("Btn", "cb:data")],
        })
        assert btns == [("Btn", "cb:data")]

    def test_empty_buttons_none(self):
        btns = orch._build_buttons({})
        assert btns is None

    def test_empty_list_none(self):
        btns = orch._build_buttons({"recommended_buttons": []})
        assert btns is None


# ─── 6. Trace ────────────────────────────────────────────────────────────────


class TestTrace:
    def test_trace_has_all_keys(self):
        trace = orch.build_trace(
            signal={"intent": "wants_price"},
            decision={"customer_state": "price_checking", "action_type": "wait"},
            offer={"offer_type": "price_calculation", "cta": "ask_area"},
            policy={"policy_action": "reply_now", "channel": "user_dm",
                    "allowed": True, "risk_level": "low"},
            action="send_user_reply",
            source="user_message",
        )
        assert trace["source"] == "user_message"
        assert trace["action"] == "send_user_reply"
        assert "signal" in trace
        assert "decision" in trace
        assert "offer" in trace
        assert "policy" in trace
        assert "created_at" in trace

    def test_trace_redacts_phone(self):
        trace = orch.build_trace(
            signal={"intent": "price", "phone": "+998901234567"},
            decision={},
            offer={},
            policy={},
            action="test",
            source="test",
        )
        phone_val = trace["signal"].get("phone", "")
        assert "+998" not in phone_val

    def test_trace_redacts_token(self):
        trace = orch.build_trace(
            signal={"text": "sk-abc123secret"},
            decision={},
            offer={},
            policy={},
            action="test",
            source="test",
        )
        text_val = trace["signal"].get("text", "")
        assert "sk-abc" not in text_val


# ─── 7. persist_trace ───────────────────────────────────────────────────────


class TestPersistTrace:
    def test_persist_stores_trace(self):
        payload = orch.fallback_payload("test")
        md = orch.persist_trace({}, payload)
        assert "last_orchestrator_trace" in md
        stored = md["last_orchestrator_trace"]
        assert stored["action"] == payload.action
        assert "created_at" in stored

    def test_persist_preserves_existing(self):
        payload = orch.fallback_payload("test")
        md = orch.persist_trace({"key": 42}, payload)
        assert md["key"] == 42


# ─── 8. fallback_payload ────────────────────────────────────────────────────


class TestFallbackPayload:
    def test_fallback_is_store_only(self):
        p = orch.fallback_payload("some error")
        assert p.action == "store_memory_only"
        assert p.allowed is False
        assert "orchestrator_fallback" in p.safety_flags

    def test_fallback_includes_reason(self):
        p = orch.fallback_payload("signal_error")
        assert "signal_error" in p.reason

    def test_fallback_custom_source(self):
        p = orch.fallback_payload("err", source="followup_due")
        assert p.source == "followup_due"


# ─── 9. Followup due pipeline ───────────────────────────────────────────────


class TestFollowupDue:
    def test_followup_catalog_warm(self):
        p = orch.run_pipeline(
            _mem(temp="warm", state="browsing_catalog"),
            source="followup_due",
            followup_type="catalog",
        )
        assert p.source == "followup_due"
        assert p.followup_type == "catalog"

    def test_followup_disabled_no_send(self):
        p = orch.run_pipeline(
            _mem(followup_enabled=False),
            source="followup_due",
            followup_type="catalog",
        )
        assert p.action in ("disable_agent", "store_memory_only", "no_action")
        assert p.allowed is False


# ─── 10. Safety edge cases ──────────────────────────────────────────────────


class TestSafetyEdgeCases:
    def test_no_fake_discount_in_cheaper(self):
        p = orch.run_pipeline(_mem(temp="warm"), text="qimmat ekan")
        if p.user_message_text:
            assert "eng arzon" not in p.user_message_text.lower()

    def test_no_bugun_qilamiz(self):
        p = orch.run_pipeline(
            _mem(urgency="high", temp="warm"), text="bugun kerak",
        )
        if p.user_message_text:
            assert "bugun qilamiz" not in p.user_message_text.lower()

    def test_phone_shared_no_user_spam(self):
        p = orch.run_pipeline(
            _mem(state="phone_shared_hot", temp="hot", phone=True),
            text="salom",
        )
        assert p.action != "send_user_reply"

    def test_cold_no_admin_escalation(self):
        p = orch.run_pipeline(_mem(lead_score=80, temp="cold"), text="salom")
        assert p.action != "send_admin_alert"

    def test_lifetime_cap_blocks(self):
        p = orch.run_pipeline(
            _mem(followup_count=5, temp="warm", intent="wants_price"),
            text="narxi qancha",
        )
        assert p.allowed is False


# ─── 11. Schema immutability ────────────────────────────────────────────────


class TestImmutability:
    def test_payload_frozen(self):
        p = orch.fallback_payload("test")
        with pytest.raises(AttributeError):
            p.action = "other"  # type: ignore[misc]


# ─── 12. Admin alert ────────────────────────────────────────────────────────


class TestAdminAlert:
    def test_admin_alert_for_escalation(self):
        p = orch.build_response_payload(
            memory=_mem(temp="hot"),
            signal={},
            decision={},
            offer={"should_notify_admin": True},
            policy={
                "policy_action": "escalate_admin",
                "allowed": True,
                "should_notify_admin": True,
            },
            source="user_message",
        )
        assert p.admin_alert_text is not None
        assert "agent alert" in p.admin_alert_text.lower()

    def test_no_admin_alert_for_reply(self):
        p = orch.build_response_payload(
            memory=_mem(),
            signal={},
            decision={},
            offer={},
            policy={"policy_action": "reply_now", "allowed": True},
            source="user_message",
        )
        assert p.admin_alert_text is None


# ─── 13. Source propagation ──────────────────────────────────────────────────


class TestSourcePropagation:
    def test_user_message_source(self):
        p = orch.run_pipeline(_mem(), text="test", source="user_message")
        assert p.source == "user_message"

    def test_followup_source(self):
        p = orch.run_pipeline(_mem(), source="followup_due")
        assert p.source == "followup_due"

    def test_journey_event_source(self):
        p = orch.run_pipeline(
            _mem(), source="journey_event", event_type="opened_catalog",
        )
        assert p.source == "journey_event"
