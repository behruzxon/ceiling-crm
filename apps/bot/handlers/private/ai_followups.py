"""
apps.bot.handlers.private.ai_followups
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Async delayed follow-up tasks: catalog follow-up, AI interaction
reminders, and photo funnel.

All tasks use ``asyncio.sleep`` and are fire-and-forget.
"""

from __future__ import annotations

import asyncio
import random
import time

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from apps.bot.handlers.private.ai_states import (
    _AI_FOLLOWUP_MSG_1,
    _AI_FOLLOWUP_MSG_2,
    AiSupportStates,
    _ai_keyboard,
)
from shared.logging import get_logger

log = get_logger(__name__)


# ── Photo funnel follow-up ──────────────────────────────────────────────────


async def _photo_followup_task(
    bot: Bot,
    chat_id: int,
    storage: object,
    state_key: object,
) -> None:
    """7-minute delayed follow-up for photo funnel."""
    await asyncio.sleep(7 * 60)
    try:
        _photo_states = {
            AiSupportStates.waiting_photo.state,
            AiSupportStates.waiting_room.state,
            AiSupportStates.waiting_area_photo.state,
        }
        current = await storage.get_state(key=state_key)  # type: ignore[union-attr]
        if current not in _photo_states:
            return
        await storage.set_state(  # type: ignore[union-attr]
            key=state_key, state=AiSupportStates.waiting_for_district.state
        )
        await bot.send_message(
            chat_id=chat_id,
            text=(
                "Ko'rib chiqdizmi? 🙂\n"
                "Xohlasangiz, bepul o'lchov uchun ustani yuborib qo'yaman. "
                "Zakaz qabul qilaymi?\n\n"
                "Qaysi tumandasiz?"
            ),
            reply_markup=_ai_keyboard(),
        )
    except Exception:
        log.warning("photo_followup_task_failed", chat_id=chat_id)


async def _enter_photo_funnel(message: Message, state: FSMContext) -> None:
    """Set waiting_photo state and prompt user to send a room photo."""
    await state.clear()
    await state.set_state(AiSupportStates.waiting_photo)
    await message.answer(
        "📸 Iltimos, xonangizni rasmini yuboring.",
        reply_markup=_ai_keyboard(),
    )


# ── Catalog follow-up (5-10 min after catalog button sent) ──────────────────

_CATALOG_FOLLOWUP_SKIP_GROUPS = (
    "LeadCaptureStates",
    "PricingStates",
    "MeasurementLeadStates",
    "BroadcastStates",
    "PipelineStates",
    "CatalogStates",
    "AppointmentStates",
)


async def _catalog_followup_task(
    bot: Bot,
    chat_id: int,
    user_id: int,
    storage: object,
    state_key: object,
) -> None:
    """5-10 min delayed follow-up sent at most once per user per 24 h."""
    from infrastructure.cache.client import get_redis
    from infrastructure.cache.keys import CacheKeys, CacheTTL

    await asyncio.sleep(random.randint(300, 600))
    try:
        redis = get_redis()
        acquired = await redis.set(
            CacheKeys.catalog_followup_sent(user_id),
            "1",
            ttl=CacheTTL.CATALOG_FOLLOWUP_SENT,
            nx=True,
        )
        if not acquired:
            return

        _skip_states: frozenset[str] = frozenset(
            {
                AiSupportStates.waiting_for_district.state,
                AiSupportStates.waiting_for_phone.state,
                AiSupportStates.waiting_photo.state,
                AiSupportStates.waiting_room.state,
                AiSupportStates.waiting_area_photo.state,
            }
        )

        current: str | None = await storage.get_state(key=state_key)  # type: ignore[union-attr]
        if current in _skip_states:
            await redis.delete(CacheKeys.catalog_followup_sent(user_id))
            return
        if current is not None and any(g in current for g in _CATALOG_FOLLOWUP_SKIP_GROUPS):
            await redis.delete(CacheKeys.catalog_followup_sent(user_id))
            return

        await storage.set_state(  # type: ignore[union-attr]
            key=state_key, state=AiSupportStates.waiting_for_district.state
        )
        await bot.send_message(
            chat_id=chat_id,
            text=(
                "Ko'rib chiqdizmi? 😊\n"
                "Xohlasangiz, bepul o'lchov uchun zakaz qabul qilib qo'yaymi?\n\n"
                "Qaysi tumandasiz va taxminiy maydon nechchi m²?"
            ),
            reply_markup=_ai_keyboard(),
        )
    except Exception:
        log.warning("catalog_followup_task_failed", chat_id=chat_id, user_id=user_id)


