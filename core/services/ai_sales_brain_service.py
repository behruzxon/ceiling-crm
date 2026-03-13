"""
core.services.ai_sales_brain_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Central orchestration layer that combines all 8 intelligence services
into a single unified sales decision.

Pure function — no I/O, no DB, no Redis. Fully deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.services.conversation_memory_graph_service import (
    STAGE_LABELS,
    TREND_LABELS,
    analyze_conversation_graph,
)
from core.services.deal_radar_service import (
    BUCKET_LABELS,
    rank_lead_for_radar,
)
from core.services.followup_brain_service import decide_follow_up
from core.services.lead_intelligence_service import analyze_buyer_type
from core.services.negotiation_engine_service import analyze_negotiation
from core.services.operator_assistant_service import build_operator_assist
from core.services.revenue_predictor_service import predict_lead_revenue
from core.services.signal_vector_service import build_signal_vector, with_deal_probability
from shared.utils.deal_probability import evaluate_deal_probability


# ── Result dataclass ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SalesBrainDecision:
    """Unified intelligence output from all 8 CRM analysis services."""

    # Radar / Priority
    priority: str
    priority_score: int

    # Deal Probability
    win_probability: int

    # Buyer Intelligence
    buyer_type: str | None
    buyer_confidence: float

    # Conversation Graph
    stage: str
    trend: str

    # Recommended Actions
    recommended_action: str
    recommended_message_type: str | None
    recommended_operator_reply: str
    recommended_followup_delay_minutes: int | None

    # Revenue
    revenue_best: int | None
    revenue_range: str | None
    upsell_potential: str

    # Risk assessment
    risk_flags: list[str] = field(default_factory=list)
    reason_summary: str = ""

    # Pass-through sub-results
    deal_probability: object | None = None
    buyer_profile: object | None = None
    revenue_estimate: object | None = None
    negotiation_result: object | None = None
    conversation_graph: object | None = None
    followup_decision: object | None = None
    radar_result: object | None = None
    operator_assist: object | None = None


# ── Private helpers ──────────────────────────────────────────────────────────


def _build_risk_flags(
    *,
    ng: object,
    cg: object,
    fd: object,
    dp: object,
    last_objection: str | None,
    follow_up_count: int,
    lead_temperature: str | None,
) -> list[str]:
    flags: list[str] = []

    if last_objection == "delay":
        flags.append("Kechiktirish e'tirozi faol")

    if cg.engagement_trend == "cooling_down":  # type: ignore[union-attr]
        flags.append("Qiziqish pasaymoqda")

    if ng.escalate_to_manager:  # type: ignore[union-attr]
        flags.append("Menejerga uzatish kerak")

    if dp.deal_probability_percent < 30 and follow_up_count >= 2:  # type: ignore[union-attr]
        flags.append("Ko'p follow-up, past ehtimol")

    if lead_temperature == "cold":
        flags.append("Sovuq lid")

    if follow_up_count >= 4:
        flags.append("Follow-up limiti yaqin")

    if not fd.should_follow_up and fd.skip_reason:  # type: ignore[union-attr]
        flags.append(f"FU to'xtatilgan: {fd.skip_reason}")  # type: ignore[union-attr]

    if last_objection == "angry":
        flags.append("Norozilik e'tirozi")

    if dp.confidence_level == "low":  # type: ignore[union-attr]
        flags.append("Past ishonch darajasi")

    return flags[:6]


def _build_reason_summary(
    *,
    rr: object,
    dp: object,
    cg: object,
    fd: object,
    risk_flags: list[str],
) -> str:
    bucket_label = BUCKET_LABELS.get(
        rr.radar_bucket, rr.radar_bucket  # type: ignore[union-attr]
    )
    stage_label = STAGE_LABELS.get(
        cg.current_decision_stage, cg.current_decision_stage  # type: ignore[union-attr]
    )
    parts: list[str] = [
        f"{bucket_label} | {dp.deal_probability_percent}% ehtimol | {stage_label}",  # type: ignore[union-attr]
    ]

    if risk_flags:
        parts.append(f"Risk: {risk_flags[0]}")
    elif fd.should_follow_up and fd.follow_up_reason:  # type: ignore[union-attr]
        parts.append(fd.follow_up_reason)  # type: ignore[union-attr]
    else:
        parts.append(rr.radar_reason)  # type: ignore[union-attr]

    return ". ".join(parts)


def _pick_best_operator_reply(
    *,
    oa: object,
    cg: object,
    bp: object,
    ng: object,
    phone_captured: bool,
    closing_attempted: bool,
) -> str:
    if (
        cg.current_decision_stage == "close_ready"  # type: ignore[union-attr]
        and phone_captured
    ):
        return oa.operator_reply_close  # type: ignore[union-attr]

    if ng.escalate_to_manager:  # type: ignore[union-attr]
        return oa.operator_call_script  # type: ignore[union-attr]
    if phone_captured and not closing_attempted:
        return oa.operator_call_script  # type: ignore[union-attr]

    if bp.buyer_type == "price_sensitive":  # type: ignore[union-attr]
        return oa.operator_reply_budget  # type: ignore[union-attr]

    if cg.current_decision_stage in ("close_ready", "negotiating"):  # type: ignore[union-attr]
        return oa.operator_reply_close  # type: ignore[union-attr]

    if cg.engagement_trend == "warming_up":  # type: ignore[union-attr]
        return oa.operator_reply_close  # type: ignore[union-attr]

    return oa.operator_reply_soft  # type: ignore[union-attr]


def _format_revenue_range(re: object) -> str | None:
    mn = re.predicted_revenue_min  # type: ignore[union-attr]
    mx = re.predicted_revenue_max  # type: ignore[union-attr]
    if mn is None or mx is None:
        return None
    return f"{mn:,} - {mx:,} UZS"


# ── Main orchestrator ───────────────────────────────────────────────────────


def build_sales_brain(
    *,
    # Lead identity
    name: str | None = None,
    district: str | None = None,
    phone: str | None = None,
    # Core signals
    score: int = 0,
    closing_confidence: float | None = None,
    phone_captured: bool = False,
    has_area: bool = False,
    area_m2: float | None = None,
    has_district: bool = False,
    closing_attempted: bool = False,
    closing_action: str | None = None,
    last_objection: str | None = None,
    intent: str | None = None,
    follow_up_count: int = 0,
    design_type: str | None = None,
    # Negotiation state
    negotiation_tactic: str | None = None,
    negotiation_escalated: bool = False,
    previous_negotiation_tactic: str | None = None,
    # Timing
    last_activity_ts: int | None = None,
    memory_created_at: int | None = None,
    # Follow-up state
    lead_temperature: str | None = None,
    previous_fu_type: str | None = None,
    # Lead status (for radar terminal check)
    lead_status: str | None = None,
    # Package type (for revenue predictor)
    package_type: str | None = None,
) -> SalesBrainDecision:
    """Orchestrate all 8 intelligence services into a single decision.

    All parameters are keyword-only with safe defaults.
    Pure function — no I/O, fully deterministic.
    """
    # ── Step 0: Build SignalVector (normalised, no double-counting) ──────
    sv = build_signal_vector(
        lead_score=score,
        closing_confidence=closing_confidence,
        phone_captured=phone_captured,
        has_area=has_area,
        area_m2=area_m2,
        has_district=has_district,
        closing_attempted=closing_attempted,
        closing_action=closing_action,
        last_objection=last_objection,
        intent=intent,
        follow_up_count=follow_up_count,
        design_type=design_type,
        lead_temperature=lead_temperature,
        lead_status=lead_status,
        negotiation_escalated=negotiation_escalated,
        last_activity_ts=last_activity_ts,
    )

    # ── Step 1: Deal Probability ──────────────────────────────────────────
    dp = evaluate_deal_probability(signal_vector=sv)

    # Update SV with dp result for downstream engines
    sv = with_deal_probability(sv, dp.deal_probability_percent)

    # ── Step 2: Buyer Intelligence ────────────────────────────────────────
    bp = analyze_buyer_type(
        score=score,
        closing_confidence=closing_confidence,
        phone_captured=phone_captured,
        has_area=has_area,
        has_district=has_district,
        closing_attempted=closing_attempted,
        closing_action=closing_action,
        last_objection=last_objection,
        intent=intent,
        follow_up_count=follow_up_count,
        design_type=design_type,
        deal_probability_percent=dp.deal_probability_percent,
    )

    # ── Step 3: Revenue Predictor ─────────────────────────────────────────
    re = predict_lead_revenue(
        area_m2=area_m2,
        design_type=design_type,
        buyer_type=bp.buyer_type,
        last_objection=last_objection,
        closing_attempted=closing_attempted,
        package_type=package_type,
        deal_probability_percent=dp.deal_probability_percent,
    )

    # ── Step 4: Negotiation Engine ────────────────────────────────────────
    ng = analyze_negotiation(
        objection_type=last_objection,
        area_m2=area_m2,
        design_type=design_type,
        score=score,
        buyer_type=bp.buyer_type,
        closing_confidence=closing_confidence,
        phone_captured=phone_captured,
        closing_attempted=closing_attempted,
        follow_up_count=follow_up_count,
        previous_negotiation_tactic=previous_negotiation_tactic or negotiation_tactic,
    )

    # ── Step 5: Conversation Graph ────────────────────────────────────────
    effective_tactic = ng.tactic if ng.negotiation_detected else negotiation_tactic
    effective_escalated = negotiation_escalated or ng.escalate_to_manager

    cg = analyze_conversation_graph(
        score=score,
        phone_captured=phone_captured,
        has_area=has_area,
        has_district=has_district,
        has_design=bool(design_type),
        closing_attempted=closing_attempted,
        last_objection=last_objection,
        intent=intent,
        follow_up_count=follow_up_count,
        deal_probability_percent=dp.deal_probability_percent,
        buyer_type=bp.buyer_type,
        negotiation_tactic=effective_tactic,
        negotiation_escalated=effective_escalated,
        closing_confidence=closing_confidence,
        last_activity_ts=last_activity_ts,
        memory_created_at=memory_created_at,
    )

    # ── Step 6: Follow-up Brain ───────────────────────────────────────────
    fd = decide_follow_up(
        score=score,
        deal_probability_percent=dp.deal_probability_percent,
        buyer_type=bp.buyer_type,
        decision_stage=cg.current_decision_stage,
        engagement_trend=cg.engagement_trend,
        last_objection=last_objection,
        phone_captured=phone_captured,
        has_area=has_area,
        has_district=has_district,
        has_design=bool(design_type),
        closing_attempted=closing_attempted,
        negotiation_tactic=effective_tactic,
        negotiation_escalated=effective_escalated,
        follow_up_count=follow_up_count,
        last_activity_ts=last_activity_ts,
        closing_confidence=closing_confidence,
        lead_temperature=lead_temperature,
        previous_fu_type=previous_fu_type,
    )

    # ── Step 7: Deal Radar (uses SignalVector) ─────────────────────────────
    # Enrich SV with upstream results for radar
    from dataclasses import replace as _dc_replace
    sv_radar = _dc_replace(
        sv,
        predicted_revenue_best=re.predicted_revenue_best,
        predicted_revenue_max=re.predicted_revenue_max,
        decision_stage=cg.current_decision_stage,
        engagement_trend=cg.engagement_trend,
        follow_up_should=fd.should_follow_up,
        follow_up_type=fd.follow_up_type if fd.should_follow_up else None,
        negotiation_escalated=effective_escalated,
    )
    rr = rank_lead_for_radar(signal_vector=sv_radar)

    # ── Step 8: Operator Assistant ────────────────────────────────────────
    oa = build_operator_assist(
        name=name,
        score=score,
        buyer_type=bp.buyer_type,
        decision_stage=cg.current_decision_stage,
        engagement_trend=cg.engagement_trend,
        last_objection=last_objection,
        area_m2=area_m2,
        district=district,
        design_type=design_type,
        phone_captured=phone_captured,
        closing_attempted=closing_attempted,
        deal_probability_percent=dp.deal_probability_percent,
        negotiation_tactic=effective_tactic,
        negotiation_escalated=effective_escalated,
        follow_up_type=fd.follow_up_type if fd.should_follow_up else None,
    )

    # ── Assemble composite fields ─────────────────────────────────────────
    risk_flags = _build_risk_flags(
        ng=ng,
        cg=cg,
        fd=fd,
        dp=dp,
        last_objection=last_objection,
        follow_up_count=follow_up_count,
        lead_temperature=lead_temperature,
    )

    reason_summary = _build_reason_summary(
        rr=rr, dp=dp, cg=cg, fd=fd, risk_flags=risk_flags,
    )

    best_reply = _pick_best_operator_reply(
        oa=oa, cg=cg, bp=bp, ng=ng,
        phone_captured=phone_captured,
        closing_attempted=closing_attempted,
    )

    return SalesBrainDecision(
        priority=rr.radar_bucket,
        priority_score=rr.radar_priority_score,
        win_probability=dp.deal_probability_percent,
        buyer_type=bp.buyer_type,
        buyer_confidence=bp.confidence,
        stage=cg.current_decision_stage,
        trend=cg.engagement_trend,
        recommended_action=rr.recommended_immediate_action or dp.recommended_action,
        recommended_message_type=(
            fd.follow_up_type if fd.should_follow_up else None
        ),
        recommended_operator_reply=best_reply,
        recommended_followup_delay_minutes=(
            fd.follow_up_delay_minutes if fd.should_follow_up else None
        ),
        revenue_best=re.predicted_revenue_best,
        revenue_range=_format_revenue_range(re),
        upsell_potential=re.upsell_potential,
        risk_flags=risk_flags,
        reason_summary=reason_summary,
        deal_probability=dp,
        buyer_profile=bp,
        revenue_estimate=re,
        negotiation_result=ng,
        conversation_graph=cg,
        followup_decision=fd,
        radar_result=rr,
        operator_assist=oa,
    )
