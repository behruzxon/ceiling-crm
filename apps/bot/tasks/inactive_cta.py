"""
apps.bot.tasks.inactive_cta
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Background asyncio task: sends a single CTA reminder to users who have been
inactive in private chat for 5 minutes, at most once per user per calendar day.

Lifecycle
---------
- start(bot)  — called from on_startup; creates the asyncio.Task
- stop()       — called from on_shutdown; cancels the task cleanly

Algorithm (runs every 60 seconds)
----------------------------------
1. Read the ``cta:user_activity`` Redis sorted set.
   Score = unix timestamp of last private activity.
   Members that scored between (now - 600) and (now - 300) are users who
   were last active 5–10 minutes ago.

2. For each such user_id:
   a. Skip if ``cta:sent:{user_id}:{today}`` key exists (sent already today).
   b. Look up the user in DB; skip non-CLIENT roles (admins, managers …).
   c. Send CTA via ``send_cta()``.
   d. Set ``cta:sent:{user_id}:{today}`` with TTL 2 days.
   e. Remove user from the sorted set (prevents rescanning on next tick).

3. Log total sent count for monitoring.

Safety notes
------------
- Never raises — all exceptions are caught and logged.
- asyncio.CancelledError propagates cleanly (not caught by ``except Exception``).
- Sends at most once per user per day.
- Skips non-CLIENT roles via DB lookup (rare; most users are clients).
"""
from __future__ import annotations

import asyncio
import datetime
import time
from asyncio import Task

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError

from apps.bot.ui.cta import send_cta
from infrastructure.cache.client import get_redis
from infrastructure.cache.keys import CacheKeys, CacheTTL
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_user_repo
from shared.logging import get_logger

log = get_logger(__name__)

_task: Task | None = None  # type: ignore[type-arg]

_CHECK_INTERVAL_SEC = 60       # how often the task wakes up
_INACTIVE_MIN_SEC   = 300      # 5 min — minimum inactivity before CTA
_INACTIVE_MAX_SEC   = 600      # 10 min — maximum inactivity window to scan


# ── Core loop ──────────────────────────────────────────────────────────────────


async def _run(bot: Bot) -> None:
    while True:
        # Sleeps 60 s between scans; CancelledError propagates on stop()
        await asyncio.sleep(_CHECK_INTERVAL_SEC)

        try:
            redis = get_redis()
            now = int(time.time())
            today = datetime.date.today().isoformat()

            # Members inactive between 5 and 10 minutes ago
            candidates: list[str] = await redis.zrangebyscore(
                CacheKeys.cta_user_activity(),
                now - _INACTIVE_MAX_SEC,
                now - _INACTIVE_MIN_SEC,
            )

            if not candidates:
                continue

            sent_count = 0
            for uid_str in candidates:
                try:
                    user_id = int(uid_str)
                except ValueError:
                    continue

                # 1. Dedup: skip if already sent today
                if await redis.exists(CacheKeys.cta_sent(user_id, today)):
                    # Still remove from sorted set so we don't re-scan it
                    await redis.zrem(CacheKeys.cta_user_activity(), uid_str)
                    continue

                # 2. Role check via DB (lightweight — happens only once per day per user)
                try:
                    factory = get_session_factory()
                    async with factory() as session:
                        user_repo = get_user_repo(session)
                        db_user = await user_repo.get_by_id(user_id)
                except Exception:
                    log.exception("inactive_cta_db_error", user_id=user_id)
                    continue

                if db_user is None or db_user.role.value != "client":
                    # Non-client — remove from set, no CTA needed
                    await redis.zrem(CacheKeys.cta_user_activity(), uid_str)
                    continue

                # 3. Send CTA (TelegramForbiddenError = user blocked bot — skip quietly)
                try:
                    await send_cta(bot, user_id, reason="inactive_5m")
                except TelegramForbiddenError:
                    log.info("inactive_cta_bot_blocked", user_id=user_id)
                    await redis.zrem(CacheKeys.cta_user_activity(), uid_str)
                    continue
                except Exception:
                    log.exception("inactive_cta_send_error", user_id=user_id)
                    continue

                # 4. Mark sent with 2-day TTL
                await redis.set(
                    CacheKeys.cta_sent(user_id, today),
                    "1",
                    ttl=CacheTTL.CTA_SENT,
                )

                # 5. Remove from sorted set (processed)
                await redis.zrem(CacheKeys.cta_user_activity(), uid_str)
                sent_count += 1

            if sent_count:
                log.info("inactive_cta_sent", count=sent_count)

        except Exception:
            log.exception("inactive_cta_loop_error")


# ── Public API ─────────────────────────────────────────────────────────────────


def start(bot: Bot) -> None:
    """Create and register the background inactive-CTA task."""
    global _task
    _task = asyncio.create_task(_run(bot), name="inactive_cta")
    log.info("inactive_cta_task_started")


def stop() -> None:
    """Cancel the background task on bot shutdown."""
    global _task
    if _task and not _task.done():
        _task.cancel()
        log.info("inactive_cta_task_cancelled")
    _task = None
