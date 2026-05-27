"""
apps.bot.handlers.private.sales_closer
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
AI Sales Closer — proactively offers a closing CTA when a lead shows
buying intent but has not yet booked a measurement.

This is a **pure helper module** (no Router).  The orchestrating function
``attempt_close()`` is called from the AI chat handlers in
``ai_support.py`` after every LLM reply.

Closing triggers (any one is sufficient):
  1. Lead score >= 40
  2. LLM intent is price / measurement / catalog
  3. User shared room size (area_m2 in memory)
  4. User shared phone (phone_captured in memory)
  5. Closing confidence >= 0.6

Cooldown: at most one closing CTA per user per 10 minutes (Redis NX key).

Closing actions (picked based on funnel state):
  - "measurement" — free measurement booking  (area + district known)
  - "call"        — phone call with manager    (phone captured)
  - "catalog"     — send detailed catalog      (fallback)
"""

from __future__ import annotations

import time
from typing import Any

from aiogram.fsm.context import FSMContext
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from shared.logging import get_logger

log = get_logger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────

_SCORE_THRESHOLD = 40
_CONFIDENCE_THRESHOLD = 0.6
_CLOSING_INTENTS: frozenset[str] = frozenset({"price", "measurement", "catalog"})

# ── CTA labels for admin cards ────────────────────────────────────────────────

CLOSING_ACTION_LABELS: dict[str, str] = {
    "measurement": "Bepul o'lchov",
    "call": "Menejer qo'ng'iroq",
    "catalog": "Katalog yuborish",
}


# ── Trigger evaluation ───────────────────────────────────────────────────────


def should_attempt_close(
    *,
    score: int,
    intent: str,
    memory: dict[str, Any],
    closing_confidence: float | None,
) -> bool:
    """Return True when at least one closing trigger fires.

    Does NOT check cooldown — that is handled by ``attempt_close`` via Redis NX.
    """
    if score >= _SCORE_THRESHOLD:
        return True
    if intent in _CLOSING_INTENTS:
        return True
    if memory.get("area_m2") is not None:
        return True
    if memory.get("phone_captured"):
        return True
    if closing_confidence is not None and closing_confidence >= _CONFIDENCE_THRESHOLD:
        return True
    return False


# ── Action picker ─────────────────────────────────────────────────────────────


def pick_closing_action(
    fsm_data: dict[str, Any],
    memory: dict[str, Any],
) -> str:
    """Choose the best closing CTA based on what the funnel already knows.

    Returns ``"measurement"`` | ``"call"`` | ``"catalog"``.
    """
    has_area = memory.get("area_m2") is not None or fsm_data.get("price_area") is not None
    has_district = bool(memory.get("district") or fsm_data.get("price_district"))
    has_phone = bool(memory.get("phone_captured"))

    if has_area and has_district:
        return "measurement"
    if has_phone:
        return "call"
    if has_area:
        # Area known but no district yet — measurement is still the best push
        return "measurement"
    return "catalog"


# ── Message builder ───────────────────────────────────────────────────────────

_MEASUREMENT_TEXT = (
    "Agar xohlasangiz, ustamiz bepul kelib o'lchab aniq narx chiqarib beradi.\n"
    "Majburiyat yo'q — bekor qilish mumkin.\n\n"
    "Qaysi vaqt qulay?"
)

_CALL_TEXT = (
    "Mutaxassisimiz siz bilan bog'lanib barcha savollaringizga javob beradi.\n"
    "Telefon raqamingizni yuboring — tez orada qo'ng'iroq qilamiz."
)

_CATALOG_TEXT = "Katalogimizda turli dizaynlar bor — xonangizga mos variantni tanlab beramiz."


