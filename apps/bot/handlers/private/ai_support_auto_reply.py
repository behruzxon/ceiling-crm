"""
Auto-reply decision layer extracted from ai_support.py.
Template-based replies that skip OpenAI when appropriate.
"""

from __future__ import annotations

import asyncio
import json

from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)

_AI_DAILY_LIMIT = 100


async def _check_ai_rate_limit(user_id: int) -> bool:
    """Return True if user is within daily AI limit, False if exceeded."""
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys, CacheTTL

        redis = get_redis()
        key = CacheKeys.ai_rate_limit_daily(user_id)
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, CacheTTL.AI_RATE_LIMIT_DAILY)
        return count <= _AI_DAILY_LIMIT
    except Exception:
        return True


async def _try_auto_reply(
    message: Message,
    state: FSMContext,
    user_id: int,
    text: str,
) -> bool:
    """Try to auto-reply with a template instead of calling OpenAI.

    Returns True if auto-reply was sent (caller should return early).
    Returns False if OpenAI should be called as usual.
    """
    try:
        from apps.bot.handlers.private.ai_memory import _load_ai_memory
        from apps.bot.handlers.private.ai_scoring import _get_lead_score
        from apps.bot.handlers.private.ai_states import _ai_keyboard
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys, CacheTTL

        redis = get_redis()

        mem = await _load_ai_memory(user_id) or {}
        score = await _get_lead_score(user_id)

        raw_consec = await redis.get(CacheKeys.auto_reply_consecutive(user_id))
        consecutive = int(raw_consec) if raw_consec else 0

        health_score = 50
        try:
            from core.services.conversation_intelligence_service import (
                analyze_conversation,
            )

            ci = analyze_conversation(
                score=score,
                last_objection=mem.get("last_objection"),
                phone_captured=bool(mem.get("phone_captured")),
                area_m2=float(mem["area_m2"]) if mem.get("area_m2") else None,
                minutes_since_last_activity=0,
                follow_up_count=0,
                lead_temperature=mem.get("lead_temperature"),
                closing_confidence=mem.get("closing_confidence"),
                buyer_type=mem.get("buyer_type"),
                has_district=bool(mem.get("district")),
                current_stage="NEW",
            )
            health_score = ci.health_score
        except Exception:
            pass

        from core.services.auto_sales_service import (
            build_escalation_alert,
            decide_auto_reply,
            generate_auto_reply,
            should_escalate,
        )

        esc = should_escalate(
            last_objection=mem.get("last_objection"),
            objection_severity=mem.get("last_objection_severity"),
            consecutive_auto_replies=consecutive,
            health_score=health_score,
            negotiation_escalated=bool(mem.get("negotiation_escalated")),
            follow_up_count=0,
            score=score,
            closing_confidence=mem.get("closing_confidence"),
        )

        if esc.should_escalate:
            settings = get_settings()
            admin_group_id = settings.bot.admin_group_id
            if admin_group_id and message.bot:
                dedup_key = CacheKeys.auto_sales_escalation(user_id)
                was_set = await redis.set(
                    dedup_key,
                    "1",
                    ttl=CacheTTL.AUTO_SALES_ESCALATION,
                    nx=True,
                )
                if was_set:
                    from shared.utils.telegram_send import safe_send_message

                    alert = build_escalation_alert(
                        lead_id=user_id,
                        lead_name=mem.get("name", "?"),
                        lead_phone=mem.get("phone", "—"),
                        reason_uz=esc.reason_uz,
                        last_message=text[:120],
                        suggested_action_uz=esc.suggested_action_uz,
                        urgency=esc.urgency,
                    )
                    asyncio.create_task(safe_send_message(message.bot, admin_group_id, alert))
            return False

        decision = decide_auto_reply(
            score=score,
            health_score=health_score,
            last_objection=mem.get("last_objection"),
            objection_severity=mem.get("last_objection_severity"),
            consecutive_auto_replies=consecutive,
            negotiation_escalated=bool(mem.get("negotiation_escalated")),
            lead_temperature=mem.get("lead_temperature"),
            closing_confidence=mem.get("closing_confidence"),
        )

        if not decision.auto_reply_allowed:
            return False

        intent = _detect_simple_intent(text)
        if intent is None:
            return False

        reply = generate_auto_reply(
            intent=intent,
            buyer_type=mem.get("buyer_type"),
            has_area=bool(mem.get("area_m2")),
            has_phone=bool(mem.get("phone_captured")),
            has_district=bool(mem.get("district")),
            last_objection=mem.get("last_objection"),
        )

        await message.answer(reply.reply_text, reply_markup=_ai_keyboard())

        key = CacheKeys.auto_reply_consecutive(user_id)
        new_count = await redis.incr(key)
        if new_count == 1:
            await redis.expire(key, CacheTTL.AUTO_REPLY_CONSECUTIVE)

        log_data = json.dumps(
            {
                "reply_type": reply.reply_type,
                "confidence": decision.confidence,
                "ts": int(__import__("time").time()),
            }
        )
        await redis.set(
            CacheKeys.auto_reply_log(user_id),
            log_data,
            ttl=CacheTTL.AUTO_REPLY_LOG,
        )

        import asyncio as _aio

        from core.services.tactic_outcome_logger import log_tactic_outcome

        _temp = "hot" if score >= 60 else ("warm" if score >= 30 else "cold")
        _aio.create_task(
            log_tactic_outcome(
                event_type="auto_reply",
                tactic_name=reply.reply_type,
                user_id=user_id,
                lead_score_at_time=score,
                lead_temperature_at_time=_temp,
            )
        )

        log.info(
            "auto_reply_sent",
            user_id=user_id,
            reply_type=reply.reply_type,
            confidence=decision.confidence,
            consecutive=new_count,
        )

        return True

    except Exception:
        log.debug("auto_reply_check_failed", user_id=user_id)
        return False


def _detect_simple_intent(text: str) -> str | None:
    """Detect a simple intent from user text for auto-reply templates."""
    t = text.lower().strip()

    _PRICE_WORDS = frozenset(
        {
            "narx",
            "qancha",
            "necha pul",
            "baho",
            "qimmat",
            "arzon",
            "narxi qancha",
            "narxi",
            "qanchaga",
            "nechpul",
        }
    )
    _MATERIAL_WORDS = frozenset(
        {
            "material",
            "rang",
            "dizayn",
            "qanday",
            "variant",
            "tekstura",
            "mat",
            "glossy",
            "satin",
            "rangli",
        }
    )
    _PACKAGE_WORDS = frozenset(
        {
            "paket",
            "tayyor",
            "komplekt",
            "to'plam",
            "premium",
            "standart",
        }
    )

    for kw in _PRICE_WORDS:
        if kw in t:
            return "price"

    for kw in _MATERIAL_WORDS:
        if kw in t:
            return "material"

    for kw in _PACKAGE_WORDS:
        if kw in t:
            return "package"

    return None


async def _reset_auto_reply_counter(user_id: int) -> None:
    """Reset consecutive auto-reply counter after an OpenAI response."""
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys

        await get_redis().delete(CacheKeys.auto_reply_consecutive(user_id))
    except Exception:
        pass
