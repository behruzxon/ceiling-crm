"""Frozen dataclass for the Next Best Action panel.

The panel surfaces the single best deterministic next step for an
operator on a given contact. No AI; no Telegram link; no send button.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NextBestActionResult:
    action_key: str = "clarify_need"
    label: str = "Ehtiyojni aniqlash"
    reason: str = ""
    priority: str = "soon"
    confidence: int = 50
    cta_label: str = ""
    cta_url: str = ""
    badge_tone: str = "info"
    empty_reason: str = ""
    safety_note: str = "Bu yo'l-yo'riq taklif. Operator har doim qaror qabul qiladi."
