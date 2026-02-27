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
     - Terminal error (chat not found / bot blocked / forbidden):
         mark users.is_blocked = true, count as failed, continue.
     - Other error: count as failed, continue.
  5. Update counters (batched every 50 sends).
  6. Finalize: set finished_at + mark DONE (or FAILED on exception).

Throttling: 1 / BROADCAST_RATE_LIMIT seconds per message.

Engine lifetime
---------------
asyncio.run() creates a new event loop, runs the coroutine, then **closes**
the loop.  A global singleton engine (like the one in session.py) would have
its asyncpg connection pool bound to that dead loop, causing
    RuntimeError: Event loop is closed
on the next task.  Therefore each top-level coroutine creates its own
AsyncEngine and disposes it in a finally block.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import sqlalchemy as sa
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from infrastructure.database.models.user import UserModel
from infrastructure.database.repositories.admin_group_repo import PostgresAdminGroupRepository
from infrastructure.database.repositories.broadcast_repo import PostgresBroadcastRepository
from infrastructure.queue.app import celery_app
from shared.config import get_settings
from shared.constants.enums import BroadcastStatus, PayloadType, SegmentType
from shared.logging import get_logger

log = get_logger(__name__)

_COUNTER_BATCH = 50  # flush counters to DB every N sends

# ── Terminal-error detection ───────────────────────────────────────────────────
# Lowercase substrings that identify a permanently unreachable chat.
# TelegramForbiddenError (403) is always terminal.
# Specific TelegramBadRequest (400) messages are listed here.
_BLOCK_PHRASES: frozenset[str] = frozenset({
    "chat not found",
    "bot was blocked by the user",
    "user is deactivated",
    "have no rights to send a message",
    "group chat was upgraded to a supergroup chat",
})


def _is_terminal_error(exc: Exception) -> bool:
    """Return True when the error means this chat_id is permanently unreachable."""
    if isinstance(exc, TelegramForbiddenError):
        return True
    msg = str(exc).lower()
    return any(phrase in msg for phrase in _BLOCK_PHRASES)


# ── Local session helpers ──────────────────────────────────────────────────────
# These helpers accept a caller-supplied session factory instead of using the
# global singleton from session.py, so they are safe to call inside asyncio.run().


