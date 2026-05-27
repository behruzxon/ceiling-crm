"""
apps.bot.handlers.admin.autopilot
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
/autopilot — AI Sales Autopilot: shows next best actions, opportunities,
at-risk leads, closing suggestions, and pipeline bottlenecks.

Access: ADMIN / SUPERADMIN roles.
"""
from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from apps.bot.filters.role import RoleFilter
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_lead_repo
from shared.constants.enums import UserRole
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="admin:autopilot")

_MGMT_ROLES = (UserRole.ADMIN, UserRole.SUPERADMIN)


@router.message(Command("autopilot"), RoleFilter(*_MGMT_ROLES))
async def cmd_autopilot(message: Message, **data: object) -> None:
    """Show AI Sales Autopilot suggestions for active leads."""
    await message.answer("\U0001f916 Autopilot tahlil qilinmoqda...")

    try:
        factory = get_session_factory()
        async with factory() as session:
            repo = get_lead_repo(session)
            leads = await repo.get_active_leads(limit=30)

        if not leads:
            await message.answer("\U0001f916 Faol lidlar topilmadi.")
            return

        results = await _analyze_leads(leads)
        text = _format_autopilot_card(results, len(leads))

        if len(text) <= 4096:
            await message.answer(text)
        else:
            parts = text.split("\n\n")
            chunk = ""
            for part in parts:
                if len(chunk) + len(part) + 2 > 4000:
                    await message.answer(chunk)
                    chunk = part
                else:
                    chunk = f"{chunk}\n\n{part}" if chunk else part
            if chunk:
                await message.answer(chunk)

    except Exception:
        log.exception("autopilot_command_failed")
        await message.answer("\u274c Autopilot xatolik yuz berdi.")


