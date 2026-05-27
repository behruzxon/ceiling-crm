"""
core.services.conversation_memory_graph_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Deterministic conversation journey tracker for leads.

Analyses the accumulated memory signals of a lead conversation and infers:
  - **current_decision_stage** — where the lead is in the buying funnel
  - **engagement_trend** — whether the lead is warming up or cooling down
  - **last_significant_signals** — the most recent meaningful actions
  - **recommended_next_step** — one Uzbek-language admin recommendation
  - **timeline_summary** — ordered list of milestones reached

This is an **additional state-tracking layer** — it does NOT replace lead
scoring, deal probability, buyer intelligence, or the negotiation engine.

Decision stages
---------------
  new_interest   — first contact, no deep signals yet
  researching    — asking questions, viewing catalog
  comparing      — comparing with competitors, asking for alternatives
  negotiating    — price objections, negotiation engine active
  close_ready    — phone captured + CTA accepted + high probability
  delayed        — explicit delay objection or long silence
  cold           — disengaged, no recent activity

Engagement trends
-----------------
  warming_up     — progressive signal accumulation (price → catalog → phone)
  stable         — consistent engagement, no regression
  cooling_down   — objections + delay + no new positive signals
  reactivated    — old lead responds after period of silence

Usage::

    from core.services.conversation_memory_graph_service import (
        analyze_conversation_graph,
    )

    graph = analyze_conversation_graph(
        score=65,
        phone_captured=True,
        has_area=True,
        has_district=True,
        closing_attempted=True,
        last_objection=None,
        deal_probability_percent=72,
        buyer_type="fast_buyer",
        negotiation_tactic="value_reframe",
    )
    # graph.current_decision_stage == "close_ready"
    # graph.engagement_trend == "warming_up"
"""

from __future__ import annotations

import time
from dataclasses import dataclass

# ── Result dataclass ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ConversationGraph:
    """Structured conversation journey analysis for a lead."""

    current_decision_stage: str
    """One of: new_interest | researching | comparing | negotiating |
    close_ready | delayed | cold."""

    engagement_trend: str
    """One of: warming_up | stable | cooling_down | reactivated."""

    last_significant_signals: list[str]
    """Recent meaningful actions (Uzbek), max 5."""

    recommended_next_step: str
    """One Uzbek-language action recommendation for the admin."""

    timeline_summary: list[str]
    """Ordered milestones reached (Uzbek), max 6."""


# ── Stage labels for admin visibility ────────────────────────────────────────

STAGE_LABELS: dict[str, str] = {
    "new_interest": "Yangi qiziqish",
    "researching": "Tadqiq qilmoqda",
    "comparing": "Taqqoslamoqda",
    "negotiating": "Muzokara",
    "close_ready": "Sotuvga tayyor",
    "delayed": "Kechiktirilgan",
    "cold": "Sovuq",
}

TREND_LABELS: dict[str, str] = {
    "warming_up": "\u2b06 Isitilmoqda",
    "stable": "\u27a1 Barqaror",
    "cooling_down": "\u2b07 Sovumoqda",
    "reactivated": "\u21bb Qayta faollashdi",
}

# ── Recommended actions by stage ─────────────────────────────────────────────

_STAGE_ACTIONS: dict[str, str] = {
    "new_interest": "Katalog yuboring va qiziqish aniqlang",
    "researching": "Batafsil ma'lumot va namunalar yuboring",
    "comparing": "Raqobat ustunliklarini ko'rsating",
    "negotiating": "Maxsus taklif yoki chegirma tayyorlang",
    "close_ready": "Darhol qo'ng'iroq qiling!",
    "delayed": "24 soatdan keyin yumshoq follow-up",
    "cold": "Bir hafta keyin qisqa xabar yuboring",
}

# Trend can override stage action
_TREND_OVERRIDES: dict[str, str] = {
    "reactivated": "Tez javob bering — qaytib keldi!",
    "cooling_down": "Qiymat taklifini eslatib o'ting",
}

# ── Signal weight for engagement scoring ─────────────────────────────────────

_POSITIVE_SIGNAL_WEIGHTS: dict[str, float] = {
    "phone_captured": 5.0,
    "has_area": 3.0,
    "has_district": 2.0,
    "has_design": 2.5,
    "closing_attempted": 4.0,
    "catalog_viewed": 1.5,
    "price_asked": 2.0,
    "high_score": 3.0,
    "high_probability": 3.5,
}