def build_closing_message(
    action: str,
    name: str | None = None,
) -> tuple[str, InlineKeyboardMarkup]:
    """Build the closing CTA text + inline keyboard for the given action.

    Returns ``(text, keyboard)``.
    """
    if action == "measurement":
        text = _MEASUREMENT_TEXT
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Bugun", callback_data="closer:book:today"),
                    InlineKeyboardButton(text="Ertaga", callback_data="closer:book:tomorrow"),
                    InlineKeyboardButton(text="Keyinroq", callback_data="closer:later"),
                ],
            ]
        )
    elif action == "call":
        text = _CALL_TEXT
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Ha, raqam yuboraman",
                        callback_data="closer:call",
                    ),
                    InlineKeyboardButton(text="Keyinroq", callback_data="closer:later"),
                ],
            ]
        )
    else:  # catalog
        text = _CATALOG_TEXT
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Katalogni ko'rish",
                        callback_data="closer:catalog",
                    ),
                    InlineKeyboardButton(
                        text="Narx hisoblash",
                        callback_data="closer:price",
                    ),
                ],
            ]
        )

    # Personalise with name
    if name:
        text = f"{name}, {text[:1].lower()}{text[1:]}"

    return text, kb


# ── Cooldown check (Redis NX) ────────────────────────────────────────────────


async def _check_and_set_cooldown(user_id: int) -> bool:
    """Return True if the cooldown lock was acquired (= no recent closing CTA).

    Uses ``SET NX`` so the key is only created if it does not yet exist.
    If ``NX`` fails, the user already received a CTA within the TTL window.
    """
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys, CacheTTL

        ok = await get_redis().set(
            CacheKeys.sales_closer_last(user_id),
            "1",
            ttl=CacheTTL.SALES_CLOSER_COOLDOWN,
            nx=True,
        )
        return bool(ok)
    except Exception:
        # Redis unavailable → allow the attempt (fail-open)
        return True


# ── Main orchestrator ─────────────────────────────────────────────────────────


async def attempt_close(
    message: Message,
    state: FSMContext,
    user_id: int,
    *,
    intent: str,
    score: int,
    closing_confidence: float | None,
) -> bool:
    """Check triggers, enforce cooldown, send closing CTA if appropriate.

    Called fire-and-forget from AI chat handlers.  Never raises.
    Returns True if a closing message was sent.
    """
    try:
        # 1. Load memory
        from apps.bot.handlers.private.ai_support import (
            _load_ai_memory,
            _save_ai_memory,
        )

        memory = await _load_ai_memory(user_id)

        # Skip if user already completed the funnel (phone captured + lead created)
        if memory.get("phone_captured"):
            fu_state_raw = None
            try:
                from infrastructure.cache.client import get_redis
                from infrastructure.cache.keys import CacheKeys

                fu_state_raw = await get_redis().get_json(CacheKeys.ai_followup_state(user_id))
            except Exception:
                pass
            if fu_state_raw and fu_state_raw.get("lead_created"):
                return False

        # 2. Evaluate triggers
        fsm_data = await state.get_data()
        if not should_attempt_close(
            score=score,
            intent=intent,
            memory=memory,
            closing_confidence=closing_confidence,
        ):
            return False

        # 3. Cooldown (Redis NX — at most once per 10 min)
        if not await _check_and_set_cooldown(user_id):
            log.debug("sales_closer_cooldown", user_id=user_id)
            return False

        # 4. Pick action + build message
        action = pick_closing_action(fsm_data, memory)
        name = memory.get("name") or fsm_data.get("user_name")
        text, kb = build_closing_message(action, name)

        # 5. Send closing CTA
        await message.answer(text, reply_markup=kb)

        # 6. Update memory
        memory["last_closing_attempt"] = action
        memory["last_closing_at"] = int(time.time())
        await _save_ai_memory(user_id, memory)

        # Log tactic outcome for outcome-based learning
        import asyncio

        from core.services.tactic_outcome_logger import log_tactic_outcome

        _temp = "hot" if score >= 60 else ("warm" if score >= 30 else "cold")
        asyncio.create_task(
            log_tactic_outcome(
                event_type="closer",
                tactic_name=action,
                user_id=user_id,
                lead_score_at_time=score,
                lead_temperature_at_time=_temp,
            )
        )

        log.info(
            "sales_closer_sent",
            user_id=user_id,
            action=action,
            score=score,
            intent=intent,
        )
        return True

    except Exception:
        log.warning("sales_closer_failed", user_id=user_id)
        return False