async def _analyze_leads(leads: list) -> dict:
    """Run full autopilot analysis on active leads."""
    from core.services.conversation_intelligence_service import (
        analyze_conversation,
    )
    from core.services.next_best_action_service import (
        analyze_pipeline_bottlenecks,
        detect_at_risk,
        detect_opportunity,
        determine_next_best_action,
        suggest_closing_tactic,
    )

    now_ts = int(datetime.now(UTC).timestamp())

    nba_list: list[dict] = []
    opportunities: list[dict] = []
    at_risk_leads: list[dict] = []
    closing_leads: list[dict] = []
    action_counter: Counter = Counter()
    stage_counter: Counter = Counter()

    for lead in leads:
        mem = await _load_lead_memory(lead.user_id)
        score = await _get_lead_score(lead.user_id)

        last_ts = mem.get("last_activity_ts") or mem.get("updated_at")
        if last_ts:
            mins_inactive = max(0, (now_ts - int(last_ts)) // 60)
        else:
            mins_inactive = int(
                (datetime.now(UTC) - lead.updated_at).total_seconds() / 60
            )

        stage_str = (
            lead.current_stage.value
            if hasattr(lead.current_stage, "value")
            else str(lead.current_stage)
        )
        temp = lead.lead_temperature or _classify_temp(score)
        stage_counter[stage_str.upper()] += 1

        # Health score
        ci = analyze_conversation(
            score=score,
            last_objection=mem.get("last_objection"),
            phone_captured=bool(lead.phone),
            area_m2=float(lead.room_area) if lead.room_area else None,
            minutes_since_last_activity=mins_inactive,
            follow_up_count=lead.follow_up_count or 0,
            lead_temperature=temp,
            closing_confidence=lead.closing_confidence,
            buyer_type=mem.get("buyer_type"),
            last_negotiation_tactic=mem.get("last_negotiation_tactic"),
            has_district=bool(lead.district),
            current_stage=stage_str,
        )

        objection_resolved = bool(
            mem.get("last_objection") and mem.get("last_negotiation_tactic")
        )

        # Build SignalVector
        sv = None
        try:
            from core.services.signal_vector_service import (
                build_signal_vector,
                with_deal_probability,
            )
            sv = build_signal_vector(
                lead_score=score,
                health_score=ci.health_score,
                closing_confidence=lead.closing_confidence,
                phone_captured=bool(lead.phone),
                has_area=lead.room_area is not None,
                area_m2=float(lead.room_area) if lead.room_area else None,
                has_district=bool(lead.district),
                closing_attempted=bool(mem.get("last_closing_attempt")),
                objection_resolved=objection_resolved,
                last_objection=mem.get("last_objection"),
                follow_up_count=lead.follow_up_count or 0,
                lead_temperature=temp,
                buyer_type=mem.get("buyer_type"),
                current_stage=stage_str,
                minutes_since_last_activity=mins_inactive,
                lead_status=lead.lead_status,
            )
        except Exception:
            pass

        # Deal probability
        dp_pct: int | None = None
        try:
            from shared.utils.deal_probability import evaluate_deal_probability
            dp = evaluate_deal_probability(signal_vector=sv) if sv else \
                evaluate_deal_probability(
                    score=score,
                    closing_confidence=lead.closing_confidence,
                    phone_captured=bool(lead.phone),
                    has_area=lead.room_area is not None,
                    area_m2=float(lead.room_area) if lead.room_area else None,
                    has_district=bool(lead.district),
                    follow_up_count=lead.follow_up_count or 0,
                )
            dp_pct = dp.deal_probability_percent
            if sv:
                sv = with_deal_probability(sv, dp_pct)
        except Exception:
            pass

        # NBA
        nba = determine_next_best_action(signal_vector=sv) if sv else \
            determine_next_best_action(
                score=score,
                health_score=ci.health_score,
                last_objection=mem.get("last_objection"),
                objection_resolved=objection_resolved,
                minutes_since_last_activity=mins_inactive,
                current_stage=stage_str,
                phone_captured=bool(lead.phone),
                area_m2=float(lead.room_area) if lead.room_area else None,
                has_district=bool(lead.district),
                follow_up_count=lead.follow_up_count or 0,
                closing_confidence=lead.closing_confidence,
                lead_temperature=temp,
                buyer_type=mem.get("buyer_type"),
                closing_attempted=bool(mem.get("last_closing_attempt")),
                deal_probability_percent=dp_pct,
            )
        action_counter[nba.action] += 1
        nba_list.append({
            "lead": lead,
            "nba": nba,
            "score": score,
            "health": ci.health_score,
            "dp": dp_pct,
        })

        # Opportunity
        opp = detect_opportunity(signal_vector=sv) if sv else \
            detect_opportunity(
                score=score,
                health_score=ci.health_score,
                last_objection=mem.get("last_objection"),
                objection_resolved=objection_resolved,
                minutes_since_last_activity=mins_inactive,
                phone_captured=bool(lead.phone),
                area_m2=float(lead.room_area) if lead.room_area else None,
                closing_confidence=lead.closing_confidence,
                deal_probability_percent=dp_pct,
            )
        if opp.detected:
            opportunities.append({"lead": lead, "opp": opp, "score": score})

        # At-risk
        risk = detect_at_risk(signal_vector=sv) if sv else \
            detect_at_risk(
                score=score,
                health_score=ci.health_score,
                last_objection=mem.get("last_objection"),
                objection_resolved=objection_resolved,
                minutes_since_last_activity=mins_inactive,
                lead_temperature=temp,
                follow_up_count=lead.follow_up_count or 0,
                closing_confidence=lead.closing_confidence,
                current_stage=stage_str,
            )
        if risk.detected:
            at_risk_leads.append({
                "lead": lead, "risk": risk, "score": score,
            })

        # Closing
        closing = suggest_closing_tactic(signal_vector=sv) if sv else \
            suggest_closing_tactic(
                score=score,
                phone_captured=bool(lead.phone),
                area_m2=float(lead.room_area) if lead.room_area else None,
                closing_confidence=lead.closing_confidence,
                deal_probability_percent=dp_pct,
                buyer_type=mem.get("buyer_type"),
                lead_temperature=temp,
                last_objection=mem.get("last_objection"),
                closing_attempted=bool(mem.get("last_closing_attempt")),
            )
        if closing.should_close:
            closing_leads.append({
                "lead": lead, "closing": closing, "score": score,
            })

    # Pipeline bottlenecks
    bottlenecks = analyze_pipeline_bottlenecks(dict(stage_counter))

    # Sort: high priority first, then by score desc
    _prio_order = {"high": 0, "medium": 1, "low": 2}
    nba_list.sort(key=lambda x: (_prio_order.get(x["nba"].priority, 3), -x["score"]))

    return {
        "nba_list": nba_list[:5],
        "opportunities": opportunities[:3],
        "at_risk": at_risk_leads[:3],
        "closing": closing_leads[:3],
        "bottlenecks": bottlenecks,
        "action_counter": action_counter,
        "total": len(leads),
    }


def _format_autopilot_card(results: dict, total: int) -> str:
    """Format autopilot results into a Telegram card."""
    from core.services.next_best_action_service import (
        _STAGE_LABELS,
        ACTION_LABELS,
        CLOSING_TACTIC_LABELS,
    )

    lines: list[str] = [
        f"\U0001f916 <b>AI Sales Autopilot</b> ({total} lid)\n",
    ]

    # ── Top NBA suggestions ──────────────────────────────────────
    nba_list = results["nba_list"]
    if nba_list:
        lines.append("<b>\U0001f3af Keyingi eng yaxshi amallar:</b>")
        _prio_badges = {"high": "\U0001f534", "medium": "\U0001f7e1", "low": "\U0001f7e2"}
        for item in nba_list:
            lead = item["lead"]
            nba = item["nba"]
            badge = _prio_badges.get(nba.priority, "\u26aa")
            action_label = ACTION_LABELS.get(nba.action, nba.action)
            lines.append(
                f"  {badge} <b>{lead.name}</b> #{lead.id}\n"
                f"    \U0001f3af {action_label}\n"
                f"    \U0001f4a1 {nba.reason_uz}"
            )
            if nba.suggested_message_uz:
                lines.append(
                    f"    \U0001f4ac <code>{nba.suggested_message_uz[:80]}</code>"
                )
        lines.append("")

    # ── Opportunities ────────────────────────────────────────────
    if results["opportunities"]:
        lines.append("<b>\U0001f525 Konversiya imkoniyatlari:</b>")
        for item in results["opportunities"]:
            lead = item["lead"]
            opp = item["opp"]
            lines.append(
                f"  \U0001f525 <b>{lead.name}</b> #{lead.id} "
                f"(score: {item['score']})\n"
                f"    \u27a1 {opp.recommended_action_uz}"
            )
        lines.append("")

    # ── At-risk leads ────────────────────────────────────────────
    if results["at_risk"]:
        lines.append("<b>\u26a0\ufe0f Xavf ostidagi lidlar:</b>")
        _urg_badges = {"immediate": "\U0001f534", "soon": "\U0001f7e1", "monitor": "\U0001f7e2"}
        for item in results["at_risk"]:
            lead = item["lead"]
            risk = item["risk"]
            urg_badge = _urg_badges.get(risk.urgency, "\u26aa")
            lines.append(
                f"  {urg_badge} <b>{lead.name}</b> #{lead.id}\n"
                f"    \u26a0\ufe0f {risk.risk_reason_uz}\n"
                f"    \u27a1 {risk.recommended_action_uz}"
            )
        lines.append("")

    # ── Closing suggestions ──────────────────────────────────────
    if results["closing"]:
        lines.append("<b>\U0001f3af Yopish imkoniyatlari:</b>")
        for item in results["closing"]:
            lead = item["lead"]
            cl = item["closing"]
            tactic_label = CLOSING_TACTIC_LABELS.get(cl.tactic, cl.tactic)
            lines.append(
                f"  \U0001f3c6 <b>{lead.name}</b> #{lead.id}\n"
                f"    Taktika: {tactic_label}\n"
                f"    \U0001f4ac <code>{cl.suggested_message_uz[:80]}</code>"
            )
        lines.append("")

    # ── Pipeline bottlenecks ─────────────────────────────────────
    if results["bottlenecks"]:
        lines.append("<b>\U0001f4ca Pipeline bottleneck:</b>")
        for ins in results["bottlenecks"]:
            label = _STAGE_LABELS.get(ins.bottleneck_stage, ins.bottleneck_stage)
            lines.append(
                f"  \u26a0\ufe0f {label}: {ins.leads_stuck} lid\n"
                f"    \U0001f4a1 {ins.recommendation_uz}"
            )
        lines.append("")

    # ── Action distribution summary ──────────────────────────────
    ac = results["action_counter"]
    if ac:
        lines.append("<b>\U0001f4cb Amallar taqsimoti:</b>")
        for action, count in ac.most_common(5):
            label = ACTION_LABELS.get(action, action)
            lines.append(f"  {label}: {count}")

    lines.append("\n/lead_ID \u2014 batafsil ko'rish")
    return "\n".join(lines)


# ── Helpers ────────────────────────────────────────────────────────────────


def _classify_temp(score: int) -> str:
    if score >= 60:
        return "hot"
    if score >= 30:
        return "warm"
    return "cold"


async def _load_lead_memory(user_id: int) -> dict:
    try:
        from apps.bot.handlers.private.ai_memory import _load_ai_memory
        return await _load_ai_memory(user_id) or {}
    except Exception:
        return {}


async def _get_lead_score(user_id: int) -> int:
    try:
        from infrastructure.cache.client import get_redis
        from infrastructure.cache.keys import CacheKeys
        raw = await get_redis().get(CacheKeys.ai_lead_score(user_id))
        return int(raw) if raw else 0
    except Exception:
        return 0