_NEGATIVE_SIGNAL_WEIGHTS: dict[str, float] = {
    "delay_objection": -4.0,
    "angry_objection": -3.0,
    "negotiation_escalated": -2.0,
    "many_followups": -2.5,
    "long_silence": -3.0,
}


# ── Main analyzer ───────────────────────────────────────────────────────────


def analyze_conversation_graph(
    *,
    score: int = 0,
    phone_captured: bool = False,
    has_area: bool = False,
    has_district: bool = False,
    has_design: bool = False,
    closing_attempted: bool = False,
    last_objection: str | None = None,
    intent: str | None = None,
    follow_up_count: int = 0,
    deal_probability_percent: int | None = None,
    buyer_type: str | None = None,
    negotiation_tactic: str | None = None,
    negotiation_escalated: bool = False,
    closing_confidence: float | None = None,
    last_activity_ts: int | None = None,
    memory_created_at: int | None = None,
) -> ConversationGraph:
    """Analyze the conversation journey from accumulated CRM signals.

    All parameters are keyword-only with safe defaults.
    Pure function — no I/O, fully deterministic.
    """
    now = int(time.time())

    # ── 1. Build signal inventory ───────────────────────────────────
    signals = _collect_signals(
        score=score,
        phone_captured=phone_captured,
        has_area=has_area,
        has_district=has_district,
        has_design=has_design,
        closing_attempted=closing_attempted,
        last_objection=last_objection,
        intent=intent,
        follow_up_count=follow_up_count,
        deal_probability_percent=deal_probability_percent,
        negotiation_tactic=negotiation_tactic,
        negotiation_escalated=negotiation_escalated,
    )

    # ── 2. Determine engagement trend ───────────────────────────────
    trend = _determine_trend(
        signals=signals,
        last_activity_ts=last_activity_ts,
        memory_created_at=memory_created_at,
        now=now,
        follow_up_count=follow_up_count,
        last_objection=last_objection,
    )

    # ── 3. Determine decision stage ─────────────────────────────────
    stage = _determine_stage(
        signals=signals,
        trend=trend,
        score=score,
        phone_captured=phone_captured,
        has_area=has_area,
        has_district=has_district,
        closing_attempted=closing_attempted,
        last_objection=last_objection,
        deal_probability_percent=deal_probability_percent,
        buyer_type=buyer_type,
        negotiation_tactic=negotiation_tactic,
        closing_confidence=closing_confidence,
        follow_up_count=follow_up_count,
    )

    # ── 4. Build timeline summary ───────────────────────────────────
    timeline = _build_timeline(
        has_area=has_area,
        has_district=has_district,
        has_design=has_design,
        phone_captured=phone_captured,
        closing_attempted=closing_attempted,
        last_objection=last_objection,
        negotiation_tactic=negotiation_tactic,
        intent=intent,
        deal_probability_percent=deal_probability_percent,
    )

    # ── 5. Last significant signals ─────────────────────────────────
    last_signals = _build_last_signals(
        score=score,
        phone_captured=phone_captured,
        has_area=has_area,
        has_district=has_district,
        has_design=has_design,
        closing_attempted=closing_attempted,
        last_objection=last_objection,
        intent=intent,
        negotiation_tactic=negotiation_tactic,
        deal_probability_percent=deal_probability_percent,
    )

    # ── 6. Recommended next step ────────────────────────────────────
    next_step = _TREND_OVERRIDES.get(trend, _STAGE_ACTIONS.get(stage, ""))

    return ConversationGraph(
        current_decision_stage=stage,
        engagement_trend=trend,
        last_significant_signals=last_signals[:5],
        recommended_next_step=next_step,
        timeline_summary=timeline[:6],
    )


# ── Signal collector ─────────────────────────────────────────────────────────


