"""Lead scoring & follow-up scheduling helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

# ── Lead Scoring ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LeadScore:
    """Result of lead scoring computation."""
    total_score: int          # 0-100
    classification: str       # "hot" / "warm" / "cold"
    breakdown: dict[str, int] # component scores


def compute_lead_score(
    *,
    message_count: int = 0,
    stage_transitions: int = 0,
    price_inquiries: int = 0,
    has_phone: bool = False,
    has_area: bool = False,
    has_district: bool = False,
    hours_since_last_activity: float | None = None,
    follow_up_count: int = 0,
    closing_confidence: float | None = None,
) -> LeadScore:
    """Score a lead 0-100 based on engagement signals.

    Components (max 100):
      - message_count:       min(messages, 20) → 0-20 pts
      - stage_transitions:   transitions × 8   → 0-24 pts
      - price_inquiries:     inquiries × 5     → 0-15 pts
      - contact info:        phone(+10) + area(+5) + district(+3) → 0-18 pts
      - recency:             0-15 pts (decays with inactivity)
      - confidence boost:    confidence × 8    → 0-8 pts

    Classification:
      ≥ 60 → HOT
      ≥ 30 → WARM
      <  30 → COLD
    """
    breakdown: dict[str, int] = {}

    # Engagement: message count (max 20)
    engagement = min(message_count, 20)
    breakdown["engagement"] = engagement

    # Pipeline progress: stage transitions (max 24)
    pipeline = min(stage_transitions * 8, 24)
    breakdown["pipeline"] = pipeline

    # Purchase intent: price inquiries (max 15)
    intent = min(price_inquiries * 5, 15)
    breakdown["intent"] = intent

    # Contact info completeness (max 18)
    contact = 0
    if has_phone:
        contact += 10
    if has_area:
        contact += 5
    if has_district:
        contact += 3
    breakdown["contact"] = contact

    # Recency: decays with inactivity (max 15)
    recency = 15
    if hours_since_last_activity is not None:
        if hours_since_last_activity > 168:    # > 7 days
            recency = 0
        elif hours_since_last_activity > 72:   # > 3 days
            recency = 3
        elif hours_since_last_activity > 24:   # > 1 day
            recency = 7
        elif hours_since_last_activity > 6:    # > 6h
            recency = 12
    breakdown["recency"] = recency

    # Confidence boost (max 8)
    confidence_pts = 0
    if closing_confidence is not None:
        confidence_pts = min(int(closing_confidence * 8), 8)
    breakdown["confidence"] = confidence_pts

    total = min(engagement + pipeline + intent + contact + recency + confidence_pts, 100)

    if total >= 60:
        classification = "hot"
    elif total >= 30:
        classification = "warm"
    else:
        classification = "cold"

    return LeadScore(
        total_score=total,
        classification=classification,
        breakdown=breakdown,
    )


def compute_next_followup(
    temperature: str | None,
    confidence: float | None,
) -> datetime | None:
    """Return the next_follow_up_at timestamp for a lead.

    Derivation (applied when *temperature* is absent/unrecognised):
      confidence >= 0.75  → "hot"
      confidence >= 0.45  → "warm"
      confidence < 0.45   → "cold"
      no temperature + no confidence → None (no scheduling)

    Delays:
      hot  → +20 minutes
      warm → +3 hours
      cold → +24 hours
    """
    temp = (temperature or "").lower().strip()
    if temp not in ("hot", "warm", "cold"):
        if confidence is None:
            return None
        if confidence >= 0.75:
            temp = "hot"
        elif confidence >= 0.45:
            temp = "warm"
        else:
            temp = "cold"

    now = datetime.now(UTC)
    if temp == "hot":
        return now + timedelta(minutes=20)
    if temp == "warm":
        return now + timedelta(hours=3)
    return now + timedelta(hours=24)  # cold
