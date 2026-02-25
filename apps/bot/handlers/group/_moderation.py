"""
apps.bot.handlers.group._moderation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Shared moderation utilities used by welcome.py, moderation.py.

Provides
--------
- is_chat_admin      — RBAC check with 60-second in-memory cache.
- try_delete         — Non-fatal message deletion.
- mute_user          — Restrict a user from sending messages.
- dm_log             — Fire-and-forget DM to BOT_ADMIN_USER_ID.
- incr_link_violations — Redis link-violation counter with in-memory fallback.
- is_flooding        — Sliding-window flood check via CacheClient.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import ChatPermissions, Message

from infrastructure.cache.client import get_redis
from infrastructure.cache.keys import CacheKeys, CacheTTL
from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)

# ── Admin cache ──────────────────────────────────────────────────────────────
# (chat_id, user_id) → (is_admin: bool, expires_monotonic: float)
_admin_cache: dict[tuple[int, int], tuple[bool, float]] = {}
_ADMIN_CACHE_TTL = 60.0  # seconds

_ADMIN_STATUSES: frozenset[str] = frozenset({
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.CREATOR,
})


async def is_chat_admin(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Return True if user_id is admin/creator in chat_id (60 s cache)."""
    now = time.monotonic()
    key = (chat_id, user_id)
    cached = _admin_cache.get(key)
    if cached is not None:
        val, expires_at = cached
        if now < expires_at:
            return val

    try:
        member = await bot.get_chat_member(chat_id, user_id)
        result = member.status in _ADMIN_STATUSES
    except Exception:
        log.warning("get_chat_member_failed", chat_id=chat_id, user_id=user_id)
        result = False

    _admin_cache[key] = (result, now + _ADMIN_CACHE_TTL)
    return result


# ── Message helpers ──────────────────────────────────────────────────────────


async def try_delete(message: Message) -> bool:
    """Delete *message*; return True on success. Never raises."""
    try:
        await message.delete()
        return True
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        log.warning("message_delete_failed", chat_id=message.chat.id, error=str(exc))
        return False


async def mute_user(bot: Bot, chat_id: int, user_id: int, seconds: int) -> bool:
    """Restrict *user_id* from sending messages for *seconds*. Returns True on success."""
    until = datetime.now(tz=timezone.utc) + timedelta(seconds=seconds)
    try:
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until,
        )
        return True
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        log.warning("mute_failed", chat_id=chat_id, user_id=user_id, error=str(exc))
        return False


async def dm_log(bot: Bot, text: str) -> None:
    """Send a DM to BOT_ADMIN_USER_ID. Non-fatal, intended for fire-and-forget."""
    settings = get_settings()
    admin_id = settings.bot.admin_user_id
    if not admin_id:
        return
    try:
        await bot.send_message(admin_id, text, parse_mode="HTML")
    except Exception as exc:
        log.warning("dm_log_failed", error=str(exc))


# ── Link violation counter ────────────────────────────────────────────────────
# In-memory fallback: (chat_id, user_id) → (count, first_monotonic_ts)
_link_violations: dict[tuple[int, int], tuple[int, float]] = {}


async def incr_link_violations(chat_id: int, user_id: int) -> int:
    """
    Increment the link-violation counter within a 10-minute window.
    Returns the new count. Falls back to an in-memory dict if Redis is unavailable.
    """
    key = CacheKeys.mod_link_violations(chat_id, user_id)
    try:
        redis = get_redis()
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, CacheTTL.MOD_LINK_WINDOW)
        return count
    except Exception:
        pass  # fall through to in-memory fallback

    now = time.monotonic()
    entry = _link_violations.get((chat_id, user_id))
    if entry is not None:
        count, first_ts = entry
        if now - first_ts > CacheTTL.MOD_LINK_WINDOW:
            count, first_ts = 0, now
    else:
        count, first_ts = 0, now
    count += 1
    _link_violations[(chat_id, user_id)] = (count, first_ts)
    return count


# ── Flood control (sliding window) ──────────────────────────────────────────
# In-memory fallback: (chat_id, user_id) → [monotonic_timestamps]
_flood_msgs: dict[tuple[int, int], list[float]] = {}
_FLOOD_WINDOW = 10   # seconds
_FLOOD_LIMIT  = 5    # max messages allowed inside the window


async def is_flooding(chat_id: int, user_id: int) -> bool:
    """
    Return True if user exceeds 5 messages in 10 seconds.
    Uses CacheClient sliding-window sorted set; falls back to in-memory.
    """
    identifier = f"flood:{chat_id}:{user_id}"
    try:
        redis = get_redis()
        allowed, _ = await redis.rate_limit_check(
            identifier=identifier,
            window_seconds=_FLOOD_WINDOW,
            max_requests=_FLOOD_LIMIT,
        )
        return not allowed
    except Exception:
        pass  # fall through to in-memory fallback

    now = time.monotonic()
    key = (chat_id, user_id)
    timestamps = [t for t in _flood_msgs.get(key, []) if now - t <= _FLOOD_WINDOW]
    timestamps.append(now)
    _flood_msgs[key] = timestamps
    return len(timestamps) > _FLOOD_LIMIT
