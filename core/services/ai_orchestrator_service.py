"""
core.services.ai_orchestrator_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
AI Control Center — single top-level entry point that coordinates
all intelligence modules and returns a unified state object.

Sits on top of :func:`build_sales_brain` (which orchestrates 8 services)
and adds auto-closer strategy selection, normalized risk flags, and a
rich brain summary.

Pure function — no I/O, no DB, no Redis. Fully deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.services.ai_auto_closer_service import (
    _build_reply,
    _compute_confidence,
    _select_strategy,
)
from core.services.ai_sales_brain_service import SalesBrainDecision, build_sales_brain

# ── Risk flag slug mapping (Uzbek → English) ────────────────────────────────

_RISK_SLUG_MAP: dict[str, str] = {
    "Kechiktirish e'tirozi faol": "delay_signal",
    "Qiziqish pasaymoqda": "cooling_trend",
    "Menejerga uzatish kerak": "escalation_needed",
    "Ko'p follow-up, past ehtimol": "low_conversion",
    "Sovuq lid": "cold_lead",
    "Follow-up limiti yaqin": "followup_cap",
    "Norozilik e'tirozi": "angry_objection",
    "Past ishonch darajasi": "low_confidence",
}


# ── Result dataclass ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class AIOrchestratorState:
    """Unified AI decision/state object for a lead or user interaction."""

    # Priority
    priority: str
    priority_score: int

    # Probability
    win_probability: float

    # Buyer
    buyer_type: str | None
    buyer_confidence: float

    # Conversation
    stage: str
    trend: str

    # Recommendations
    recommended_action: str
    recommended_followup_type: str | None
    recommended_followup_delay_minutes: int | None
    recommended_message_type: str
    recommended_operator_reply: str

    # Auto-close
    auto_close_reply: str
    auto_close_confidence: float

    # Revenue
    revenue_best: int | None
    revenue_range: str | None
    upsell_potential: str

    # Assessment
    risk_flags: list[str] = field(default_factory=list)
    brain_summary: list[str] = field(default_factory=list)

    # Pass-through
    sales_brain: SalesBrainDecision | None = None


# ── Private helpers ──────────────────────────────────────────────────────────


def _slugify_risk_flags(flags: list[str]) -> list[str]:
    """Convert Uzbek risk flag strings to English slugs."""
    result: list[str] = []
    for flag in flags:
        # Direct mapping first
        for uz_text, slug in _RISK_SLUG_MAP.items():
            if uz_text in flag:
                result.append(slug)
                break
        else:
            # FU skip reasons come as "FU to'xtatilgan: ..." → generic slug
            if flag.startswith("FU to'xtatilgan"):
                result.append("followup_stopped")
            else:
                # Fallback: lowercase, replace spaces with underscores
                result.append(flag.lower().replace(" ", "_").replace("'", ""))
    return result


def _build_brain_summary(
    brain: SalesBrainDecision,
    strategy: str,
    last_objection: str | None,
    phone_captured: bool,
    has_area: bool,
    has_district: bool,
) -> list[str]:
    """Build 3-6 descriptive summary strings from brain output."""
    lines: list[str] = []

    # 1. Score classification
    if brain.win_probability >= 60:
        lines.append("Lead score is high")
    elif brain.win_probability >= 30:
        lines.append("Lead score is moderate")
    else:
        lines.append("Lead score is low")

    # 2. Objection
    _obj_desc = {
        "expensive": "Price objection detected",
        "compare": "Comparing with competitors",
        "delay": "Delay signal detected",
        "trust": "Trust concern raised",
        "angry": "Negative sentiment detected",
    }
    if last_objection and last_objection in _obj_desc:
        lines.append(_obj_desc[last_objection])

    # 3. Data captured
    captured: list[str] = []
    if phone_captured:
        captured.append("phone")
    if has_area:
        captured.append("area")
    if has_district:
        captured.append("district")
    if captured:
        lines.append(f"User shared {' and '.join(captured)}")

    # 4. Trend
    _trend_desc = {
        "warming_up": "Trend is warming up",
        "cooling_down": "Trend is cooling down",
        "reactivated": "Lead has reactivated",
        "stable": "Engagement is stable",
    }
    if brain.trend in _trend_desc:
        lines.append(_trend_desc[brain.trend])

    # 5. Strategy
    _strat_desc = {
        "budget_option": "Budget approach recommended",
        "premium_design": "Premium design pitch recommended",
        "measurement_push": "Free measurement offer recommended",
        "direct_close": "Direct close attempt recommended",
        "soft_followup": "Soft follow-up recommended",
    }
    if strategy in _strat_desc:
        lines.append(_strat_desc[strategy])

    # 6. Revenue (if available)
    if brain.revenue_best:
        lines.append(f"Predicted revenue: {brain.revenue_best:,} UZS")

    return lines[:6]


# ── Main function ────────────────────────────────────────────────────────────


def build_ai_orchestrator_state(
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
    # Lead status
    lead_status: str | None = None,
    package_type: str | None = None,
) -> AIOrchestratorState:
    """Build the unified AI orchestrator state for a lead.

    Calls :func:`build_sales_brain` (which orchestrates all 8 intelligence
    services), adds auto-closer strategy selection, normalizes risk flags
    to English slugs, and builds a rich brain summary.

    Pure function — no I/O, fully deterministic.
    """
    # ── Step 1: Full intelligence via Sales Brain ─────────────────────────
    brain = build_sales_brain(
        name=name,
        district=district,
        phone=phone,
        score=score,
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
        negotiation_tactic=negotiation_tactic,
        negotiation_escalated=negotiation_escalated,
        previous_negotiation_tactic=previous_negotiation_tactic,
        last_activity_ts=last_activity_ts,
        memory_created_at=memory_created_at,
        lead_temperature=lead_temperature,
        previous_fu_type=previous_fu_type,
        lead_status=lead_status,
        package_type=package_type,
    )

    # ── Step 2: Auto-closer strategy (reuse, don't duplicate) ─────────────
    strategy = _select_strategy(
        brain=brain,
        last_objection=last_objection,
        intent=intent,
        phone_captured=phone_captured,
    )
    auto_reply = _build_reply(strategy, name)
    auto_confidence = _compute_confidence(brain)

    # ── Step 3: Normalize risk flags to English slugs ─────────────────────
    risk_slugs = _slugify_risk_flags(brain.risk_flags)

    # ── Step 4: Build rich brain summary ──────────────────────────────────
    summary = _build_brain_summary(
        brain=brain,
        strategy=strategy,
        last_objection=last_objection,
        phone_captured=phone_captured,
        has_area=has_area,
        has_district=has_district,
    )

    return AIOrchestratorState(
        priority=brain.priority,
        priority_score=brain.priority_score,
        win_probability=round(brain.win_probability / 100.0, 2),
        buyer_type=brain.buyer_type,
        buyer_confidence=brain.buyer_confidence,
        stage=brain.stage,
        trend=brain.trend,
        recommended_action=brain.recommended_action,
        recommended_followup_type=brain.recommended_message_type,
        recommended_followup_delay_minutes=brain.recommended_followup_delay_minutes,
        recommended_message_type=strategy,
        recommended_operator_reply=brain.recommended_operator_reply,
        auto_close_reply=auto_reply,
        auto_close_confidence=auto_confidence,
        revenue_best=brain.revenue_best,
        revenue_range=brain.revenue_range,
        upsell_potential=brain.upsell_potential,
        risk_flags=risk_slugs,
        brain_summary=summary,
        sales_brain=brain,
    )
