"""
apps.bot.utils.reactions
~~~~~~~~~~~~~~~~~~~~~~~~~~
Telegram reaction micro-UX helper (2026 bot feel).

When the bot starts working on a message it sets a subtle reaction (👀) on the
user's message so the user feels acknowledged while AI / price / catalog logic
runs; after the reply it clears that reaction (or changes it to ✅). No extra
text messages are ever sent.

Hard safety guarantees
----------------------
* **Default OFF.** Everything no-ops unless ``TELEGRAM_REACTIONS_ENABLED=true``.
* **Private only** by default; groups need ``TELEGRAM_REACTIONS_GROUPS_ENABLED``.
* **Never raises** to the caller. Every Telegram / SDK / generic error is
  swallowed and logged at debug/warning — a reaction problem can never break a
  customer reply.
* **No PII in logs.** We log chat type and emoji only — never message text,
  user text, tokens, or secrets.

Structured log events: ``telegram_reaction_set``, ``telegram_reaction_clear``,
``telegram_reaction_failed``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from shared.config import get_settings
from shared.logging import get_logger

if TYPE_CHECKING:  # avoid importing heavy aiogram types at module import time
    from aiogram import Bot
    from aiogram.types import Message

log = get_logger(__name__)


def _reactions_settings() -> Any:
    """Return the telegram settings group, tolerant of partial settings objects."""
    return getattr(get_settings(), "telegram", None)


def _should_react(message: Message | None) -> bool:
    """Gate: feature on, message usable, and chat type allowed.

    Private chats are always allowed when the feature is on; group/supergroup
    chats require the extra ``reactions_groups_enabled`` flag.
    """
    cfg = _reactions_settings()
    if cfg is None or not getattr(cfg, "reactions_enabled", False):
        return False
    if message is None or getattr(message, "chat", None) is None:
        return False
    if getattr(message, "message_id", None) is None:
        return False
    chat_type = getattr(message.chat, "type", None)
    if chat_type == "private":
        return True
    if chat_type in ("group", "supergroup"):
        return bool(getattr(cfg, "reactions_groups_enabled", False))
    return False


async def _set_reaction(bot: Bot, message: Message, emoji: str | None) -> None:
    """Low-level set/clear. ``emoji=None`` clears the reaction. Never raises."""
    # Import inside the function so the module stays import-light and so a missing
    # aiogram (e.g. in pure unit contexts) can never break import of callers.
    try:
        from aiogram.types import ReactionTypeEmoji

        reaction = [ReactionTypeEmoji(emoji=emoji)] if emoji else []
        await bot.set_message_reaction(
            chat_id=message.chat.id,
            message_id=message.message_id,
            reaction=reaction,
        )
        if emoji:
            log.debug(
                "telegram_reaction_set",
                chat_type=getattr(message.chat, "type", None),
                emoji=emoji,
            )
        else:
            log.debug(
                "telegram_reaction_clear",
                chat_type=getattr(message.chat, "type", None),
            )
    except Exception as exc:  # TelegramBadRequest / Forbidden / anything else
        # Debug-level: an unsupported emoji or a chat that forbids reactions is
        # expected and harmless. We log the exception *type* only — no text/token.
        log.debug(
            "telegram_reaction_failed",
            chat_type=getattr(getattr(message, "chat", None), "type", None),
            error_type=type(exc).__name__,
        )


async def maybe_react_processing(
    bot: Bot,
    message: Message,
    reaction: str | None = None,
) -> None:
    """Set the 'processing' reaction (default 👀) on the user's message.

    No-op when the feature is off or the chat type is not allowed. Never raises.
    """
    if not _should_react(message):
        return
    cfg = _reactions_settings()
    emoji = reaction or getattr(cfg, "reaction_processing", "👀") or "👀"
    await _set_reaction(bot, message, emoji)


async def maybe_react_done(
    bot: Bot,
    message: Message,
    mode: str | None = None,
) -> None:
    """Resolve the processing reaction after the reply was sent.

    Behavior (configurable):
    * ``reaction_clear_on_reply=true`` (default) → clear the reaction (always a
      valid Telegram op).
    * otherwise → change it to ``reaction_done`` (default ✅; if Telegram rejects
      that emoji it is swallowed and the processing reaction simply lingers).

    ``mode`` may be passed explicitly as ``"clear"`` or ``"done"`` to override.
    No-op when the feature is off. Never raises.
    """
    if not _should_react(message):
        return
    cfg = _reactions_settings()
    if mode is None:
        mode = "clear" if getattr(cfg, "reaction_clear_on_reply", True) else "done"
    if mode == "done":
        emoji = getattr(cfg, "reaction_done", "✅") or "✅"
        await _set_reaction(bot, message, emoji)
    else:
        await _set_reaction(bot, message, None)


async def maybe_clear_reaction(bot: Bot, message: Message) -> None:
    """Clear any reaction on the user's message. No-op when off. Never raises."""
    if not _should_react(message):
        return
    await _set_reaction(bot, message, None)
