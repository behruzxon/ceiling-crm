"""Unit tests for the AI Sales Brain orchestration service."""

from __future__ import annotations

from core.services.ai_sales_brain_service import SalesBrainDecision, build_sales_brain


class TestBuildSalesBrainMinimal:
    """Tests with minimal / default signals."""

    def test_minimal_signals_returns_valid_decision(self):
        result = build_sales_brain()
        assert isinstance(result, SalesBrainDecision)
        assert result.priority in (
            "attack_now",
            "work_today",
            "nurture",
            "revive",
            "low_priority",
        )
        assert 0 <= result.priority_score <= 100
        assert 0 <= result.win_probability <= 100
        assert result.buyer_type is not None
        assert result.stage is not None
        assert result.trend is not None
        assert result.recommended_action
        assert result.recommended_operator_reply

    def test_all_sub_results_populated(self):
        result = build_sales_brain(score=50, phone_captured=True, has_area=True, area_m2=20.0)
        assert result.deal_probability is not None
        assert result.buyer_profile is not None
        assert result.revenue_estimate is not None
        assert result.negotiation_result is not None
        assert result.conversation_graph is not None
        assert result.followup_decision is not None
        assert result.radar_result is not None
        assert result.operator_assist is not None

    def test_reason_summary_non_empty(self):
        result = build_sales_brain(score=50, phone_captured=True)
        assert len(result.reason_summary) > 10


class TestBuildSalesBrainPriority:
    """Tests for priority / radar bucket assignment."""

    def test_hot_lead_gets_high_priority(self):
        result = build_sales_brain(
            score=80,
            phone_captured=True,
            has_area=True,
            area_m2=25.0,
            has_district=True,
            closing_attempted=True,
            closing_confidence=0.85,
            intent="price",
        )
        assert result.priority in ("attack_now", "work_today")
        assert result.win_probability >= 50
        assert result.revenue_best is not None
        assert result.revenue_range is not None

    def test_cold_lead_gets_low_priority(self):
        result = build_sales_brain(score=5, lead_temperature="cold")
        assert result.priority in ("low_priority", "nurture", "revive")
        assert result.win_probability < 30

    def test_terminal_status_deal(self):
        result = build_sales_brain(score=80, phone_captured=True, lead_status="deal")
        assert result.priority == "low_priority"
        assert result.priority_score == 0

    def test_terminal_status_lost(self):
        result = build_sales_brain(lead_status="lost")
        assert result.priority == "low_priority"
        assert result.priority_score == 0


class TestBuildSalesBrainRiskFlags:
    """Tests for risk flag assembly."""

    def test_delay_objection_adds_risk_flag(self):
        result = build_sales_brain(score=40, last_objection="delay")
        assert any("echiktirish" in f for f in result.risk_flags)

    def test_angry_objection_adds_risk_flag(self):
        result = build_sales_brain(score=40, last_objection="angry")
        assert any("orozilik" in f for f in result.risk_flags)

    def test_max_six_flags(self):
        result = build_sales_brain(
            score=45,
            last_objection="angry",
            follow_up_count=5,
            lead_temperature="cold",
        )
        assert len(result.risk_flags) <= 6

    def test_clean_lead_few_flags(self):
        result = build_sales_brain(
            score=70,
            phone_captured=True,
            closing_attempted=True,
            closing_confidence=0.8,
        )
        assert len(result.risk_flags) <= 2


class TestBuildSalesBrainRevenue:
    """Tests for revenue propagation."""

    def test_revenue_none_when_no_area(self):
        result = build_sales_brain(score=50, phone_captured=True)
        assert result.revenue_best is None
        assert result.revenue_range is None

    def test_revenue_present_when_area_given(self):
        result = build_sales_brain(score=50, area_m2=20.0, has_area=True)
        assert result.revenue_best is not None
        assert result.revenue_range is not None
        assert "UZS" in result.revenue_range


class TestBuildSalesBrainFollowUp:
    """Tests for follow-up propagation."""

    def test_followup_cap_reached(self):
        result = build_sales_brain(
            score=5,
            lead_temperature="cold",
            follow_up_count=5,
        )
        # Follow-up cap reached -> no message type recommended
        assert result.recommended_message_type is None


class TestBuildSalesBrainBuyerType:
    """Tests for buyer type propagation."""

    def test_buyer_type_propagated(self):
        result = build_sales_brain(
            score=60,
            phone_captured=True,
            closing_attempted=True,
        )
        assert result.buyer_type in (
            "price_sensitive",
            "quality_buyer",
            "fast_buyer",
            "research_buyer",
        )
        assert 0.0 <= result.buyer_confidence <= 1.0


class TestBuildSalesBrainOperatorReply:
    """Tests for operator reply selection."""

    def test_reply_always_non_empty(self):
        result = build_sales_brain(score=30)
        assert result.recommended_operator_reply
        assert len(result.recommended_operator_reply) > 5

    def test_price_sensitive_lead_reply(self):
        result = build_sales_brain(last_objection="expensive", intent="price")
        assert result.recommended_operator_reply
