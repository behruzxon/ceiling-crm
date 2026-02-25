"""
apps.bot.handlers.group.link_guard
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Link detection logic for group moderation (C3-3).

has_link() returns True when a message contains a blockable link:
- Telegram URL or TEXT_LINK entities (most reliable)
- Bare https://, www. or t.me/ references not parsed as entities
"""
from __future__ import annotations

import re

from aiogram.enums import MessageEntityType
from aiogram.types import Message

# Covers bare https://, www. and t.me/ links that Telegram may not have
# parsed into URL entities (e.g. in captions or edge-case clients).
_LINK_RE = re.compile(r"(https?://|www\.|t\.me/)", re.IGNORECASE)

# Entity types that always represent a blockable link.
_LINK_ENTITY_TYPES: frozenset[str] = frozenset({
    MessageEntityType.URL,
    MessageEntityType.TEXT_LINK,
})


def has_link(message: Message) -> bool:
    """Return True if *message* contains a blockable link."""
    # Check Telegram-parsed entities in text and caption.
    for entities in (message.entities or [], message.caption_entities or []):
        for entity in entities:
            if entity.type in _LINK_ENTITY_TYPES:
                return True

    # Regex fallback for text / caption content.
    text = message.text or message.caption or ""
    if not text:
        return False
    return bool(_LINK_RE.search(text))