@asynccontextmanager
async def _rw_session(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Read-write session: commits on success, rolls back on error."""
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def _ro_session(
    factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """Read-only session: never commits."""
    async with factory() as session:
        try:
            yield session
        finally:
            await session.rollback()
            await session.close()


def _make_session_factory() -> tuple[object, async_sessionmaker[AsyncSession]]:
    """
    Create a fresh AsyncEngine + session factory bound to the *current* event
    loop.  Callers must call ``await engine.dispose()`` when done.
    """
    settings = get_settings()
    engine = create_async_engine(
        settings.db.async_url,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=2,
        connect_args={
            "server_settings": {"jit": "off"},
            "command_timeout": 60,
        },
    )
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    return engine, factory


# ── Auto-block helper ──────────────────────────────────────────────────────────


async def _auto_block_chat(
    chat_id: int,
    factory: async_sessionmaker[AsyncSession],
) -> None:
    """Set users.is_blocked = true for *chat_id* and commit.

    Only acts on positive IDs (private users).  Groups / channels (id <= 0)
    live in admin_groups, not in users, so they are skipped silently.

    Never raises — a failure to auto-block is logged at WARNING level so the
    broadcast loop is never interrupted by a secondary DB error.
    """
    if chat_id <= 0:
        return
    try:
        async with _rw_session(factory) as session:
            await session.execute(
                sa.update(UserModel)
                .where(UserModel.id == chat_id)
                .values(is_blocked=True, updated_at=datetime.now(timezone.utc))
            )
        log.info("broadcast_user_auto_blocked", chat_id=chat_id)
    except Exception as block_exc:
        log.warning(
            "broadcast_auto_block_failed",
            chat_id=chat_id,
            error=str(block_exc),
        )


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
    """Mark a broadcast as FAILED.  Creates its own engine so it is safe
    to call from a fresh asyncio.run() context."""
    engine, Session = _make_session_factory()
    try:
        async with _rw_session(Session) as session:
            repo = PostgresBroadcastRepository(session)
            await repo.mark_status(broadcast_id, BroadcastStatus.FAILED)
    finally:
        await engine.dispose()


async def _async_process_broadcast(broadcast_id: int) -> dict:
    """Full async broadcast pipeline.

    Creates a dedicated AsyncEngine for this invocation so the connection
    pool is always bound to the current event loop (never a closed one).
    """
    settings = get_settings()
    rate_limit: int = settings.business.broadcast_rate_limit or 30
    sleep_per_msg: float = 1.0 / rate_limit

    # Fresh engine — bound to the current event loop created by asyncio.run().
    engine, Session = _make_session_factory()

    try:
        # 1. Load broadcast
        async with _ro_session(Session) as session:
            repo = PostgresBroadcastRepository(session)
            broadcast = await repo.get_by_id(broadcast_id)

        if broadcast is None:
            log.warning("broadcast_not_found", broadcast_id=broadcast_id)
            return {"status": "not_found"}

        if broadcast.status not in (BroadcastStatus.PENDING.value, BroadcastStatus.SCHEDULED.value):
            log.info(
                "broadcast_skip_non_pending",
                broadcast_id=broadcast_id,
                status=broadcast.status,
            )
            return {"status": "skipped", "reason": broadcast.status}

        # 2. Mark RUNNING
        async with _rw_session(Session) as session:
            repo = PostgresBroadcastRepository(session)
            await repo.mark_status(broadcast_id, BroadcastStatus.RUNNING)

        log.info("broadcast_started", broadcast_id=broadcast_id)

        # 3. Resolve targets
        seg_type = broadcast.segment_type

        async with _ro_session(Session) as session:
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
                success = await _send_one(bot, broadcast, chat_id, sleep_per_msg, Session)
                if success:
                    sent += 1
                else:
                    failed += 1

                # Flush counters to DB every COUNTER_BATCH sends
                if (sent + failed) % _COUNTER_BATCH == 0:
                    async with _rw_session(Session) as session:
                        repo = PostgresBroadcastRepository(session)
                        await repo.inc_sent(broadcast_id, sent)
                        await repo.inc_failed(broadcast_id, failed)
                    sent = 0
                    failed = 0

        finally:
            await bot.session.close()

        # 5. Final counter flush + finalize
        async with _rw_session(Session) as session:
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

    finally:
        await engine.dispose()


async def _send_one(
    bot: Bot,
    broadcast,
    chat_id: int,
    sleep_after: float,
    factory: async_sessionmaker[AsyncSession],
) -> bool:
    """Send one message to one chat.  Returns True on success, False on failure.

    On terminal Telegram errors ("chat not found", "bot was blocked by the
    user", any 403 Forbidden) the user row is automatically marked
    ``is_blocked = true`` via ``_auto_block_chat`` before returning False.
    The broadcast loop is never interrupted — all errors are caught here.
    """
    payload_type = broadcast.payload_type
    text = broadcast.text or ""
    file_id = broadcast.file_id

    async def _do_send() -> None:
        """Inner helper — performs the actual Telegram API call."""
        if payload_type == PayloadType.TEXT.value:
            await bot.send_message(chat_id, text)
        elif payload_type == PayloadType.PHOTO.value and file_id:
            await bot.send_photo(chat_id, file_id, caption=text or None)
        elif payload_type == PayloadType.VIDEO.value and file_id:
            await bot.send_video(chat_id, file_id, caption=text or None)
        elif payload_type == PayloadType.DOCUMENT.value and file_id:
            await bot.send_document(chat_id, file_id, caption=text or None)
        else:
            # Fallback: send as plain text if available
            if text:
                await bot.send_message(chat_id, text)
            else:
                log.warning("broadcast_no_content", chat_id=chat_id)
                raise ValueError("no content to send")

    try:
        await _do_send()
        await asyncio.sleep(sleep_after)
        return True

    except TelegramRetryAfter as exc:
        log.warning(
            "broadcast_retry_after",
            chat_id=chat_id,
            retry_after=exc.retry_after,
        )
        await asyncio.sleep(exc.retry_after + 0.5)
        # Retry once after the requested back-off.
        try:
            await _do_send()
            await asyncio.sleep(sleep_after)
            return True
        except Exception as retry_exc:
            if _is_terminal_error(retry_exc):
                await _auto_block_chat(chat_id, factory)
                log.info(
                    "broadcast_terminal_error_on_retry",
                    chat_id=chat_id,
                    error=str(retry_exc),
                )
            else:
                log.error(
                    "broadcast_retry_failed",
                    chat_id=chat_id,
                    error=str(retry_exc),
                )
            return False

    except TelegramForbiddenError as exc:
        # 403 — bot was blocked by the user, or was kicked from the chat.
        await _auto_block_chat(chat_id, factory)
        log.info("broadcast_forbidden", chat_id=chat_id, error=str(exc))
        return False

    except Exception as exc:
        if _is_terminal_error(exc):
            # "chat not found", "user is deactivated", etc.
            await _auto_block_chat(chat_id, factory)
            log.info(
                "broadcast_terminal_error",
                chat_id=chat_id,
                error=str(exc),
            )
        else:
            log.error("broadcast_send_error", chat_id=chat_id, error=str(exc))
        return False
