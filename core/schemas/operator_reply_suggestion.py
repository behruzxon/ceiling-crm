"""Frozen dataclasses for the operator AI reply suggestion panel.

These types describe the read-only output the web template renders. They
deliberately do **not** carry any free-form metadata: the only fields are
what the panel displays. There are no fields for raw prompts, tokens,
session hashes, or internal AI metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OperatorReplySuggestion:
    suggestion_id: str = ""
    tone: str = "professional"
    text: str = ""
    reason: str = ""
    risk_level: str = "low"
    copy_label: str = "Copy"


@dataclass(frozen=True)
class OperatorReplySuggestionResult:
    feature_enabled: bool = False
    contact_id: int | str = ""
    source_message_preview: str = ""
    suggestions: tuple[OperatorReplySuggestion, ...] = field(default_factory=tuple)
    empty_reason: str = ""
    safety_note: str = "Bu yordamchi takliflar. Operator har doim tahrirlab yuborishi shart."
