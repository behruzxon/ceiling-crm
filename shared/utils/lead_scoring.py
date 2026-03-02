"""Lead follow-up scheduling helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


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

    now = datetime.now(timezone.utc)
    if temp == "hot":
        return now + timedelta(minutes=20)
    if temp == "warm":
        return now + timedelta(hours=3)
    return now + timedelta(hours=24)  # cold
