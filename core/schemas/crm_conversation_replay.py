"""Conversation replay schemas."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ConversationReplayEvent:
    event_id: str = ""
    event_type: str = ""
    actor: str = "system"
    title: str = ""
    description: str = ""
    message_preview: str | None = None
    intent: str | None = None
    severity: str | None = None
    status: str | None = None
    related_contact_id: int | None = None
    related_handoff_id: int | None = None
    metadata_summary: str | None = None
    icon_key: str = "circle"
    timestamp: str | None = None


@dataclass
class ConversationReplaySummary:
    total_events: int = 0
    user_messages: int = 0
    bot_replies: int = 0
    price_events: int = 0
    handoff_events: int = 0
    objections: int = 0
    stop_events: int = 0
    first_seen_at: str | None = None
    last_event_at: str | None = None
    recommended_next_action: str = ""


@dataclass
class ConversationReplayResult:
    contact_id: int = 0
    events: list[ConversationReplayEvent] = field(default_factory=list)
    summary: ConversationReplaySummary = field(
        default_factory=ConversationReplaySummary,
    )
