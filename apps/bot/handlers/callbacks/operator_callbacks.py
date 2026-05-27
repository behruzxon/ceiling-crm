"""
On-demand operator assistant callbacks.

Flow:
  1. Admin taps "💡 Operator yordam" on a lead card  → op:menu:{lead_id}
  2. Bot replies with 5 suggestion buttons             → op:{lead_id}:soft/close/budget/call/autoclose
  3. Admin taps one → bot sends copyable reply text   → answer inline

Callback patterns:
  op:menu:{lead_id}          — show suggestion menu
  op:{lead_id}:soft          — gentle opener
  op:{lead_id}:close         — strong close
  op:{lead_id}:budget        — budget alternative
  op:{lead_id}:call          — call script
  op:{lead_id}:autoclose     — AI auto-close suggestion
"""

from __future__ import annotations

import re

from aiogram import F, Router
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from infrastructure.database.repositories.lead_repo import PostgresLeadRepository
from infrastructure.database.session import get_session_factory
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="callbacks:operator_assist")

_MENU_RE = re.compile(r"^op:menu:(\d+)$")
_ACTION_RE = re.compile(r"^op:(\d+):(soft|close|budget|call)$")
_AUTOCLOSE_RE = re.compile(r"^op:(\d+):autoclose$")


# ── Menu callback ────────────────────────────────────────────────────────────


@router.callback_query(F.data.regexp(_MENU_RE))
async def cb_operator_menu(callback: CallbackQuery, **data: object) -> None:
    """Show operator assist sub-menu with 4 suggestion buttons."""
    await callback.answer()
    if not callback.data:
        return

    m = _MENU_RE.match(callback.data)
    if not m:
        return

    lead_id = int(m.group(1))
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="\U0001f4ac Yumshoq javob",
                    callback_data=f"op:{lead_id}:soft",
                ),
                InlineKeyboardButton(
                    text="\U0001f3af Closing javob",
                    callback_data=f"op:{lead_id}:close",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="\U0001f4b2 Byudjet javob",
                    callback_data=f"op:{lead_id}:budget",
                ),
                InlineKeyboardButton(
                    text="\U0001f4de Qo'ng'iroq skript",
                    callback_data=f"op:{lead_id}:call",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="\U0001f9e0 Auto Close",
                    callback_data=f"op:{lead_id}:autoclose",
                ),
            ],
        ]
    )
    await callback.message.answer(  # type: ignore[union-attr]
        f"\U0001f4a1 <b>Lid #{lead_id} uchun operator yordam</b>\n\n" "Qaysi javob kerak?",
        reply_markup=keyboard,
    )


# ── Action callbacks ─────────────────────────────────────────────────────────