def _collect_signals(
    *,
    score: int,
    phone_captured: bool,
    has_area: bool,
    has_district: bool,
    has_design: bool,
    closing_attempted: bool,
    last_objection: str | None,
    intent: str | None,
    follow_up_count: int,
    deal_probability_percent: int | None,
    negotiation_tactic: str | None,
    negotiation_escalated: bool,
) -> dict[str, bool]:
    """Collect boolean signal flags from CRM data."""
    return {
        "phone_captured": phone_captured,
        "has_area": has_area,
        "has_district": has_district,
        "has_design": has_design,
        "closing_attempted": closing_attempted,
        "catalog_viewed": intent == "catalog",
        "price_asked": intent == "price",
        "high_score": score >= 50,
        "high_probability": (deal_probability_percent or 0) >= 60,
        "delay_objection": last_objection == "delay",
        "angry_objection": last_objection == "angry",
        "expensive_objection": last_objection == "expensive",
        "compare_objection": last_objection == "compare",
        "negotiation_active": negotiation_tactic is not None and negotiation_tactic != "none",
        "negotiation_escalated": negotiation_escalated,
        "many_followups": follow_up_count >= 3,
    }


# ── Trend determination ──────────────────────────────────────────────────────


def _determine_trend(
    *,
    signals: dict[str, bool],
    last_activity_ts: int | None,
    memory_created_at: int | None,
    now: int,
    follow_up_count: int,
    last_objection: str | None,
) -> str:
    """Infer engagement trend from signal pattern + timing."""

    # Reactivation: old lead (created >48h ago) with recent activity (<2h ago)
    if memory_created_at and last_activity_ts:
        age_hours = (now - memory_created_at) / 3600
        silence_hours = (now - last_activity_ts) / 3600
        if age_hours > 48 and silence_hours < 2:
            return "reactivated"

    # Long silence: last activity >24h ago
    if last_activity_ts:
        silence_hours = (now - last_activity_ts) / 3600
        if silence_hours > 24:
            # If signals are strong, it's just delayed, not cooling
            positive_count = sum(
                1
                for k in (
                    "phone_captured",
                    "has_area",
                    "has_district",
                    "closing_attempted",
                    "high_score",
                )
                if signals.get(k)
            )
            if positive_count < 3:
                return "cooling_down"

    # Cooling: delay/angry objection + many follow-ups + no strong positive signals
    if (signals.get("delay_objection") or signals.get("angry_objection")) and follow_up_count >= 2:
        return "cooling_down"

    # Warming: progressive signal accumulation
    positive_count = sum(
        1
        for k in (
            "phone_captured",
            "has_area",
            "has_district",
            "has_design",
            "closing_attempted",
            "catalog_viewed",
            "price_asked",
            "high_score",
            "high_probability",
        )
        if signals.get(k)
    )

    if positive_count >= 4:
        return "warming_up"

    if positive_count >= 2:
        return "stable"

    # Few signals — either new or cooling
    if last_objection in ("delay", "angry"):
        return "cooling_down"

    return "stable"


# ── Stage determination ──────────────────────────────────────────────────────


def _determine_stage(
    *,
    signals: dict[str, bool],
    trend: str,
    score: int,
    phone_captured: bool,
    has_area: bool,
    has_district: bool,
    closing_attempted: bool,
    last_objection: str | None,
    deal_probability_percent: int | None,
    buyer_type: str | None,
    negotiation_tactic: str | None,
    closing_confidence: float | None,
    follow_up_count: int,
) -> str:
    """Determine the current decision stage from signals + trend."""

    prob = deal_probability_percent or 0

    # ── Cold: cooling trend + low engagement ─────────────────────────
    if trend == "cooling_down" and score < 20 and not phone_captured:
        return "cold"

    # ── Delayed: explicit delay + no closing ─────────────────────────
    if last_objection == "delay" and not closing_attempted:
        return "delayed"

    # ── Close ready: strong closing signals ──────────────────────────
    if phone_captured and closing_attempted and prob >= 60:
        return "close_ready"
    if (
        phone_captured
        and score >= 60
        and (closing_confidence is not None and closing_confidence >= 0.7)
    ):
        return "close_ready"

    # ── Negotiating: active negotiation or price pressure ────────────
    if signals.get("negotiation_active"):
        return "negotiating"
    if last_objection == "expensive" and score >= 30:
        return "negotiating"

    # ── Comparing: comparison objection or research buyer comparing ──
    if signals.get("compare_objection"):
        return "comparing"
    if buyer_type == "research_buyer" and (
        signals.get("catalog_viewed") or signals.get("price_asked")
    ):
        return "comparing"

    # ── Researching: some data collected but no commitment ───────────
    if (has_area or has_district or signals.get("has_design")) and not phone_captured:
        return "researching"
    if signals.get("catalog_viewed") and not phone_captured:
        return "researching"
    if buyer_type == "research_buyer":
        return "researching"

    # ── New interest: minimal signals ────────────────────────────────
    if score < 20 and not has_area and not has_district and not phone_captured:
        return "new_interest"

    # ── Fallback: infer from signal density ──────────────────────────
    positive_count = sum(
        1
        for k in (
            "phone_captured",
            "has_area",
            "has_district",
            "closing_attempted",
            "high_score",
        )
        if signals.get(k)
    )
    if positive_count >= 3:
        return "close_ready"
    if positive_count >= 1:
        return "researching"
    return "new_interest"


