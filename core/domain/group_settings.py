"""Domain model for per-group moderation settings."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class GroupSettings(BaseModel):
    """Immutable snapshot of one group's moderation settings."""

    model_config = ConfigDict(frozen=True)

    chat_id: int
    welcome_enabled: bool = True
    welcome_autodelete_seconds: int = 3600
    captcha_enabled: bool = False
    link_block_enabled: bool = True
    flood_enabled: bool = False
    logs_enabled: bool = True
    updated_at: datetime | None = None
