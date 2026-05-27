"""Unit tests for the AI Orchestrator / Control Center service."""
from __future__ import annotations

from core.services.ai_orchestrator_service import (
    AIOrchestratorState,
    _slugify_risk_flags,
    build_ai_orchestrator_state,
)


class TestBuildOrchestratorMinimal:
    """Tests with minimal / default signals."""

    def test_minimal_signals_returns_valid_state(self):
        result = build_ai_orchestrator_state()
        assert isinstance(result, AIOrchestratorState)
        assert result.priority in (
            "attack_now", "work_today", "nurture", "revive", "low_priority",
        )
        assert 0 <= result.priority_score <= 100
        assert 0.0 <= result.win_probability <= 1.0
        assert result.buyer_type is not None
        assert result.stage is not None
        assert result.trend is not None
        assert result.recommended_action
        assert result.recommended_operator_reply
        assert result.recommended_message_type in (
            "budget_option", "premium_design", "measurement_push",
            "direct_close", "soft_followup",
        )

    def test_sales_brain_pass_through(self):
        result = build_ai_orchestrator_state(score=50)
        assert result.sales_brain is not None
        assert result.sales_brain.win_probability == round(result.win_probability * 100)

    def test_brain_summary_has_items(self):
        result = build_ai_orchestrator_state(score=50, phone_captured=True)
        assert 3 <= len(result.brain_summary) <= 6

    def test_auto_close_fields_populated(self):
        result = build_ai_orchestrator_state()
        assert result.auto_close_reply
        assert 0.0 <= result.auto_close_confidence <= 1.0


class TestOrchestratorPriority:
    """Tests for priority assignment."""

    def test_hot_lead_high_priority(self):
        result = build_ai_orchestrator_state(
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
        assert result.win_probability >= 0.5
        assert result.revenue_best is not None

    def test_terminal_deal_low_priority(self):
        result = build_ai_orchestrator_state(
            score=80, phone_captured=True, lead_status="deal",
        )
        assert result.priority == "low_priority"
        assert result.priority_score == 0

    def test_terminal_lost_low_priority(self):
        result = build_ai_orchestrator_state(lead_status="lost")
        assert result.priority == "low_priority"


class TestOrchestratorRiskFlags:
    """Tests for risk flag slugification."""

    def test_delay_objection_slug(self):
        result = build_ai_orchestrator_state(score=40, last_objection="delay")
        assert "delay_signal" in result.risk_flags

    def test_angry_objection_slug(self):
        result = build_ai_orchestrator_state(score=40, last_objection="angry")
        assert "angry_objection" in result.risk_flags

    def test_flags_are_english_slugs(self):
        result = build_ai_orchestrator_state(
            score=45, last_objection="delay", follow_up_count=5,
            lead_temperature="cold",
        )
        for flag in result.risk_flags:
            assert flag.isascii(), f"Non-ASCII flag: {flag}"
            assert " " not in flag, f"Flag has spaces: {flag}"

    def test_max_six_flags(self):
        result = build_ai_orchestrator_state(
            score=45, last_objection="angry", follow_up_count=5,
            lead_temperature="cold",
        )
        assert len(result.risk_flags) <= 6


class TestSlugifyRiskFlags:
    """Unit tests for the slug mapper."""

    def test_known_flags(self):
        flags = [
            "Kechiktirish e'tirozi faol",
            "Qiziqish pasaymoqda",
            "Menejerga uzatish kerak",
        ]
        slugs = _slugify_risk_flags(flags)
        assert slugs == ["delay_signal", "cooling_trend", "escalation_needed"]

    def test_fu_stopped_flag(self):
        slugs = _slugify_risk_flags(["FU to'xtatilgan: some reason"])
        assert slugs == ["followup_stopped"]

    def test_unknown_flag_fallback(self):
        slugs = _slugify_risk_flags(["Something unknown"])
        assert slugs == ["something_unknown"]


class TestOrchestratorStrategy:
    """Tests for auto-closer strategy selection."""

    def test_price_objection_budget(self):
        result = build_ai_orchestrator_state(last_objection="expensive")
        assert result.recommended_message_type == "budget_option"

    def test_catalog_intent_premium(self):
        result = build_ai_orchestrator_state(intent="catalog")
        if result.buyer_type != "price_sensitive":
            assert result.recommended_message_type == "premium_design"


class TestOrchestratorRevenue:
    """Tests for revenue fields."""

    def test_no_area_no_revenue(self):
        result = build_ai_orchestrator_state(score=50)
        assert result.revenue_best is None
        assert result.revenue_range is None

    def test_area_has_revenue(self):
        result = build_ai_orchestrator_state(
            score=50, has_area=True, area_m2=20.0,
        )
        assert result.revenue_best is not None
        assert result.revenue_range is not None
        assert "UZS" in result.revenue_range


class TestBrainSummary:
    """Tests for the brain_summary builder."""

    def test_includes_score_line(self):
        result = build_ai_orchestrator_state(score=80, phone_captured=True)
        assert any("score" in s.lower() for s in result.brain_summary)

    def test_includes_objection_line(self):
        result = build_ai_orchestrator_state(
            score=40, last_objection="expensive",
        )
        assert any("objection" in s.lower() or "price" in s.lower()
                    for s in result.brain_summary)

    def test_includes_captured_data(self):
        result = build_ai_orchestrator_state(
            score=50, phone_captured=True, has_area=True,
        )
        assert any("shared" in s.lower() for s in result.brain_summary)

    def test_includes_trend(self):
        result = build_ai_orchestrator_state(score=50)
        assert any("trend" in s.lower() or "engagement" in s.lower() or
                    "warming" in s.lower() or "cooling" in s.lower() or
                    "stable" in s.lower() or "reactivated" in s.lower()
                    for s in result.brain_summary)

    def test_name_in_auto_reply(self):
        result = build_ai_orchestrator_state(name="Aziz", score=30)
        assert "Aziz" in result.auto_close_reply