@router.callback_query(F.data.regexp(_ACTION_RE))
async def cb_operator_action(callback: CallbackQuery, **data: object) -> None:
    """Load lead, build assist, send the requested reply suggestion."""
    await callback.answer()
    if not callback.data:
        return

    m = _ACTION_RE.match(callback.data)
    if not m:
        return

    lead_id = int(m.group(1))
    action = m.group(2)

    # Load lead from DB
    try:
        factory = get_session_factory()
        async with factory() as session:
            repo = PostgresLeadRepository(session)
            lead = await repo.get_by_id(lead_id)
    except Exception:
        log.exception("operator_assist_load_failed", lead_id=lead_id)
        await callback.message.answer("Xatolik yuz berdi.")  # type: ignore[union-attr]
        return

    if lead is None:
        await callback.message.answer(f"Lid #{lead_id} topilmadi.")  # type: ignore[union-attr]
        return

    # Load AI memory for extra context
    mem: dict = {}
    try:
        from apps.bot.handlers.private.ai_support import _load_ai_memory

        mem = await _load_ai_memory(lead.user_id)
    except Exception:
        pass  # proceed without memory

    # Build operator assist
    from core.services.operator_assistant_service import build_operator_assist

    # Run intelligence layers for better suggestions
    dp_pct: int | None = None
    buyer_type: str | None = mem.get("buyer_type")
    decision_stage: str | None = None
    engagement_trend: str | None = None

    try:
        from shared.utils.deal_probability import evaluate_deal_probability

        _sv = None
        try:
            from core.services.signal_vector_service import build_signal_vector

            _sv = build_signal_vector(
                lead_score=lead.score or 0,
                closing_confidence=lead.closing_confidence,
                phone_captured=bool(lead.phone),
                has_area=lead.room_area is not None,
                area_m2=float(lead.room_area) if lead.room_area else None,
                has_district=bool(lead.district),
                follow_up_count=lead.follow_up_count or 0,
                lead_temperature=lead.lead_temperature,
            )
        except Exception:
            pass
        dp = (
            evaluate_deal_probability(signal_vector=_sv)
            if _sv
            else evaluate_deal_probability(
                score=lead.score or 0,
                closing_confidence=lead.closing_confidence,
                phone_captured=bool(lead.phone),
                has_area=lead.room_area is not None,
                area_m2=float(lead.room_area) if lead.room_area else None,
                has_district=bool(lead.district),
                follow_up_count=lead.follow_up_count or 0,
            )
        )
        dp_pct = dp.deal_probability_percent

        if not buyer_type:
            from core.services.lead_intelligence_service import analyze_buyer_type

            bp = analyze_buyer_type(
                score=lead.score or 0,
                closing_confidence=lead.closing_confidence,
                phone_captured=bool(lead.phone),
                has_area=lead.room_area is not None,
                has_district=bool(lead.district),
                deal_probability_percent=dp_pct,
            )
            buyer_type = bp.buyer_type

        from core.services.conversation_memory_graph_service import (
            analyze_conversation_graph,
        )

        cg = analyze_conversation_graph(
            score=lead.score or 0,
            phone_captured=bool(lead.phone),
            has_area=lead.room_area is not None,
            has_district=bool(lead.district),
            deal_probability_percent=dp_pct,
            buyer_type=buyer_type,
            last_objection=mem.get("last_objection"),
            closing_confidence=lead.closing_confidence,
            follow_up_count=lead.follow_up_count or 0,
            last_activity_ts=mem.get("updated_at"),
            memory_created_at=mem.get("created_at"),
        )
        decision_stage = cg.current_decision_stage
        engagement_trend = cg.engagement_trend
    except Exception:
        pass  # proceed with partial data

    assist = build_operator_assist(
        name=lead.name if lead.name != "Noma'lum" else mem.get("name"),
        score=lead.score or 0,
        buyer_type=buyer_type,
        decision_stage=decision_stage,
        engagement_trend=engagement_trend,
        last_objection=mem.get("last_objection"),
        area_m2=float(lead.room_area) if lead.room_area else mem.get("area_m2"),
        district=lead.district or mem.get("district"),
        design_type=mem.get("design_type"),
        phone_captured=bool(lead.phone),
        closing_attempted=bool(mem.get("last_closing_attempt")),
        deal_probability_percent=dp_pct,
        negotiation_tactic=mem.get("last_negotiation_tactic"),
        negotiation_escalated=bool(mem.get("negotiation_escalated")),
        follow_up_type=mem.get("last_fu_type"),
    )

    # Pick the requested reply
    _action_map = {
        "soft": ("\U0001f4ac Yumshoq javob", assist.operator_reply_soft),
        "close": ("\U0001f3af Closing javob", assist.operator_reply_close),
        "budget": ("\U0001f4b2 Byudjet javob", assist.operator_reply_budget),
        "call": ("\U0001f4de Qo'ng'iroq skript", assist.operator_call_script),
    }
    label, reply_text = _action_map.get(action, ("", ""))
    if not reply_text:
        return

    text = (
        f"{label} — Lid #{lead_id}\n\n"
        f"<code>{reply_text}</code>\n\n"
        f"<i>{assist.operator_action_reason}</i>"
    )
    await callback.message.answer(text)  # type: ignore[union-attr]

    # Log tactic outcome for outcome-based learning
    import asyncio

    from core.services.tactic_outcome_logger import log_tactic_outcome

    asyncio.create_task(
        log_tactic_outcome(
            event_type="operator",
            tactic_name=action,
            user_id=lead.user_id,
            lead_id=lead_id,
            lead_score_at_time=lead.score or 0,
            lead_temperature_at_time=lead.lead_temperature,
        )
    )


