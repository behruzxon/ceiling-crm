"""Business logic for per-group moderation settings."""

from __future__ import annotations

from core.domain.group_settings import GroupSettings
from core.repositories.group_settings_repo import AbstractGroupSettingsRepository
from shared.logging import get_logger

log = get_logger(__name__)

# Fields that can be toggled (bool only).
_TOGGLEABLE: frozenset[str] = frozenset(
    {
        "welcome_enabled",
        "captcha_enabled",
        "link_block_enabled",
        "flood_enabled",
        "logs_enabled",
    }
)


class GroupSettingsService:

    def __init__(self, repo: AbstractGroupSettingsRepository) -> None:
        self._repo = repo

    async def get_or_create(self, chat_id: int) -> GroupSettings:
        """Return current settings, creating defaults if first access."""
        return await self._repo.get_or_create(chat_id)

    async def toggle(self, chat_id: int, field: str) -> GroupSettings:
        """Flip a boolean setting and persist the change."""
        if field not in _TOGGLEABLE:
            raise ValueError(f"Field {field!r} is not a toggleable boolean setting")
        current = await self._repo.get_or_create(chat_id)
        new_value = not getattr(current, field)
        settings = await self._repo.set_field(chat_id, field, new_value)
        log.info("group_setting_toggled", chat_id=chat_id, field=field, value=new_value)
        return settings
