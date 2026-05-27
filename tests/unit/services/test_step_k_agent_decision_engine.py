"""Step K tests: agent decision engine — state classification, action, scoring, safety."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.services.agent_decision_engine import (
    calculate_priority_score,
    classify_customer_state,
    evaluate,
)
from shared.constants.enums import (
    AgentActionType,
    AgentCustomerState,
    JourneyEventType,
)

E = JourneyEventType
S = AgentCustomerState
A = AgentActionType


def _events(*types: JourneyEventType) -> list[dict[str, object]]:
    return [{"event_type": t.value} for t in types]


def _et_set(*types: JourneyEventType) -> frozenset[str]:
    return frozenset(t.value for t in types)


# ── State classification ──────────────────────────────────────────────────


class TestClassifyState:
    def test_started_only_new_visitor(self) -> None:
        s = classify_customer_state({}, _et_set(E.STARTED_BOT))
        assert s == S.NEW_VISITOR

    def test_opened_catalog(self) -> None:
        s = classify_customer_state({}, _et_set(E.STARTED_BOT, E.OPENED_CATALOG))
        assert s == S.BROWSING_CATALOG

    def test_viewed_catalog_item(self) -> None:
        s = classify_customer_state(
            {"interested_designs": ["gulli"]},
            _et_set(E.VIEWED_CATALOG_ITEM),
        )
        assert s == S.DESIGN_INTERESTED

    def test_used_calculator(self) -> None:
        s = classify_customer_state({}, _et_set(E.USED_PRICE_CALCULATOR))
        assert s == S.PRICE_CHECKING

    def test_price_calculated(self) -> None:
        s = classify_customer_state({}, _et_set(E.PRICE_CALCULATED))
        assert s == S.PRICE_CONSIDERING

    def test_clicked_order(self) -> None:
        s = classify_customer_state({}, _et_set(E.CLICKED_ORDER))
        assert s == S.ORDER_INTENT

    def test_order_started_no_phone(self) -> None:
        s = classify_customer_state({}, _et_set(E.ORDER_FORM_STARTED))
        assert s == S.ORDER_ABANDONED

    def test_phone_shared(self) -> None:
        s = classify_customer_state({}, _et_set(E.PHONE_SHARED))
        assert s == S.PHONE_SHARED_HOT

    def test_operator_requested(self) -> None:
        s = classify_customer_state({}, _et_set(E.OPERATOR_REQUESTED))
        assert s == S.OPERATOR_HANDOFF

    def test_followup_disabled_stopped(self) -> None:
        s = classify_customer_state({"followup_enabled": False}, frozenset())
        assert s == S.STOPPED

    def test_deal_closed(self) -> None:
        s = classify_customer_state(
            {"followup_enabled": False, "stop_reason": "deal_closed"},
            frozenset(),
        )
        assert s == S.CLOSED

    def test_lost_lead(self) -> None:
        s = classify_customer_state(
            {"followup_enabled": False, "stop_reason": "lost_lead"},
            frozenset(),
        )
        assert s == S.LOST

    def test_price_objection(self) -> None:
        s = classify_customer_state(
            {"objection_type": "price"},
            _et_set(E.STARTED_BOT),
        )
        assert s == S.NEGOTIATING_PRICE

    def test_inactive_warm(self) -> None:
        old = datetime.now(UTC) - timedelta(hours=30)
        s = classify_customer_state(
            {"lead_temperature": "warm", "last_event_at": old},
            frozenset(),
        )
        assert s == S.INACTIVE_WARM

    def test_inactive_cold(self) -> None:
        old = datetime.now(UTC) - timedelta(hours=80)
        s = classify_customer_state(
            {"lead_temperature": "cold", "last_event_at": old},
            frozenset(),
        )
        assert s == S.INACTIVE_COLD


# ── Action selection ──────────────────────────────────────────────────────


class TestActionSelection:
    def test_new_visitor_wait(self) -> None:
        d = evaluate({}, _events(E.STARTED_BOT))
        assert d.action_type == A.WAIT.value

    def test_catalog_followup(self) -> None:
        d = evaluate({}, _events(E.OPENED_CATALOG))
        assert d.action_type == A.SEND_CATALOG_FOLLOWUP.value

    def test_design_suggest_calculator(self) -> None:
        d = evaluate(
            {"interested_designs": ["gulli"]},
            _events(E.VIEWED_CATALOG_ITEM),
        )
        assert d.action_type == A.SUGGEST_PRICE_CALCULATOR.value

    def test_price_checking_request_area(self) -> None:
        d = evaluate({}, _events(E.USED_PRICE_CALCULATOR))
        assert d.action_type == A.REQUEST_AREA.value

    def test_price_considering_followup(self) -> None:
        d = evaluate({}, _events(E.PRICE_CALCULATED))
        assert d.action_type == A.SEND_PRICE_FOLLOWUP.value

    def test_order_abandoned_followup(self) -> None:
        d = evaluate({}, _events(E.ORDER_FORM_STARTED))
        assert d.action_type == A.SEND_ORDER_FOLLOWUP.value

    def test_phone_shared_hot(self) -> None:
        d = evaluate(
            {
                "full_name": "Ali",
                "phone_masked": "+998**…**67",
                "area_m2": 20,
                "estimated_price": 5_000_000,
                "district": "Qarshi",
                "interested_designs": ["gulli"],
            },
            _events(E.STARTED_BOT, E.PRICE_CALCULATED, E.PHONE_SHARED),
        )
        assert d.action_type == A.MARK_HOT_LEAD.value

    def test_operator_disable(self) -> None:
        d = evaluate({}, _events(E.OPERATOR_REQUESTED))
        assert d.action_type == A.DISABLE_FOLLOWUP.value

    def test_negotiating_suggest_operator(self) -> None:
        d = evaluate({"objection_type": "price"}, _events(E.STARTED_BOT))
        assert d.action_type == A.SUGGEST_OPERATOR.value


# ── Priority and confidence scoring ───────────────────────────────────────


class TestScoring:
    def test_priority_in_range(self) -> None:
        d = evaluate({}, _events(E.STARTED_BOT))
        assert 0 <= d.priority_score <= 100

    def test_priority_with_phone_higher(self) -> None:
        d1 = evaluate({}, _events(E.PRICE_CALCULATED))
        d2 = evaluate(
            {"phone_masked": "+998**…**67", "estimated_price": 5_000_000},
            _events(E.PRICE_CALCULATED),
        )
        assert d2.priority_score > d1.priority_score

    def test_confidence_in_range(self) -> None:
        d = evaluate({}, _events(E.STARTED_BOT))
        assert 0 <= d.confidence_score <= 100

    def test_confidence_more_signals_higher(self) -> None:
        d1 = evaluate({}, _events(E.STARTED_BOT))
        d2 = evaluate(
            {
                "full_name": "Ali",
                "area_m2": 20.0,
                "estimated_price": 5_000_000,
                "phone_masked": "+998**…**67",
                "district": "Qarshi",
                "interested_designs": ["gulli"],
            },
            _events(E.STARTED_BOT, E.PRICE_CALCULATED, E.PHONE_SHARED),
        )
        assert d2.confidence_score > d1.confidence_score

    def test_priority_capped_at_100(self) -> None:
        score = calculate_priority_score(
            {
                "estimated_price": 9_000_000,
                "phone_masked": "+998**…**67",
                "area_m2": 50.0,
                "interested_designs": ["a", "b", "c"],
                "lead_temperature": "hot",
            },
            _et_set(E.PHONE_SHARED, E.PRICE_CALCULATED),
            base_priority=90,
        )
        assert score == 100


# ── Safety rules ──────────────────────────────────────────────────────────


class TestSafety:
    def test_stopped_always_wait(self) -> None:
        d = evaluate({"followup_enabled": False, "stop_reason": "user_opted_out"}, [])
        assert d.action_type == A.WAIT.value
        assert "followup_disabled" in d.safety_flags

    def test_lost_always_wait(self) -> None:
        d = evaluate({"followup_enabled": False, "stop_reason": "lost_lead"}, [])
        assert d.action_type == A.WAIT.value

    def test_lifetime_cap_flagged(self) -> None:
        d = evaluate({"followup_count": 5}, _events(E.OPENED_CATALOG))
        assert "lifetime_cap_reached" in d.safety_flags

    def test_cold_no_admin_escalation(self) -> None:
        old = datetime.now(UTC) - timedelta(hours=30)
        d = evaluate(
            {"lead_temperature": "cold", "last_event_at": old},
            [],
        )
        assert d.action_type == A.WAIT.value
        assert d.admin_escalation_needed is False

    def test_low_confidence_downgrades_high_impact(self) -> None:
        d = evaluate({}, _events(E.PHONE_SHARED))
        if d.confidence_score < 60:
            assert d.action_type == A.WAIT.value
            assert "low_confidence_downgrade" in d.safety_flags


# ── Follow-up scheduling decision ────────────────────────────────────────


class TestFollowupDecision:
    def test_catalog_should_schedule(self) -> None:
        d = evaluate({}, _events(E.OPENED_CATALOG))
        assert d.should_schedule_followup is True
        assert d.followup_type == "catalog"
        assert d.delay_minutes == 10

    def test_price_should_schedule(self) -> None:
        d = evaluate({}, _events(E.PRICE_CALCULATED))
        assert d.should_schedule_followup is True
        assert d.followup_type == "price"

    def test_order_abandoned_should_schedule(self) -> None:
        d = evaluate({}, _events(E.ORDER_FORM_STARTED))
        assert d.should_schedule_followup is True
        assert d.followup_type == "abandoned_order"

    def test_wait_no_schedule(self) -> None:
        d = evaluate({}, _events(E.STARTED_BOT))
        assert d.should_schedule_followup is False
        assert d.followup_type is None

    def test_stopped_no_schedule(self) -> None:
        d = evaluate({"followup_enabled": False}, _events(E.OPENED_CATALOG))
        assert d.should_schedule_followup is False


# ── AgentDecision schema ─────────────────────────────────────────────────


class TestAgentDecisionSchema:
    def test_frozen_dataclass(self) -> None:
        d = evaluate({}, _events(E.STARTED_BOT))
        with pytest.raises(AttributeError):
            d.priority_score = 999  # type: ignore[misc]

    def test_all_fields_present(self) -> None:
        d = evaluate({}, _events(E.STARTED_BOT))
        assert hasattr(d, "customer_state")
        assert hasattr(d, "action_type")
        assert hasattr(d, "priority_score")
        assert hasattr(d, "confidence_score")
        assert hasattr(d, "reason")
        assert hasattr(d, "lead_temperature")
        assert hasattr(d, "safety_flags")
        assert hasattr(d, "metadata")


# ── Feature flags ────────────────────────────────────────────────────────


class TestDecisionFlags:
    def test_flag_default_false(self) -> None:
        from shared.config.settings import BusinessSettings
        s = BusinessSettings()
        assert s.agent_decision_engine_enabled is False

    def test_log_only_default_true(self) -> None:
        from shared.config.settings import BusinessSettings
        s = BusinessSettings()
        assert s.agent_decision_log_only is True

    def test_min_confidence_default_60(self) -> None:
        from shared.config.settings import BusinessSettings
        s = BusinessSettings()
        assert s.agent_decision_min_confidence == 60


# ── No regression ────────────────────────────────────────────────────────


class TestNoRegression:
    def test_followup_service_build_message_unchanged(self) -> None:
        from core.services.followup_scheduler_service import FollowupSchedulerService
        for fu_type in ("catalog", "price", "abandoned_order"):
            text, buttons = FollowupSchedulerService.build_message(fu_type)
            assert text
            assert len(buttons) == 3

    def test_stop_signal_still_works(self) -> None:
        from core.services.followup_scheduler_service import FollowupSchedulerService
        assert FollowupSchedulerService.is_stop_signal("kerak emas") is True
        assert FollowupSchedulerService.is_stop_signal("Salom") is False