# ── Auto Close callback ──────────────────────────────────────────────────────


@router.callback_query(F.data.regexp(_AUTOCLOSE_RE))
async def cb_operator_autoclose(callback: CallbackQuery, **data: object) -> None:
    """Load lead, run AI Auto Closer, send strategy + copyable reply."""
    await callback.answer()
    if not callback.data:
        return

    m = _AUTOCLOSE_RE.match(callback.data)
    if not m:
        return

    lead_id = int(m.group(1))

    # Load lead from DB
    try:
        factory = get_session_factory()
        async with factory() as session:
            repo = PostgresLeadRepository(session)
            lead = await repo.get_by_id(lead_id)
    except Exception:
        log.exception("autoclose_load_failed", lead_id=lead_id)
        await callback.message.answer("Xatolik yuz berdi.")  # type: ignore[union-attr]
        return

    if lead is None:
        await callback.message.answer(f"Lid #{lead_id} topilmadi.")  # type: ignore[union-attr]
        return

    # Load AI memory + Redis score
    mem: dict = {}
    redis_score: int = 0
    try:
        from apps.bot.handlers.private.ai_support import _get_lead_score, _load_ai_memory

        mem = await _load_ai_memory(lead.user_id)
        redis_score = await _get_lead_score(lead.user_id)
    except Exception:
        pass

    effective_score = redis_score or lead.score or 0
    lead_name = lead.name if lead.name != "Noma'lum" else mem.get("name")

    # Run Auto Closer
    from core.services.ai_auto_closer_service import STRATEGY_LABELS, build_auto_close_reply

    ac = build_auto_close_reply(
        name=lead_name,
        district=lead.district or mem.get("district"),
        phone=lead.phone,
        score=effective_score,
        closing_confidence=lead.closing_confidence,
        phone_captured=bool(lead.phone),
        has_area=lead.room_area is not None,
        area_m2=float(lead.room_area) if lead.room_area else mem.get("area_m2"),
        has_district=bool(lead.district),
        closing_attempted=bool(mem.get("last_closing_attempt")),
        closing_action=mem.get("last_closing_action"),
        last_objection=mem.get("last_objection"),
        intent=mem.get("last_intent"),
        follow_up_count=lead.follow_up_count or 0,
        design_type=mem.get("design_type"),
        negotiation_tactic=mem.get("last_negotiation_tactic"),
        negotiation_escalated=bool(mem.get("negotiation_escalated")),
        last_activity_ts=mem.get("updated_at"),
        memory_created_at=mem.get("created_at"),
        lead_temperature=lead.lead_temperature,
        lead_status=lead.lead_status,
    )

    strategy_label = STRATEGY_LABELS.get(ac.recommended_strategy, ac.recommended_strategy)
    reasons_text = "\n".join(f"  \u2022 {r}" for r in ac.reason_summary)

    text = (
        f"\U0001f9e0 <b>Auto Close</b> \u2014 Lid #{lead_id}\n\n"
        f"Strategiya: <b>{strategy_label}</b>\n"
        f"Ishonch: <b>{ac.confidence:.0%}</b>\n\n"
        f"Tavsiya etilgan javob:\n"
        f"<code>{ac.recommended_reply}</code>\n\n"
        f"<i>{reasons_text}</i>"
    )
    await callback.message.answer(text)  # type: ignore[union-attr]