def _schedule_catalog_followup(
    bot: Bot,
    chat_id: int,
    user_id: int,
    storage: object,
    state_key: object,
) -> None:
    """Fire-and-forget: schedule one catalog follow-up for a private chat."""
    if chat_id < 0:
        return
    asyncio.create_task(
        _catalog_followup_task(
            bot=bot,
            chat_id=chat_id,
            user_id=user_id,
            storage=storage,
            state_key=state_key,
        )
    )


# ── AI interaction follow-up reminders ──────────────────────────────────────


async def _refresh_ai_followup_nonce(user_id: int) -> str:
    """Store a fresh random nonce in Redis and return it."""
    from infrastructure.cache.client import get_redis
    from infrastructure.cache.keys import CacheKeys, CacheTTL

    nonce = str(random.getrandbits(64))
    try:
        redis = get_redis()
        await redis.set(
            CacheKeys.ai_followup_nonce(user_id),
            nonce,
            ttl=CacheTTL.AI_FOLLOWUP_NONCE,
        )
        await redis.set(
            CacheKeys.ai_last_interaction(user_id),
            str(int(time.time())),
            ttl=CacheTTL.AI_LAST_INTERACTION,
        )
        existing = (await redis.get_json(CacheKeys.ai_followup_state(user_id))) or {}
        await redis.set_json(
            CacheKeys.ai_followup_state(user_id),
            {
                "first_sent": False,
                "second_sent": False,
                "lead_created": existing.get("lead_created", False),
            },
            ttl=CacheTTL.AI_FOLLOWUP_STATE,
        )
    except Exception:
        pass
    return nonce


async def _ai_followup_task(
    bot: Bot,
    chat_id: int,
    user_id: int,
    nonce: str,
    storage: object,
    state_key: object,
) -> None:
    """Two-stage follow-up: fires at 10 min and 60 min after the last interaction."""
    from infrastructure.cache.client import get_redis
    from infrastructure.cache.keys import CacheKeys, CacheTTL

    _skip_states = frozenset(
        {
            AiSupportStates.waiting_for_phone.state,
            AiSupportStates.waiting_for_district.state,
            AiSupportStates.waiting_photo.state,
            AiSupportStates.waiting_room.state,
            AiSupportStates.waiting_area_photo.state,
        }
    )

    async def _cancelled() -> bool:
        try:
            redis = get_redis()
            stored = await redis.get(CacheKeys.ai_followup_nonce(user_id))
            if stored != nonce:
                return True
            current = await storage.get_state(key=state_key)  # type: ignore[union-attr]
            if current in _skip_states:
                return True
            fu_state = (await redis.get_json(CacheKeys.ai_followup_state(user_id))) or {}
            return bool(fu_state.get("lead_created"))
        except Exception:
            return True

    async def _mark_sent(key: str) -> None:
        try:
            redis = get_redis()
            fu_state = (await redis.get_json(CacheKeys.ai_followup_state(user_id))) or {}
            fu_state[key] = True
            await redis.set_json(
                CacheKeys.ai_followup_state(user_id),
                fu_state,
                ttl=CacheTTL.AI_FOLLOWUP_STATE,
            )
        except Exception:
            pass

    # Reminder #1 — 10 minutes
    await asyncio.sleep(10 * 60)
    if await _cancelled():
        return
    try:
        await bot.send_message(chat_id=chat_id, text=_AI_FOLLOWUP_MSG_1)
        await _mark_sent("first_sent")
        log.info("ai_followup_1_sent", chat_id=chat_id, user_id=user_id)
    except Exception:
        log.warning("ai_followup_1_failed", chat_id=chat_id)
        return

    # Reminder #2 — 50 more minutes (60 min total)
    await asyncio.sleep(50 * 60)
    if await _cancelled():
        return
    try:
        await bot.send_message(chat_id=chat_id, text=_AI_FOLLOWUP_MSG_2)
        await _mark_sent("second_sent")
        log.info("ai_followup_2_sent", chat_id=chat_id, user_id=user_id)
    except Exception:
        log.warning("ai_followup_2_failed", chat_id=chat_id)


def _schedule_ai_followup(
    bot: Bot,
    chat_id: int,
    user_id: int,
    nonce: str,
    storage: object,
    state_key: object,
) -> None:
    """Fire-and-forget: schedule two-stage AI follow-up for private DMs only."""
    if chat_id < 0:
        return
    asyncio.create_task(
        _ai_followup_task(
            bot=bot,
            chat_id=chat_id,
            user_id=user_id,
            nonce=nonce,
            storage=storage,
            state_key=state_key,
        )
    )
