"""Tests for Step M — DynamicOfferService (rule-based offer engine)."""
from __future__ import annotations

import pytest

from core.schemas.dynamic_offer import DynamicOffer, OfferContext
from core.services.dynamic_offer_service import DynamicOfferService
from shared.constants.enums import (
    CustomerIntent,
    ObjectionType,
    OfferCTA,
    OfferPriority,
    OfferType,
    UrgencyLevel,
)

svc = DynamicOfferService


# ── Helpers ───────────────────────────────────────────────────────────────────


def _mem(
    *,
    intent: str = "unclear",
    objection: str | None = None,
    urgency: str = "low",
    lead_score: int = 0,
    temp: str = "cold",
    area: float | None = None,
    phone: bool = False,
    followup_enabled: bool = True,
    state: str = "new_visitor",
) -> dict:
    md: dict = {"last_intent": intent, "urgency": urgency, "lead_score": lead_score}
    if objection:
        md["objection_type"] = objection
    if area:
        md["area_m2"] = area
    md["customer_state"] = state
    m: dict = {
        "lead_temperature": temp,
        "followup_enabled": followup_enabled,
        "memory_data": md,
    }
    if area:
        m["area_m2"] = area
    if phone:
        m["phone_masked"] = "+998**…**00"
    return m


def _sig(**kw: object) -> dict:
    return dict(kw)


# ─── 1. wants_price + no area → PRICE_CALCULATION + ASK_AREA ────────────────


class TestPriceCalculation:
    def test_wants_price_no_area(self):
        offer = svc.choose_offer(_mem(intent="wants_price"))
        assert offer.offer_type == OfferType.PRICE_CALCULATION.value
        assert offer.cta == OfferCTA.ASK_AREA.value

    def test_wants_price_with_area(self):
        offer = svc.choose_offer(_mem(intent="wants_price", area=20.0))
        assert offer.offer_type == OfferType.PRICE_CALCULATION.value
        assert offer.cta == OfferCTA.ASK_DESIGN_TYPE.value

    def test_price_no_area_hint(self):
        offer = svc.choose_offer(_mem(intent="wants_price"))
        assert "kvadrat" in offer.message_hint.lower()

    def test_price_with_area_hint(self):
        offer = svc.choose_offer(_mem(intent="wants_price", area=20.0))
        assert "turini" in offer.message_hint.lower()


# ─── 2. Objection-based offers ──────────────────────────────────────────────


class TestObjectionOffers:
    def test_price_objection_cheaper_option(self):
        offer = svc.choose_offer(_mem(objection="price", temp="warm"))
        assert offer.offer_type == OfferType.CHEAPER_OPTION.value

    def test_price_objection_cta(self):
        offer = svc.choose_offer(_mem(objection="price", temp="warm"))
        assert offer.cta == OfferCTA.OPEN_PRICE_CALCULATOR.value

    def test_price_objection_hint_no_cheapest(self):
        offer = svc.choose_offer(_mem(objection="price", temp="warm"))
        assert "eng arzon" not in offer.message_hint.lower()

    def test_trust_objection_warranty(self):
        offer = svc.choose_offer(_mem(objection="trust", temp="warm"))
        assert offer.offer_type == OfferType.WARRANTY_TRUST.value

    def test_trust_objection_cta(self):
        offer = svc.choose_offer(_mem(objection="trust", temp="warm"))
        assert offer.cta == OfferCTA.SHOW_CATALOG.value

    def test_not_ready_design_help(self):
        offer = svc.choose_offer(_mem(objection="not_ready", temp="warm"))
        assert offer.offer_type == OfferType.DESIGN_HELP.value

    def test_not_ready_cta(self):
        offer = svc.choose_offer(_mem(objection="not_ready", temp="warm"))
        assert offer.cta == OfferCTA.SHOW_CATALOG.value

    def test_comparing_social_proof(self):
        offer = svc.choose_offer(_mem(objection="comparing", temp="warm"))
        assert offer.offer_type == OfferType.PORTFOLIO_SOCIAL_PROOF.value

    def test_family_decision_design_help(self):
        offer = svc.choose_offer(_mem(objection="spouse_family_decision", temp="warm"))
        assert offer.offer_type == OfferType.DESIGN_HELP.value


# ─── 3. Urgency-based offers ────────────────────────────────────────────────


