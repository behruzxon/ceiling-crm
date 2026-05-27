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
import dataclasses
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import sqlalchemy as sa
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from infrastructure.database.models.user import UserModel
from infrastructure.database.repositories.admin_group_repo import PostgresAdminGroupRepository
from infrastructure.database.repositories.blocked_chat_repo import PostgresBlockedChatRepository
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
_BLOCK_PHRASES: frozenset[str] = frozenset(
    {
        "chat not found",
        "bot was blocked by the user",
        "user is deactivated",
        "have no rights to send a message",
        "group chat was upgraded to a supergroup chat",
    }
)


def _is_terminal_error(exc: Exception) -> bool:
    """Return True when the error means this chat_id is permanently unreachable."""
    if isinstance(exc, TelegramForbiddenError):
        return True
    msg = str(exc).lower()
    return any(phrase in msg for phrase in _BLOCK_PHRASES)


def _classify_error(exc: Exception) -> str:
    """Classify a send failure into one of three stat buckets.

    Returns one of: ``"blocked"`` | ``"forbidden"`` | ``"other"``.

    Priority order:
    1. "bot was blocked by the user" in message → blocked
    2. TelegramForbiddenError (403) or known forbidden phrases → forbidden
    3. Anything else → other
    """
    msg = str(exc).lower()
    if "bot was blocked by the user" in msg:
        return "blocked"
    if isinstance(exc, TelegramForbiddenError):
        return "forbidden"
    if any(p in msg for p in ("forbidden", "not enough rights", "chat not found", "kicked")):
        return "forbidden"
    return "other"


@dataclasses.dataclass
class _Stats:
    """In-memory stats accumulator for a single broadcast run.

    Passed through the send loop and serialised into the admin DM report
    after the broadcast completes.
    """

    broadcast_id: int
    started_at: datetime

    # Targets (by chat type — negative id = group/supergroup)
    users_total: int = 0
    groups_total: int = 0

    # Successful deliveries
    users_sent: int = 0
    groups_sent: int = 0

    # Failure breakdown
    failed_blocked: int = 0  # bot was blocked by the user
    failed_forbidden: int = 0  # forbidden / kicked / no rights / chat not found
    failed_other: int = 0  # network, timeout, unexpected errors

    # Operational counters
    retry_count: int = 0  # number of TelegramRetryAfter back-offs triggered
    batch_count: int = 0  # number of DB counter-flush operations performed

    # Auto-clean counters
    newly_blocked: int = 0  # chat IDs added to blocked_chats this run
    skipped_by_blocklist: int = 0  # targets excluded at resolution time

    finished_at: datetime | None = None

    # ── Computed ─────────────────────────────────────────────────────────────

    @property
    def total_targets(self) -> int:
        return self.users_total + self.groups_total

    @property
    def failed_total(self) -> int:
        return self.failed_blocked + self.failed_forbidden + self.failed_other

    @property
    def duration_seconds(self) -> float:
        if self.finished_at is None:
            return 0.0
        return round((self.finished_at - self.started_at).total_seconds(), 1)


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
                .values(is_blocked=True, updated_at=datetime.now(UTC))
            )
        log.info("broadcast_user_auto_blocked", chat_id=chat_id)
    except Exception as block_exc:
        log.warning(
            "broadcast_auto_block_failed",
            chat_id=chat_id,
            error=str(block_exc),
        )


# ── Blocked-chat persistence helper ───────────────────────────────────────────


