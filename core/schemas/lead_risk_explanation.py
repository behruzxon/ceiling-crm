"""Frozen dataclasses for the Lead Risk Explanation panel.

Deterministic, pure output: a risk level + 3-5 short Uzbek reasons.
No AI; no raw customer text in the labels (only sanitised previews
inside ``LeadRiskReason.detail`` are allowed).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LeadRiskReason:
    reason_key: str = ""
    label: str = ""
    detail: str = ""
    weight: int = 0
    tone: str = "info"


@dataclass(frozen=True)
class LeadRiskResult:
    risk_level: str = "unknown"
    score: int = 0
    confidence: int = 0
    reasons: tuple[LeadRiskReason, ...] = field(default_factory=tuple)
    summary: str = ""
    badge_tone: str = "neutral"
    safety_note: str = (
        "Bu xulosa avtomatik signallarga asoslangan. Yakuniy qarorni operator qabul qiladi."
    )
    empty_reason: str = ""