class TestUrgencyOffers:
    def test_high_urgency_fast_install(self):
        offer = svc.choose_offer(_mem(urgency="high", temp="warm"))
        assert offer.offer_type == OfferType.FAST_INSTALLATION.value
        assert offer.cta == OfferCTA.CONTACT_OPERATOR.value

    def test_high_urgency_priority_urgent(self):
        offer = svc.choose_offer(_mem(urgency="high", temp="warm"))
        assert offer.priority == OfferPriority.URGENT.value

    def test_high_urgency_hint_no_same_day_promise(self):
        offer = svc.choose_offer(_mem(urgency="high", temp="warm"))
        assert "bugun qilamiz" not in offer.message_hint.lower()


# ─── 4. Intent-based offers ─────────────────────────────────────────────────


class TestIntentOffers:
    def test_wants_operator(self):
        offer = svc.choose_offer(_mem(intent="wants_operator", temp="warm"))
        assert offer.offer_type == OfferType.OPERATOR_CONSULTATION.value
        assert offer.cta == OfferCTA.CONTACT_OPERATOR.value

    def test_wants_order(self):
        offer = svc.choose_offer(_mem(intent="wants_order", temp="warm"))
        assert offer.offer_type == OfferType.ORDER_CONTINUE.value
        assert offer.cta == OfferCTA.CONTINUE_ORDER.value

    def test_wants_measurement(self):
        offer = svc.choose_offer(_mem(intent="wants_measurement", temp="warm"))
        assert offer.offer_type == OfferType.MEASUREMENT_VISIT.value
        assert offer.cta == OfferCTA.CONTACT_OPERATOR.value

    def test_wants_catalog(self):
        offer = svc.choose_offer(_mem(intent="wants_catalog", temp="warm"))
        assert offer.offer_type == OfferType.DESIGN_HELP.value
        assert offer.cta == OfferCTA.SHOW_CATALOG.value

    def test_wants_discount(self):
        offer = svc.choose_offer(_mem(intent="wants_discount", temp="warm"))
        assert offer.offer_type == OfferType.DISCOUNT_DISCUSSION.value
        assert offer.cta == OfferCTA.CONTACT_OPERATOR.value

    def test_discount_hint_operator(self):
        offer = svc.choose_offer(_mem(intent="wants_discount", temp="warm"))
        assert "operator" in offer.message_hint.lower()


# ─── 5. Score-based offers ──────────────────────────────────────────────────


class TestScoreOffers:
    def test_hot_score_no_phone_callback(self):
        offer = svc.choose_offer(_mem(lead_score=75, temp="hot"))
        assert offer.offer_type == OfferType.CALLBACK_REQUEST.value
        assert offer.cta == OfferCTA.REQUEST_PHONE.value

    def test_hot_score_with_phone_operator(self):
        offer = svc.choose_offer(_mem(lead_score=75, temp="hot", phone=True))
        assert offer.offer_type == OfferType.OPERATOR_CONSULTATION.value

    def test_hot_score_notify_admin(self):
        offer = svc.choose_offer(_mem(lead_score=75, temp="hot"))
        assert offer.should_notify_admin is True

    def test_hot_score_priority_high(self):
        offer = svc.choose_offer(_mem(lead_score=75, temp="hot"))
        assert offer.priority == OfferPriority.HIGH.value


# ─── 6. Image-based offers ──────────────────────────────────────────────────


class TestImageOffers:
    def test_image_sent_design_help(self):
        offer = svc.choose_offer(
            _mem(temp="warm"),
            recent_events=[{"event_type": "image_sent"}],
        )
        assert offer.offer_type == OfferType.DESIGN_HELP.value

    def test_image_sent_notify_admin(self):
        offer = svc.choose_offer(
            _mem(temp="warm"),
            recent_events=[{"event_type": "image_sent"}],
        )
        assert offer.should_notify_admin is True


# ─── 7. Cold + unclear → NO_OFFER ───────────────────────────────────────────


class TestColdUnclear:
    def test_cold_unclear_no_offer(self):
        offer = svc.choose_offer(_mem())
        assert offer.offer_type == OfferType.NO_OFFER.value

    def test_cold_unclear_wait(self):
        offer = svc.choose_offer(_mem())
        assert offer.cta == OfferCTA.WAIT.value


