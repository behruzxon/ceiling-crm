"""
apps.bot.handlers.group.flood_guard
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Flood control logic for group moderation (C3-4).

check_flood() delegates to the sliding-window is_flooding() helper in
_moderation.py, which uses Redis sorted sets with an in-memory fallback.

Threshold: > 5 messages in 10 seconds → flooding.
"""
from __future__ import annotations

from apps.bot.handlers.group._moderation import is_flooding


async def check_flood(chat_id: int, user_id: int) -> bool:
    """Return True if user_id exceeds the flood threshold in chat_id."""
    return await is_flooding(chat_id, user_id)