async def _upsert_blocked_chat(
    chat_id: int,
    reason: str,
    factory: async_sessionmaker[AsyncSession],
) -> bool:
    """Upsert *chat_id* into blocked_chats and return True if newly inserted.

    Works for both private users (chat_id > 0) and groups (chat_id < 0).
    Never raises — a DB failure is logged at WARNING level so it never
    interrupts the broadcast loop.
    """
    try:
        async with _rw_session(factory) as session:
            repo = PostgresBlockedChatRepository(session)
            return await repo.upsert_block(chat_id, reason)
    except Exception:
        log.warning("blocked_chat_upsert_failed", chat_id=chat_id, reason=reason)
        return False


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


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, name="broadcast.send_single")
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
                group_ids = []  # private-only: no groups
            elif seg_type == SegmentType.LEAD_STAGE.value:
                lead_stage = broadcast.lead_stage or ""
                user_ids = await bcast_repo.get_user_ids_by_stage(lead_stage)
                group_ids = []
            else:  # ADMIN_GROUPS
                user_ids = []
                group_ids = await ag_repo.list_all_chat_ids()

        # Ensure main_group_id is included in ADMIN_GROUPS broadcasts even if
        # it was never upserted into admin_groups via the tracker.
        main_group_id = settings.bot.main_group_id
        if main_group_id and seg_type == SegmentType.ADMIN_GROUPS.value:
            if main_group_id not in group_ids:
                group_ids.append(main_group_id)

        all_chat_ids: list[int] = user_ids + group_ids

        # Filter out permanently blocked chats so we never waste API calls on
        # them.  LEAD_STAGE and ADMIN_GROUPS are intentionally skipped:
        #   - LEAD_STAGE: qualified leads must not be silently dropped.
        #   - ADMIN_GROUPS: targets are fetched directly from admin_groups
        #     table; applying the blocklist would hide valid groups whose
        #     IDs were added to blocked_chats after a transient send error.
        skipped_by_blocklist = 0
        if seg_type == SegmentType.ALL_PRIVATE.value and all_chat_ids:
            async with _ro_session(Session) as session:
                block_repo = PostgresBlockedChatRepository(session)
                allowed = await block_repo.bulk_filter_blocked(all_chat_ids)
                skipped_by_blocklist = len(all_chat_ids) - len(allowed)
                all_chat_ids = allowed

        total = len(all_chat_ids)
        log.info(
            "broadcast_targets_resolved",
            broadcast_id=broadcast_id,
            total=total,
            skipped_blocked=skipped_by_blocklist,
        )

        # 4. Create bot
        bot = Bot(
            token=settings.bot.token.get_secret_value(),
            default=DefaultBotProperties(parse_mode="HTML"),
        )

        # ── Per-broadcast stats ───────────────────────────────────────────────
        stats = _Stats(
            broadcast_id=broadcast_id,
            started_at=datetime.now(UTC),
            users_total=sum(1 for cid in all_chat_ids if cid > 0),
            groups_total=sum(1 for cid in all_chat_ids if cid <= 0),
            skipped_by_blocklist=skipped_by_blocklist,
        )

        sent = 0
        failed = 0

        try:
            for chat_id in all_chat_ids:
                result_code, retried = await _send_one(
                    bot, broadcast, chat_id, sleep_per_msg, Session
                )
                if retried:
                    stats.retry_count += 1

                is_group = chat_id < 0
                if result_code == "ok":
                    if is_group:
                        stats.groups_sent += 1
                    else:
                        stats.users_sent += 1
                    sent += 1
                else:
                    if result_code == "blocked":
                        stats.failed_blocked += 1
                    elif result_code == "forbidden":
                        stats.failed_forbidden += 1
                    else:
                        stats.failed_other += 1
                    failed += 1

                    # Persist permanent failures to blocked_chats so they are
                    # excluded from future broadcasts automatically.
                    # Transient "other" errors (network, timeout) are also
                    # recorded so repeated soft failures accumulate a seen_count.
                    is_new = await _upsert_blocked_chat(chat_id, result_code, Session)
                    if is_new:
                        stats.newly_blocked += 1

                # Flush counters to DB every COUNTER_BATCH sends
                if (sent + failed) % _COUNTER_BATCH == 0:
                    stats.batch_count += 1
                    async with _rw_session(Session) as session:
                        repo = PostgresBroadcastRepository(session)
                        await repo.inc_sent(broadcast_id, sent)
                        await repo.inc_failed(broadcast_id, failed)
                    sent = 0
                    failed = 0

        finally:
            await bot.session.close()

        # 5. Final counter flush + finalize
        now_done = datetime.now(UTC)
        stats.finished_at = now_done

        async with _rw_session(Session) as session:
            repo = PostgresBroadcastRepository(session)
            if sent or failed:
                await repo.inc_sent(broadcast_id, sent)
                await repo.inc_failed(broadcast_id, failed)
            await repo.finalize(broadcast_id, now_done)
            await repo.mark_status(broadcast_id, BroadcastStatus.DONE)

        log.info(
            "broadcast_completed",
            broadcast_id=broadcast_id,
            sent=stats.users_sent + stats.groups_sent,
            failed=stats.failed_total,
            total=total,
        )

        # 6. Send final statistics report to admin DM only
        admin_user_id = settings.bot.admin_user_id
        if admin_user_id:
            await _send_admin_report(
                stats=stats,
                bot_token=settings.bot.token.get_secret_value(),
                admin_user_id=admin_user_id,
            )
        else:
            log.warning(
                "broadcast_report_skipped_no_admin_id",
                broadcast_id=broadcast_id,
            )

        return {
            "status": "done",
            "sent": stats.users_sent + stats.groups_sent,
            "failed": stats.failed_total,
            "total": total,
        }

    finally:
        await engine.dispose()