# ─── 8. Safety / terminal states ────────────────────────────────────────────


class TestSafety:
    def test_followup_disabled_no_offer(self):
        offer = svc.choose_offer(_mem(followup_enabled=False))
        assert offer.offer_type == OfferType.NO_OFFER.value
        assert "followup_disabled" in offer.safety_flags

    def test_stopped_state_no_offer(self):
        offer = svc.choose_offer(_mem(state="stopped"))
        assert offer.offer_type == OfferType.NO_OFFER.value
        assert "terminal_state" in offer.safety_flags

    def test_lost_state_no_offer(self):
        offer = svc.choose_offer(_mem(state="lost"))
        assert offer.offer_type == OfferType.NO_OFFER.value

    def test_closed_state_no_offer(self):
        offer = svc.choose_offer(_mem(state="closed"))
        assert offer.offer_type == OfferType.NO_OFFER.value

    def test_stop_request_intent(self):
        offer = svc.choose_offer(_mem(intent="stop_request"))
        assert offer.offer_type == OfferType.NO_OFFER.value
        assert offer.cta == OfferCTA.STOP.value
        assert "stop_request" in offer.safety_flags

    def test_cold_lead_no_admin_notify(self):
        offer = svc.choose_offer(_mem(lead_score=75, temp="cold"))
        assert offer.should_notify_admin is False

    def test_warm_lead_admin_notify(self):
        offer = svc.choose_offer(_mem(lead_score=75, temp="warm"))
        assert offer.should_notify_admin is True


# ─── 9. Priority calculation ────────────────────────────────────────────────


class TestPriority:
    def test_urgent_for_high_urgency(self):
        ctx = OfferContext(urgency="high")
        assert svc.calculate_offer_priority("any", ctx) == "urgent"

    def test_high_for_hot_temp(self):
        ctx = OfferContext(lead_temperature="hot")
        assert svc.calculate_offer_priority("any", ctx) == "high"

    def test_high_for_high_score(self):
        ctx = OfferContext(lead_score=75)
        assert svc.calculate_offer_priority("any", ctx) == "high"

    def test_medium_for_warm_temp(self):
        ctx = OfferContext(lead_temperature="warm")
        assert svc.calculate_offer_priority("any", ctx) == "medium"

    def test_low_for_cold(self):
        ctx = OfferContext(lead_temperature="cold")
        assert svc.calculate_offer_priority("any", ctx) == "low"


# ─── 10. Validation ─────────────────────────────────────────────────────────


class TestValidation:
    def test_valid_offer(self):
        offer = svc.choose_offer(_mem(intent="wants_price"))
        ok, reason = svc.validate_offer(offer)
        assert ok is True

    def test_reject_eng_arzon_hint(self):
        offer = DynamicOffer(
            offer_type="test", cta="test", priority="low",
            confidence_score=50, reason="test",
            message_hint="Eng arzon variant",
        )
        ok, reason = svc.validate_offer(offer)
        assert ok is False
        assert reason == "unsafe_claim_cheapest"

    def test_reject_bugun_qilamiz_hint(self):
        offer = DynamicOffer(
            offer_type="test", cta="test", priority="low",
            confidence_score=50, reason="test",
            message_hint="Bugun qilamiz",
        )
        ok, reason = svc.validate_offer(offer)
        assert ok is False
        assert reason == "unsafe_promise_today"


# ─── 11. Memory storage ─────────────────────────────────────────────────────


class TestMemoryStorage:
    def test_store_offer(self):
        offer = svc.choose_offer(_mem(intent="wants_price"))
        md = svc.store_offer_to_memory({}, offer)
        stored = md["last_dynamic_offer"]
        assert stored["offer_type"] == offer.offer_type
        assert stored["cta"] == offer.cta
        assert "created_at" in stored

    def test_store_preserves_existing(self):
        offer = svc.choose_offer(_mem(intent="wants_price"))
        md = svc.store_offer_to_memory({"existing_key": 42}, offer)
        assert md["existing_key"] == 42
        assert "last_dynamic_offer" in md


# ─── 12. Buttons ────────────────────────────────────────────────────────────


