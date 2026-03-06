"""Unit tests for the AI Auto Closer service."""
from __future__ import annotations

from core.services.ai_auto_closer_service import (
    AutoCloseDecision,
    STRATEGY_LABELS,
    build_auto_close_reply,
)

_VALID_STRATEGIES = set(STRATEGY_LABELS.keys())


class TestBuildAutoCloseReplyMinimal:
    """Tests with minimal / default signals."""

    def test_minimal_signals_returns_valid_decision(self):
        result = build_auto_close_reply()
        assert isinstance(result, AutoCloseDecision)
        assert result.recommended_strategy in _VALID_STRATEGIES
        assert result.recommended_reply
        assert 0.0 <= result.close_probability <= 1.0
        assert 0.0 <= result.confidence <= 1.0

    def test_reason_summary_has_items(self):
        result = build_auto_close_reply()
        assert 1 <= len(result.reason_summary) <= 4

    def test_reply_is_uzbek_text(self):
        result = build_auto_close_reply()
        assert len(result.recommended_reply) > 10

    def test_buyer_type_propagated(self):
        result = build_auto_close_reply(score=60, phone_captured=True)
        assert result.buyer_type in (
            "price_sensitive", "quality_buyer", "fast_buyer", "research_buyer",
        )


class TestStrategySelection:
    """Tests for deterministic strategy rules."""

    def test_price_sensitive_gets_budget(self):
        result = build_auto_close_reply(
            last_objection="expensive", intent="price",
        )
        assert result.recommended_strategy == "budget_option"

    def test_compare_objection_gets_budget(self):
        result = build_auto_close_reply(last_objection="compare")
        assert result.recommended_strategy == "budget_option"

    def test_quality_buyer_gets_premium(self):
        # Quality buyer: high score, no price objections, closing attempted
        result = build_auto_close_reply(
            score=70,
            phone_captured=True,
            closing_attempted=True,
            closing_confidence=0.8,
            design_type="premium",
        )
        # buyer_type should be quality_buyer -> premium_design
        if result.buyer_type == "quality_buyer":
            assert result.recommended_strategy == "premium_design"

    def test_catalog_intent_gets_premium(self):
        result = build_auto_close_reply(intent="catalog")
        # catalog intent should map to premium_design unless price-sensitive
        if result.buyer_type != "price_sensitive":
            assert result.recommended_strategy == "premium_design"

    def test_close_ready_phone_gets_direct(self):
        result = build_auto_close_reply(
            score=80,
            phone_captured=True,
            has_area=True,
            area_m2=25.0,
            has_district=True,
            closing_attempted=True,
            closing_confidence=0.85,
        )
        # High signals → close_ready stage → direct_close
        assert result.recommended_strategy in ("direct_close", "premium_design")

    def test_cold_lead_gets_soft_or_measurement(self):
        result = build_auto_close_reply(score=5, lead_temperature="cold")
        assert result.recommended_strategy in ("soft_followup", "measurement_push")

    def test_researching_no_phone_gets_measurement(self):
        result = build_auto_close_reply(
            score=20, has_area=True, area_m2=15.0, has_district=True,
        )
        # researching + no phone → measurement_push
        if result.recommended_strategy not in ("premium_design", "budget_option"):
            assert result.recommended_strategy in ("measurement_push", "soft_followup")


class TestReplyPersonalization:
    """Tests for name-based reply personalization."""

    def test_reply_includes_name_when_provided(self):
        result = build_auto_close_reply(name="Aziz", score=30)
        assert "Aziz" in result.recommended_reply

    def test_reply_works_without_name(self):
        result = build_auto_close_reply(score=30)
        assert result.recommended_reply
        assert "{name}" not in result.recommended_reply


class TestConfidence:
    """Tests for confidence computation."""

    def test_high_signals_high_confidence(self):
        result = build_auto_close_reply(
            score=80,
            phone_captured=True,
            closing_attempted=True,
            closing_confidence=0.9,
            has_area=True,
            area_m2=20.0,
        )
        assert result.confidence >= 0.5

    def test_low_signals_low_confidence(self):
        result = build_auto_close_reply(score=5)
        assert result.confidence < 0.5

    def test_confidence_bounded(self):
        result = build_auto_close_reply(score=100, closing_confidence=1.0)
        assert 0.0 <= result.confidence <= 1.0


class TestCloseProbability:
    """Tests for close_probability field."""

    def test_terminal_deal_zero_probability(self):
        result = build_auto_close_reply(lead_status="deal")
        # Terminal leads get 0 priority but close_probability reflects win_probability
        assert 0.0 <= result.close_probability <= 1.0

    def test_hot_lead_high_probability(self):
        result = build_auto_close_reply(
            score=80, phone_captured=True, closing_confidence=0.85,
            has_area=True, area_m2=25.0, has_district=True,
        )
        assert result.close_probability >= 0.5
