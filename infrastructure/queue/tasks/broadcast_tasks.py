"""
Celery tasks for broadcast message delivery.

Worker flow
-----------
process_broadcast_batch(broadcast_id)
  1. Load broadcast from DB; bail early if not PENDING/SCHEDULED.
  2. Mark status → RUNNING.
  3. Resolve target chat IDs:
       ALL_PRIVATE  → all non-blocked users
       LEAD_STAGE   → users with matching latest pipeline stage
       ADMIN_GROUPS → admin_groups table only
  4. Send each message (text / photo / video / document).
     - RetryAfter: sleep then retry once.
     - Forbidden:  user blocked the bot; count as failed, continue.
  5. Update counters (batched every 50 sends).
  6. Finalize: set finished_at + mark DONE (or FAILED on exception).

Throttling: 1 / BROADCAST_RATE_LIMIT seconds per message.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from infrastructure.database.repositories.admin_group_repo import PostgresAdminGroupRepository
from infrastructure.database.repositories.broadcast_repo import PostgresBroadcastRepository
from infrastructure.database.session import get_readonly_session, get_session
from infrastructure.queue.app import celery_app
from shared.config import get_settings
from shared.constants.enums import BroadcastStatus, PayloadType, SegmentType
from shared.logging import get_logger

log = get_logger(__name__)

_COUNTER_BATCH = 50  # flush counters to DB every N sends


# ── Celery entry points ────────────────────────────────────────────────────────


@celery_app.task(bind=True, max_retries=0, name="broadcast.process_batch")
def process_broadcast_batch(self, broadcast_id: int) -> dict:
    """
    Process a full broadcast.  Runs synchronously inside Celery worker
    and delegates async work to asyncio.run().
    """
    try:
        result = asyncio.run(_async_process_broadcast(broadcast_id))
        return result
    except Exception as exc:
        log.error("broadcast_task_failed", broadcast_id=broadcast_id, error=str(exc))
        # Best-effort status update
        try:
            asyncio.run(_mark_failed(broadcast_id))
        except Exception:
            pass
        raise


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60,
                 name="broadcast.send_single")
def send_broadcast_message(self, user_id: int, broadcast_id: int, message: str) -> dict:
    """Legacy single-send task (kept for backward compat). TODO: remove."""
    raise NotImplementedError


# ── async implementation ───────────────────────────────────────────────────────


async def _mark_failed(broadcast_id: int) -> None:
    async with get_session() as session:
        repo = PostgresBroadcastRepository(session)
        await repo.mark_status(broadcast_id, BroadcastStatus.FAILED)


async def _async_process_broadcast(broadcast_id: int) -> dict:
    """Full async broadcast pipeline."""
    settings = get_settings()
    rate_limit: int = settings.business.broadcast_rate_limit or 30
    sleep_per_msg: float = 1.0 / rate_limit

    # 1. Load broadcast
    async with get_readonly_session() as session:
        repo = PostgresBroadcastRepository(session)
        broadcast = await repo.get_by_id(broadcast_id)

    if broadcast is None:
        log.warning("broadcast_not_found", broadcast_id=broadcast_id)
        return {"status": "not_found"}

    if broadcast.status not in (BroadcastStatus.PENDING.value, BroadcastStatus.SCHEDULED.value):
        log.info("broadcast_skip_non_pending", broadcast_id=broadcast_id, status=broadcast.status)
        return {"status": "skipped", "reason": broadcast.status}

    # 2. Mark RUNNING
    async with get_session() as session:
        repo = PostgresBroadcastRepository(session)
        await repo.mark_status(broadcast_id, BroadcastStatus.RUNNING)

    log.info("broadcast_started", broadcast_id=broadcast_id)

    # 3. Resolve targets
    seg_type = broadcast.segment_type

    async with get_readonly_session() as session:
        bcast_repo = PostgresBroadcastRepository(session)
        ag_repo = PostgresAdminGroupRepository(session)

        if seg_type == SegmentType.ALL_PRIVATE.value:
            user_ids = await bcast_repo.get_all_private_user_ids()
            group_ids = await ag_repo.list_all_chat_ids()
        elif seg_type == SegmentType.LEAD_STAGE.value:
            lead_stage = broadcast.lead_stage or ""
            user_ids = await bcast_repo.get_user_ids_by_stage(lead_stage)
            group_ids = []
        else:  # ADMIN_GROUPS
            user_ids = []
            group_ids = await ag_repo.list_all_chat_ids()

    all_chat_ids: list[int] = user_ids + group_ids
    total = len(all_chat_ids)
    log.info("broadcast_targets_resolved", broadcast_id=broadcast_id, total=total)

    # 4. Create bot
    bot = Bot(
        token=settings.bot.token.get_secret_value(),
        default=DefaultBotProperties(parse_mode="HTML"),
    )

    sent = 0
    failed = 0

    try:
        for chat_id in all_chat_ids:
            success = await _send_one(bot, broadcast, chat_id, sleep_per_msg)
            if success:
                sent += 1
            else:
                failed += 1

            # Flush counters to DB every COUNTER_BATCH sends
            if (sent + failed) % _COUNTER_BATCH == 0:
                async with get_session() as session:
                    repo = PostgresBroadcastRepository(session)
                    await repo.inc_sent(broadcast_id, sent)
                    await repo.inc_failed(broadcast_id, failed)
                sent = 0
                failed = 0

    finally:
        await bot.session.close()

    # 5. Final counter flush + finalize
    async with get_session() as session:
        repo = PostgresBroadcastRepository(session)
        if sent or failed:
            await repo.inc_sent(broadcast_id, sent)
            await repo.inc_failed(broadcast_id, failed)
        await repo.finalize(broadcast_id, datetime.now(timezone.utc))
        await repo.mark_status(broadcast_id, BroadcastStatus.DONE)

    log.info(
        "broadcast_completed",
        broadcast_id=broadcast_id,
        sent=sent,
        failed=failed,
        total=total,
    )
    return {"status": "done", "sent": sent, "failed": failed, "total": total}


async def _send_one(bot: Bot, broadcast, chat_id: int, sleep_after: float) -> bool:
    """Send one message to one chat.  Returns True on success, False on failure."""
    payload_type = broadcast.payload_type
    text = broadcast.text or ""
    file_id = broadcast.file_id

    try:
        if payload_type == PayloadType.TEXT.value:
            await bot.send_message(chat_id, text)
        elif payload_type == PayloadType.PHOTO.value and file_id:
            await bot.send_photo(chat_id, file_id, caption=text or None)
        elif payload_type == PayloadType.VIDEO.value and file_id:
            await bot.send_video(chat_id, file_id, caption=text or None)
        elif payload_type == PayloadType.DOCUMENT.value and file_id:
            await bot.send_document(chat_id, file_id, caption=text or None)
        else:
            # Fallback: try send_message with whatever text we have
            if text:
                await bot.send_message(chat_id, text)
            else:
                log.warning("broadcast_no_content", chat_id=chat_id)
                return False

        await asyncio.sleep(sleep_after)
        return True

    except TelegramRetryAfter as exc:
        log.warning(
            "broadcast_retry_after",
            chat_id=chat_id,
            retry_after=exc.retry_after,
        )
        await asyncio.sleep(exc.retry_after + 0.5)
        # Retry once
        try:
            if payload_type == PayloadType.TEXT.value:
                await bot.send_message(chat_id, text)
            elif payload_type == PayloadType.PHOTO.value and file_id:
                await bot.send_photo(chat_id, file_id, caption=text or None)
            elif payload_type == PayloadType.VIDEO.value and file_id:
                await bot.send_video(chat_id, file_id, caption=text or None)
            elif payload_type == PayloadType.DOCUMENT.value and file_id:
                await bot.send_document(chat_id, file_id, caption=text or None)
            await asyncio.sleep(sleep_after)
            return True
        except Exception as retry_exc:
            log.error("broadcast_retry_failed", chat_id=chat_id, error=str(retry_exc))
            return False

    except TelegramForbiddenError:
        # User blocked the bot — expected, count as failed and move on
        log.debug("broadcast_forbidden", chat_id=chat_id)
        return False

    except Exception as exc:
        log.error("broadcast_send_error", chat_id=chat_id, error=str(exc))
        return False