async def _send_one(
    bot: Bot,
    broadcast,
    chat_id: int,
    sleep_after: float,
    factory: async_sessionmaker[AsyncSession],
) -> tuple[str, bool]:
    """Send one message to one chat.

    Returns ``(result_code, retried)`` where:
    - *result_code*: ``"ok"`` | ``"blocked"`` | ``"forbidden"`` | ``"other"``
    - *retried*:     ``True`` if a ``TelegramRetryAfter`` back-off was triggered.

    On terminal Telegram errors the user row is automatically marked
    ``is_blocked = true`` via ``_auto_block_chat``.
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
        return "ok", False

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
            return "ok", True
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
            return _classify_error(retry_exc), True

    except TelegramForbiddenError as exc:
        # 403 — bot was blocked by the user, or was kicked from the chat.
        await _auto_block_chat(chat_id, factory)
        log.info("broadcast_forbidden", chat_id=chat_id, error=str(exc))
        return _classify_error(exc), False

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
        return _classify_error(exc), False


# ── Admin DM report ────────────────────────────────────────────────────────────


async def _send_admin_report(
    stats: _Stats,
    bot_token: str,
    admin_user_id: int,
) -> None:
    """Send a final broadcast statistics report to the admin's private DM.

    Creates a short-lived Bot instance — safe to call from inside asyncio.run().
    Never raises: a failure is logged at WARNING level so it never masks
    the broadcast's own success status.
    """
    text = (
        f"✅ Rassilka #{stats.broadcast_id} yakunlandi\n\n"
        f"🎯 Total targets: {stats.total_targets}\n\n"
        f"👤 Userlar: {stats.users_sent}/{stats.users_total}\n"
        f"👥 Guruhlar: {stats.groups_sent}/{stats.groups_total}\n\n"
        f"❌ Yuborilmadi: {stats.failed_total}\n"
        f"   🚫 Blocked: {stats.failed_blocked}\n"
        f"   ⛔ Forbidden: {stats.failed_forbidden}\n"
        f"   ⚠️ Other: {stats.failed_other}\n\n"
        f"📦 Batchlar: {stats.batch_count}\n"
        f"🔁 Retry urinishlar: {stats.retry_count}\n"
        f"⏱ Davomiyligi: {stats.duration_seconds} sec\n\n"
        f"🧹 Auto-blocked (new): {stats.newly_blocked}\n"
        f"🚫 Skipped (already blocked): {stats.skipped_by_blocklist}"
    )

    bot = Bot(token=bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    try:
        await bot.send_message(admin_user_id, text)
        log.info(
            "broadcast_admin_report_sent",
            broadcast_id=stats.broadcast_id,
            admin_user_id=admin_user_id,
        )
    except Exception:
        log.warning(
            "broadcast_admin_report_failed",
            broadcast_id=stats.broadcast_id,
            admin_user_id=admin_user_id,
        )
    finally:
        await bot.session.close()
