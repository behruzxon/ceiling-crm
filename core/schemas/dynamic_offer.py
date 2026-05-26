"""Frozen dataclasses for dynamic offer engine output."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OfferContext:
    intent: str = "unclear"
    objection_type: str | None = None
    urgency: str = "low"
    lead_score: int = 0
    lead_temperature: str = "cold"
    area_m2: float | None = None
    has_phone: bool = False
    has_image: bool = False
    followup_enabled: bool = True
    customer_state: str = "new_visitor"


@dataclass(frozen=True)
class DynamicOffer:
    offer_type: str
    cta: str
    priority: str
    confidence_score: int
    reason: str
    message_hint: str = ""
    recommended_buttons: list[tuple[str, str]] = field(default_factory=list)
    should_notify_admin: bool = False
    safety_flags: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