# ── Timeline builder ─────────────────────────────────────────────────────────


def _build_timeline(
    *,
    has_area: bool,
    has_district: bool,
    has_design: bool,
    phone_captured: bool,
    closing_attempted: bool,
    last_objection: str | None,
    negotiation_tactic: str | None,
    intent: str | None,
    deal_probability_percent: int | None,
) -> list[str]:
    """Build an ordered timeline of milestones reached."""
    timeline: list[str] = []

    # Ordered by typical funnel progression
    if intent == "price":
        timeline.append("Narx so'ragan")
    if intent == "catalog":
        timeline.append("Katalog ko'rgan")
    if has_area:
        timeline.append("Maydon aniqlangan")
    if has_district:
        timeline.append("Manzil aniqlangan")
    if has_design:
        timeline.append("Dizayn tanlangan")
    if last_objection:
        _obj_map = {
            "expensive": "Narx e'tirozi",
            "trust": "Ishonch e'tirozi",
            "compare": "Taqqoslash e'tirozi",
            "delay": "Kechiktirish e'tirozi",
            "angry": "Norozilik e'tirozi",
        }
        timeline.append(_obj_map.get(last_objection, "E'tiroz"))
    if negotiation_tactic and negotiation_tactic != "none":
        timeline.append("Muzokara boshlangan")
    if phone_captured:
        timeline.append("Telefon ulashilgan")
    if closing_attempted:
        timeline.append("Closing CTA qabul qilingan")
    if (deal_probability_percent or 0) >= 70:
        timeline.append("Yuqori ehtimollik")

    return timeline


# ── Last significant signals ─────────────────────────────────────────────────


def _build_last_signals(
    *,
    score: int,
    phone_captured: bool,
    has_area: bool,
    has_district: bool,
    has_design: bool,
    closing_attempted: bool,
    last_objection: str | None,
    intent: str | None,
    negotiation_tactic: str | None,
    deal_probability_percent: int | None,
) -> list[str]:
    """Build a list of the most recent/relevant signals, highest impact first."""
    signals: list[str] = []

    # Highest impact signals first
    if phone_captured:
        signals.append("Telefon raqam ulashgan")
    if closing_attempted:
        signals.append("Closing CTA qabul qilgan")
    if (deal_probability_percent or 0) >= 70:
        signals.append(f"Ehtimollik: {deal_probability_percent}%")
    if score >= 50:
        signals.append(f"Yuqori ball: {score}")
    if negotiation_tactic and negotiation_tactic != "none":
        from core.services.negotiation_engine_service import TACTIC_LABELS

        signals.append(f"Muzokara: {TACTIC_LABELS.get(negotiation_tactic, negotiation_tactic)}")
    if last_objection:
        _obj_labels = {
            "expensive": "Narx e'tirozi",
            "trust": "Ishonch e'tirozi",
            "compare": "Taqqoslash",
            "delay": "Kechiktirish",
            "angry": "Norozilik",
        }
        signals.append(_obj_labels.get(last_objection, last_objection))
    if has_design:
        signals.append("Dizayn tanlangan")
    if has_area:
        signals.append("Maydon aniqlangan")
    if has_district:
        signals.append("Manzil aniqlangan")
    if intent == "catalog":
        signals.append("Katalog ko'rgan")
    if intent == "price":
        signals.append("Narx so'ragan")

    return signals
