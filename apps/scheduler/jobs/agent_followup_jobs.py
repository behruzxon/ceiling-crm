"""APScheduler job: process due agent follow-ups every 60 seconds."""
from __future__ import annotations

from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from shared.logging import get_logger

log = get_logger(__name__)


def register_agent_followup_jobs(scheduler: AsyncIOScheduler) -> None:
    scheduler.add_job(
        process_agent_followups,
        trigger="interval",
        seconds=60,
        id="process_agent_followups",
        replace_existing=True,
    )


async def _redis_pre_check(user_id: int, fu_type: str) -> tuple[bool, str]:
    """Optional Redis-layer anti-spam. Returns (allowed, reason).

    If Redis is unavailable the check passes (DB fallback in should_send).
    """
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys

        redis = get_redis()

        # Min-gap check
        last_key = CacheKeys.agent_fu_last(user_id)
        if await redis.get(last_key):
            return False, "redis_min_gap"

        # Per-type dedup
        dedup_key = CacheKeys.agent_fu_dedup(user_id, fu_type)
        if await redis.get(dedup_key):
            return False, "redis_dedup"

        # Daily counter
        daily_key = CacheKeys.agent_fu_daily(user_id)
        daily_raw = await redis.get(daily_key)
        if daily_raw and int(daily_raw) >= 3:
            return False, "redis_daily_cap"

        return True, "ok"
    except Exception:
        return True, "redis_unavailable"


async def _redis_post_send(user_id: int, fu_type: str) -> None:
    """Record the send in Redis for dedup/cooldown. Best-effort."""
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys, CacheTTL

        redis = get_redis()

        await redis.set(
            CacheKeys.agent_fu_last(user_id), "1",
            ttl=CacheTTL.AGENT_FU_LAST_SENT,
        )

        ttl_map = {
            "catalog": CacheTTL.AGENT_FU_CATALOG,
            "price": CacheTTL.AGENT_FU_PRICE,
            "abandoned_order": CacheTTL.AGENT_FU_ORDER,
        }
        dedup_ttl = ttl_map.get(fu_type, CacheTTL.AGENT_FU_CATALOG)
        await redis.set(
            CacheKeys.agent_fu_dedup(user_id, fu_type), "1",
            ttl=dedup_ttl, nx=True,
        )

        daily_key = CacheKeys.agent_fu_daily(user_id)
        await redis.incr(daily_key)
        await redis.expire(daily_key, CacheTTL.AGENT_FU_DAILY_COUNT)
    except Exception:
        log.warning("redis_post_send_failed", user_id=user_id)


async def process_agent_followups() -> None:
    """Query due follow-ups and send them if all conditions pass."""
    try:
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

        from core.services.agent_memory_service import AgentMemoryService
        from core.services.followup_scheduler_service import FollowupSchedulerService
        from infrastructure.database.session import get_session_factory
        from shared.config import get_settings
        from shared.utils.business_hours import defer_to_business_hours, is_off_hours

        settings = get_settings()
        if not settings.business.agent_followups_enabled:
            return

        bot_token = settings.bot.token.get_secret_value()

        factory = get_session_factory()
        async with factory() as session:
            fu_svc = FollowupSchedulerService(session)
            mem_svc = AgentMemoryService(session)
            now = datetime.now(UTC)

            due_list = await fu_svc.get_due(now, limit=20)
            if not due_list:
                return

            # Off-hours: reschedule all due items to next morning
            if is_off_hours():
                for fu in due_list:
                    next_time = defer_to_business_hours(now)
                    await fu_svc.reschedule(fu.id, next_time)
                await session.commit()
                log.info("agent_followups_deferred", count=len(due_list))
                return

            bot = Bot(token=bot_token, default=DefaultBotProperties(parse_mode="HTML"))
            sent = 0
            try:
                for fu in due_list:
                    try:
                        mem = await mem_svc.get_or_create(fu.telegram_user_id)
                        ok, reason = await fu_svc.should_send(fu, mem)
                        if not ok:
                            await fu_svc.mark_skipped(fu.id, reason)
                            continue

                        # Redis anti-spam layer
                        redis_ok, redis_reason = await _redis_pre_check(
                            fu.telegram_user_id, fu.followup_type,
                        )
                        if not redis_ok:
                            await fu_svc.mark_skipped(fu.id, redis_reason)
                            continue

                        mem_dict = {
                            "full_name": mem.full_name,
                            "interested_designs": mem.interested_designs,
                            "area_m2": mem.area_m2,
                            "ceiling_type": mem.ceiling_type,
                            "estimated_price": mem.estimated_price,
                            "phone_masked": mem.phone_masked,
                            "district": mem.district,
                        }
                        text, buttons = await FollowupSchedulerService.build_message_ai(
                            fu.followup_type, memory_data=mem_dict,
                        )
                        if not text:
                            await fu_svc.mark_skipped(fu.id, "no_template")
                            continue

                        kb = None
                        if buttons:
                            rows = [
                                [InlineKeyboardButton(text=label, callback_data=cb)]
                                for label, cb in buttons
                            ]
                            kb = InlineKeyboardMarkup(inline_keyboard=rows)

                        await bot.send_message(
                            chat_id=fu.telegram_user_id,
                            text=text,
                            reply_markup=kb,
                        )

                        await fu_svc.mark_sent(fu.id, text)
                        await mem_svc.mark_followup_sent(fu.telegram_user_id)
                        await _redis_post_send(fu.telegram_user_id, fu.followup_type)
                        sent += 1

                    except Exception as exc:
                        exc_name = type(exc).__name__
                        if "Forbidden" in exc_name:
                            await fu_svc.mark_failed(fu.id, "user_blocked")
                            await mem_svc.disable_followup(
                                fu.telegram_user_id, "blocked",
                            )
                        elif "RetryAfter" in exc_name:
                            log.warning(
                                "followup_rate_limited",
                                user_id=fu.telegram_user_id,
                            )
                            break
                        else:
                            await fu_svc.mark_failed(fu.id, exc_name[:500])
                            log.warning(
                                "followup_send_error",
                                user_id=fu.telegram_user_id,
                                error=exc_name,
                            )

                await session.commit()
            finally:
                await bot.session.close()

            if sent:
                log.info("agent_followups_sent", count=sent)
    except Exception:
        log.exception("agent_followup_job_error")