class TestButtons:
    def test_ask_area_buttons(self):
        btns = svc.build_recommended_buttons(OfferCTA.ASK_AREA.value)
        assert len(btns) >= 1

    def test_request_phone_buttons(self):
        btns = svc.build_recommended_buttons(OfferCTA.REQUEST_PHONE.value)
        assert len(btns) >= 1

    def test_wait_no_buttons(self):
        btns = svc.build_recommended_buttons(OfferCTA.WAIT.value)
        assert btns == []


# ─── 13. Confidence ─────────────────────────────────────────────────────────


class TestConfidence:
    def test_high_confidence_with_many_signals(self):
        offer = svc.choose_offer(_mem(
            intent="wants_price", objection="price",
            urgency="high", area=20.0, lead_score=80,
        ))
        assert offer.confidence_score >= 70

    def test_low_confidence_unclear(self):
        offer = svc.choose_offer(_mem(temp="warm"))
        assert offer.confidence_score < 60


# ─── 14. Decision engine integration ────────────────────────────────────────


class TestDecisionEngineIntegration:
    def test_evaluate_with_offer_returns_tuple(self):
        from core.services.agent_decision_engine import evaluate_with_offer
        memory = {"followup_enabled": True, "memory_data": {}}
        decision, offer = evaluate_with_offer(memory, [])
        assert decision is not None
        # offer is None because feature flag is off (default)
        assert offer is None

    def test_evaluate_still_works(self):
        from core.services.agent_decision_engine import evaluate
        memory = {"followup_enabled": True, "memory_data": {}}
        decision = evaluate(memory, [])
        assert decision.customer_state is not None


# ─── 15. AI composer integration ────────────────────────────────────────────


class TestComposerIntegration:
    def test_build_prompt_with_offer_hint(self):
        from core.services.ai_message_composer_service import _build_user_prompt
        md = {
            "full_name": "Aziz",
            "last_dynamic_offer": {
                "message_hint": "Arzonroq variant bor.",
            },
        }
        prompt = _build_user_prompt("catalog", md)
        assert "arzonroq variant" in prompt.lower()

    def test_build_prompt_without_offer(self):
        from core.services.ai_message_composer_service import _build_user_prompt
        md = {"full_name": "Aziz"}
        prompt = _build_user_prompt("catalog", md)
        assert "taklif" not in prompt.lower()

    def test_build_prompt_offer_warns_no_prices(self):
        from core.services.ai_message_composer_service import _build_user_prompt
        md = {
            "last_dynamic_offer": {
                "message_hint": "Some hint",
            },
        }
        prompt = _build_user_prompt("price", md)
        assert "o'ylab topma" in prompt.lower()


# ─── 16. Schema immutability ────────────────────────────────────────────────


class TestSchemaImmutability:
    def test_offer_frozen(self):
        offer = svc.choose_offer(_mem(intent="wants_price"))
        with pytest.raises(AttributeError):
            offer.offer_type = "other"  # type: ignore[misc]

    def test_context_frozen(self):
        ctx = OfferContext(intent="wants_price")
        with pytest.raises(AttributeError):
            ctx.intent = "other"  # type: ignore[misc]


# ─── 17. Warm lead offers ───────────────────────────────────────────────────


class TestWarmLeadOffers:
    def test_warm_with_area_price_calc(self):
        offer = svc.choose_offer(_mem(temp="warm", area=20.0))
        assert offer.offer_type == OfferType.PRICE_CALCULATION.value

    def test_warm_no_area_design_help(self):
        offer = svc.choose_offer(_mem(temp="warm"))
        assert offer.offer_type == OfferType.DESIGN_HELP.value

    def test_warm_medium_priority(self):
        offer = svc.choose_offer(_mem(temp="warm", intent="wants_catalog"))
        assert offer.priority == OfferPriority.MEDIUM.value


# ─── 18. Signal passthrough ─────────────────────────────────────────────────


class TestSignalPassthrough:
    def test_signal_intent_overrides_memory(self):
        offer = svc.choose_offer(
            _mem(temp="warm"),
            lead_signal={"intent": "wants_order"},
        )
        assert offer.offer_type == OfferType.ORDER_CONTINUE.value

    def test_signal_objection_used(self):
        offer = svc.choose_offer(
            _mem(temp="warm"),
            lead_signal={"objection_type": "trust"},
        )
        assert offer.offer_type == OfferType.WARRANTY_TRUST.value
