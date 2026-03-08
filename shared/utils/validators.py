"""Validation helpers for onboarding wizard fields."""
from __future__ import annotations

import re

# Telegram bot token format: {bot_id}:{alphanumeric_part}
# Bot IDs can be 6-10 digits; the secret part is typically 35 chars but can vary
_BOT_TOKEN_RE = re.compile(r"^\d{6,10}:[A-Za-z0-9_-]{30,50}$")


def is_valid_bot_token(token: str) -> bool:
    """Validate Telegram bot token format (does NOT call Telegram API)."""
    return bool(_BOT_TOKEN_RE.match(token.strip()))


def is_valid_group_id(text: str) -> bool:
    """Validate a Telegram group/supergroup chat ID (negative integer)."""
    text = text.strip()
    if not text.lstrip("-").isdigit():
        return False
    return int(text) < 0
