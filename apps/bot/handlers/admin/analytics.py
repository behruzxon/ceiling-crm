"""
apps.bot.handlers.admin.analytics
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
/analytics [days] — Sales Analytics: concise performance summary.

Loads leads for the requested period, enriches a sample with Redis AI
memory, runs ``build_sales_analytics``, and formats a compact admin card.

Access: ADMIN / SUPERADMIN roles.
"""

from __future__ import annotations

from datetime import UTC

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from apps.bot.filters.role import RoleFilter
from infrastructure.database.session import get_session_factory
from infrastructure.di import get_lead_repo
from shared.constants.enums import UserRole
from shared.logging import get_logger

log = get_logger(__name__)
router = Router(name="admin:analytics")

_MGMT_ROLES = (UserRole.ADMIN, UserRole.SUPERADMIN)


@router.message(Command("analytics"), RoleFilter(*_MGMT_ROLES))
async def cmd_analytics(message: Message, **data: object) -> None:
    """Show sales analytics for the given period (default 30 days)."""
    # Parse optional days argument
    days = 30
    if message.text:
        parts = message.text.split()
        if len(parts) >= 2:
            try:
                days = max(1, min(365, int(parts[1])))
            except ValueError:
                pass

    await message.answer(f"\U0001f4ca Tahlil qilinmoqda ({days} kun)...")

    try:
        # Load leads from DB
        factory = get_session_factory()
        async with factory() as session:
            repo = get_lead_repo(session)
            leads = await repo.get_leads_for_analytics(days=days, limit=500)

        if not leads:
            await message.answer(f"\U0001f4ca Oxirgi {days} kunda lidlar topilmadi.")
            return

        # Build signal dicts with optional Redis enrichment
        leads_data = await _build_leads_data(leads)

        # Run analytics
        from core.services.sales_analytics_service import build_sales_analytics

        report = build_sales_analytics(leads_data)

        # Query outcome-based tactic performance (best-effort)
        tactic_perf_report = None
        try:
            from core.services.tactic_performance_service import build_tactic_performance
            from infrastructure.di import get_tactic_outcome_repo

            async with factory() as session2:
                tac_repo = get_tactic_outcome_repo(session2)
                from datetime import datetime, timedelta

                since = datetime.now(UTC) - timedelta(days=days)
                resolved_stats = await tac_repo.get_resolved_stats(since=since, min_samples=3)
                if resolved_stats:
                    tactic_perf_report = build_tactic_performance(resolved_stats)
        except Exception:
            pass

        # Format and send
        text = _format_report(report, days, tactic_perf_report=tactic_perf_report)

        # Split if too long (Telegram limit 4096)
        if len(text) <= 4096:
            await message.answer(text)
        else:
            # Split at double newlines
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
        log.exception("analytics_command_failed")
        await message.answer("\u274c Tahlil xatolik yuz berdi.")


async def _build_leads_data(leads: list) -> list[dict]:
    """Convert Lead domain objects to signal dicts with optional Redis enrichment."""
    result: list[dict] = []

    for lead in leads:
        ld: dict = {
            "lead_id": lead.id,
            "source": lead.source.value if hasattr(lead.source, "value") else str(lead.source),
            "current_stage": (
                lead.current_stage.value
                if hasattr(lead.current_stage, "value")
                else str(lead.current_stage)
            ),
            "lead_status": lead.lead_status,
            "score": lead.score or 0,
            "phone": lead.phone,
            "district": lead.district,
            "room_area": float(lead.room_area) if lead.room_area else None,
            "follow_up_count": lead.follow_up_count or 0,
            "closing_confidence": lead.closing_confidence,
            "lead_temperature": lead.lead_temperature,
        }

        # Try Redis AI memory enrichment (best-effort, skip on error)
        mem: dict = {}
        try:
            from apps.bot.handlers.private.ai_memory import _load_ai_memory

            mem = await _load_ai_memory(lead.user_id) or {}
            if mem:
                ld["buyer_type"] = mem.get("buyer_type")
                ld["last_objection"] = mem.get("last_objection")
                ld["last_objection_severity"] = mem.get("last_objection_severity")
                ld["last_negotiation_tactic"] = mem.get("last_negotiation_tactic")
                ld["last_fu_type"] = mem.get("last_fu_type")
        except Exception:
            pass

        # Try revenue estimate (best-effort)
        try:
            from core.services.revenue_predictor_service import predict_lead_revenue

            rev = predict_lead_revenue(
                area_m2=ld.get("room_area"),
                buyer_type=ld.get("buyer_type"),
                last_objection=ld.get("last_objection"),
            )
            ld["predicted_revenue_best"] = rev.predicted_revenue_best
        except Exception:
            pass

        # Try conversation intelligence enrichment (best-effort)
        try:
            from core.services.conversation_intelligence_service import (
                analyze_conversation,
            )
            from infrastructure.cache.client import get_redis
            from infrastructure.cache.keys import CacheKeys

            score_raw = await get_redis().get(CacheKeys.ai_lead_score(lead.user_id))
            ai_score = int(score_raw) if score_raw else ld.get("score", 0)

            from datetime import datetime

            last_ts = mem.get("last_activity_ts") or mem.get("updated_at")
            if last_ts:
                mins_inactive = max(
                    0,
                    (int(datetime.now(UTC).timestamp()) - int(last_ts)) // 60,
                )
            else:
                mins_inactive = int((datetime.now(UTC) - lead.updated_at).total_seconds() / 60)

            ci = analyze_conversation(
                score=ai_score,
                last_objection=mem.get("last_objection"),
                last_objection_severity=mem.get("last_objection_severity"),
                last_user_message=mem.get("last_user_message"),
                phone_captured=bool(mem.get("phone_captured") or lead.phone),
                area_m2=float(lead.room_area) if lead.room_area else None,
                minutes_since_last_activity=mins_inactive,
                follow_up_count=lead.follow_up_count or 0,
                lead_temperature=lead.lead_temperature,
                closing_confidence=lead.closing_confidence,
                buyer_type=mem.get("buyer_type"),
                last_negotiation_tactic=mem.get("last_negotiation_tactic"),
                negotiation_escalated=bool(mem.get("negotiation_escalated")),
                has_district=bool(lead.district),
                last_closing_attempt=mem.get("last_closing_attempt"),
                lead_status=lead.lead_status,
                current_stage=ld["current_stage"],
            )
            ld["conv_health_score"] = ci.health_score
            ld["conv_signals"] = ci.signals
            ld["conv_risk_level"] = ci.risk_level
            ld["conv_cooling"] = ci.cooling_detected
            ld["conv_quality_score"] = ci.quality_score
        except Exception:
            pass

        # Shared variables for autopilot + closing enrichment
        _health = ld.get("conv_health_score", 50)
        _obj_resolved = bool(mem.get("last_objection") and mem.get("last_negotiation_tactic"))

        # Build SignalVector once — used by all engines below
        try:
            from core.services.signal_vector_service import (
                build_signal_vector,
                with_deal_probability,
            )

            sv = build_signal_vector(
                lead_score=ai_score,
                health_score=_health,
                closing_confidence=lead.closing_confidence,
                phone_captured=bool(mem.get("phone_captured") or lead.phone),
                has_area=lead.room_area is not None,
                area_m2=float(lead.room_area) if lead.room_area else None,
                has_district=bool(lead.district),
                closing_attempted=bool(mem.get("last_closing_attempt")),
                objection_resolved=_obj_resolved,
                last_objection=mem.get("last_objection"),
                last_objection_severity=mem.get("last_objection_severity"),
                follow_up_count=lead.follow_up_count or 0,
                lead_temperature=lead.lead_temperature,
                buyer_type=mem.get("buyer_type"),
                current_stage=ld["current_stage"],
                minutes_since_last_activity=mins_inactive,
                lead_status=lead.lead_status,
            )
        except Exception:
            sv = None

        # Try deal probability (best-effort, used by closing enrichment)
        try:
            from shared.utils.deal_probability import evaluate_deal_probability

            _dp = (
                evaluate_deal_probability(signal_vector=sv)
                if sv
                else evaluate_deal_probability(
                    score=ai_score,
                    closing_confidence=lead.closing_confidence,
                    phone_captured=bool(lead.phone),
                    has_area=lead.room_area is not None,
                    area_m2=float(lead.room_area) if lead.room_area else None,
                    has_district=bool(lead.district),
                    follow_up_count=lead.follow_up_count or 0,
                )
            )
            ld["deal_probability_percent"] = _dp.deal_probability_percent
            if sv:
                sv = with_deal_probability(sv, _dp.deal_probability_percent)
        except Exception:
            pass

        # Try autopilot enrichment (best-effort)
        try:
            from core.services.next_best_action_service import (
                detect_at_risk,
                detect_opportunity,
                determine_next_best_action,
                suggest_closing_tactic,
            )

            nba = (
                determine_next_best_action(signal_vector=sv)
                if sv
                else determine_next_best_action(
                    score=ai_score,
                    health_score=_health,
                    last_objection=mem.get("last_objection"),
                    objection_resolved=_obj_resolved,
                    minutes_since_last_activity=mins_inactive,
                    current_stage=ld["current_stage"],
                    phone_captured=bool(mem.get("phone_captured") or lead.phone),
                    area_m2=float(lead.room_area) if lead.room_area else None,
                    has_district=bool(lead.district),
                    follow_up_count=lead.follow_up_count or 0,
                    closing_confidence=lead.closing_confidence,
                    lead_temperature=lead.lead_temperature,
                    buyer_type=mem.get("buyer_type"),
                    closing_attempted=bool(mem.get("last_closing_attempt")),
                )
            )
            ld["nba_action"] = nba.action
            opp = (
                detect_opportunity(signal_vector=sv)
                if sv
                else detect_opportunity(
                    score=ai_score,
                    health_score=_health,
                    last_objection=mem.get("last_objection"),
                    objection_resolved=_obj_resolved,
                    minutes_since_last_activity=mins_inactive,
                    phone_captured=bool(lead.phone),
                    area_m2=float(lead.room_area) if lead.room_area else None,
                    closing_confidence=lead.closing_confidence,
                )
            )
            ld["opportunity_detected"] = opp.detected
            risk = (
                detect_at_risk(signal_vector=sv)
                if sv
                else detect_at_risk(
                    score=ai_score,
                    health_score=_health,
                    last_objection=mem.get("last_objection"),
                    objection_resolved=_obj_resolved,
                    minutes_since_last_activity=mins_inactive,
                    lead_temperature=lead.lead_temperature,
                    follow_up_count=lead.follow_up_count or 0,
                    closing_confidence=lead.closing_confidence,
                    current_stage=ld["current_stage"],
                )
            )
            ld["at_risk_detected"] = risk.detected
            closing = (
                suggest_closing_tactic(signal_vector=sv)
                if sv
                else suggest_closing_tactic(
                    score=ai_score,
                    phone_captured=bool(lead.phone),
                    area_m2=float(lead.room_area) if lead.room_area else None,
                    closing_confidence=lead.closing_confidence,
                    buyer_type=mem.get("buyer_type"),
                    lead_temperature=lead.lead_temperature,
                    last_objection=mem.get("last_objection"),
                    closing_attempted=bool(mem.get("last_closing_attempt")),
                )
            )
            ld["closing_ready"] = closing.should_close
        except Exception:
            pass

        # Try auto-seller enrichment (best-effort)
        try:
            import json as _json

            from infrastructure.cache.client import get_redis as _get_redis
            from infrastructure.cache.keys import CacheKeys as _CK

            _ar_log_raw = await _get_redis().get(_CK.auto_reply_log(lead.user_id))
            if _ar_log_raw:
                _ar_log = _json.loads(_ar_log_raw)
                ld["auto_reply_used"] = True
                ld["auto_reply_confidence"] = _ar_log.get("confidence")
            _esc_raw = await _get_redis().get(_CK.auto_sales_escalation(lead.id))
            if _esc_raw:
                ld["auto_escalated"] = True
        except Exception:
            pass

        # Try closing readiness enrichment (best-effort)
        try:
            from core.services.closing_readiness_service import (
                detect_close_loss_risk,
                evaluate_closing_readiness,
                select_closing_tactic,
            )

            cr = (
                evaluate_closing_readiness(signal_vector=sv)
                if sv
                else evaluate_closing_readiness(
                    score=ai_score,
                    health_score=_health,
                    last_objection=mem.get("last_objection"),
                    last_objection_severity=mem.get("last_objection_severity"),
                    objection_resolved=_obj_resolved,
                    minutes_since_last_activity=mins_inactive,
                    current_stage=ld["current_stage"],
                    phone_captured=bool(lead.phone),
                    area_m2=float(lead.room_area) if lead.room_area else None,
                    has_district=bool(lead.district),
                    follow_up_count=lead.follow_up_count or 0,
                    closing_confidence=lead.closing_confidence,
                    lead_temperature=lead.lead_temperature,
                    buyer_type=mem.get("buyer_type"),
                    closing_attempted=bool(mem.get("last_closing_attempt")),
                    deal_probability_percent=ld.get("deal_probability_percent"),
                )
            )
            ld["closing_readiness_tier"] = cr.readiness_tier
            risk = detect_close_loss_risk(
                readiness_tier=cr.readiness_tier,
                closing_score=cr.closing_score,
                minutes_since_last_activity=mins_inactive,
                health_score=ld.get("conv_health_score", 50),
                lead_temperature=lead.lead_temperature,
                last_objection=mem.get("last_objection"),
                objection_resolved=_obj_resolved,
            )
            ld["closing_loss_risk"] = risk.detected
            tactic = select_closing_tactic(
                readiness_tier=cr.readiness_tier,
                closing_score=cr.closing_score,
                last_objection=mem.get("last_objection"),
                objection_resolved=_obj_resolved,
                buyer_type=mem.get("buyer_type"),
                phone_captured=bool(lead.phone),
                area_m2=float(lead.room_area) if lead.room_area else None,
                closing_attempted=bool(mem.get("last_closing_attempt")),
                minutes_since_last_activity=mins_inactive,
                follow_up_count=lead.follow_up_count or 0,
                lead_temperature=lead.lead_temperature,
            )
            ld["closing_tactic"] = tactic.tactic
        except Exception:
            pass

        result.append(ld)

    return result


def _format_report(report, days: int, *, tactic_perf_report=None) -> str:
    """Format SalesAnalytics into a concise Telegram card."""
    lines: list[str] = []

    # ── Header ────────────────────────────────────────────────────────
    lines.append(f"\U0001f4ca <b>Sotuv tahlili — {days} kun</b>\n")

    # ── Total summary ─────────────────────────────────────────────────
    lines.append(
        f"\U0001f4cb Jami: {report.total_leads} | "
        f"\u2705 {report.won_leads} | "
        f"\u274c {report.lost_leads} | "
        f"\U0001f504 {report.active_leads}"
    )
    lines.append(f"\U0001f3af Konversiya: {report.conversion_rate:.1%}")
    lines.append(f"\U0001f4ca O'rtacha ball: {report.avg_score}")

    # Score distribution
    sd = report.score_distribution
    lines.append(
        f"\U0001f525 Hot: {sd['hot']} | "
        f"\U0001f7e1 Warm: {sd['warm']} | "
        f"\u2744\ufe0f Cold: {sd['cold']}"
    )

    # ── Revenue ───────────────────────────────────────────────────────
    if report.total_estimated_revenue > 0:
        lines.append("")
        lines.append(f"\U0001f4b0 Umumiy daromad: {report.total_estimated_revenue:,} UZS")
        lines.append(f"\U0001f4b5 Har bir lid: {report.avg_revenue_per_lead:,} UZS")

    # ── Sources ───────────────────────────────────────────────────────
    if report.top_sources:
        lines.append("")
        lines.append("<b>\U0001f4e1 Manbalar:</b>")
        for src in report.top_sources[:4]:
            lines.append(
                f"  {src['source']}: {src['leads']} lid | "
                f"\u2705{src['won']} | {src['rate']:.0%}"
            )

    # ── Funnel ────────────────────────────────────────────────────────
    if report.stage_counts:
        lines.append("")
        lines.append("<b>\U0001f3d7 Voronka:</b>")
        for sc in report.stage_counts:
            stage_label = _STAGE_LABELS_SHORT.get(sc["stage"], sc["stage"])
            bar = "\u2588" * min(sc["count"], 20)
            lines.append(f"  {stage_label}: {sc['count']} {bar}")

    if report.largest_dropoff_stage:
        label = _STAGE_LABELS_SHORT.get(report.largest_dropoff_stage, report.largest_dropoff_stage)
        lines.append(f"  \u26a0\ufe0f Eng katta tushish: {label}")

    # ── Objections ────────────────────────────────────────────────────
    if report.top_objections:
        lines.append("")
        lines.append("<b>\U0001f6ab E'tirozlar:</b>")
        _obj_labels = {
            "expensive": "\U0001f4b8 Qimmat",
            "delay": "\u23f3 Keyinroq",
            "trust": "\U0001f914 Ishonch",
            "compare": "\u2696\ufe0f Taqqoslash",
            "angry": "\U0001f624 Norozilik",
        }
        for obj in report.top_objections[:4]:
            label = _obj_labels.get(obj["type"], obj["type"])
            lines.append(f"  {label}: {obj['count']}")

    # ── Severity breakdown ──────────────────────────────────────────
    sev = report.objection_severity_stats
    if sev and (sev.get("medium", 0) + sev.get("high", 0)) > 0:
        lines.append(
            f"  \U0001f7e2 Past: {sev['low']} | "
            f"\U0001f7e1 O'rta: {sev['medium']} | "
            f"\U0001f534 Yuqori: {sev['high']}"
        )

    # ── Objection → Lost correlation ─────────────────────────────────
    if report.objection_lost_correlation:
        worst = [
            o
            for o in report.objection_lost_correlation
            if o["total"] >= 2 and o["lost_rate"] >= 0.3
        ]
        if worst:
            lines.append("")
            lines.append("<b>\u26a0\ufe0f E'tiroz \u2192 Yo'qotish:</b>")
            _olbl = {
                "expensive": "Qimmat",
                "delay": "Keyinroq",
                "trust": "Ishonch",
                "compare": "Taqqoslash",
                "angry": "Norozilik",
            }
            for o in worst[:3]:
                label = _olbl.get(o["type"], o["type"])
                lines.append(f"  {label}: {o['lost']}/{o['total']} ({o['lost_rate']:.0%} lost)")

    # ── Tactic effectiveness ─────────────────────────────────────────
    if report.tactic_stats:
        lines.append("")
        lines.append("<b>\U0001f3af Taktikalar:</b>")
        from core.services.negotiation_engine_service import TACTIC_LABELS

        for ts in report.tactic_stats[:4]:
            label = TACTIC_LABELS.get(ts["tactic"], ts["tactic"])
            lines.append(f"  {label}: {ts['count']} | " f"\u2705{ts['won']} ({ts['rate']:.0%})")
        if report.best_tactic:
            best_label = TACTIC_LABELS.get(
                report.best_tactic["tactic"], report.best_tactic["tactic"]
            )
            lines.append(
                f"  \U0001f3c6 Eng yaxshi: {best_label} " f"({report.best_tactic['won_rate']:.0%})"
            )

    # ── Buyer types ───────────────────────────────────────────────────
    if report.buyer_type_stats:
        lines.append("")
        lines.append("<b>\U0001f9e0 Xaridor turlari:</b>")
        _bt_labels = {
            "price_sensitive": "\U0001f4b2 Narxga sezgir",
            "quality_buyer": "\u2b50 Sifat",
            "fast_buyer": "\u26a1 Tez qaror",
            "research_buyer": "\U0001f50d Tadqiqotchi",
        }
        for bt in report.buyer_type_stats[:4]:
            label = _bt_labels.get(bt["type"], bt["type"])
            lines.append(f"  {label}: {bt['count']} | " f"\u2705{bt['won']} ({bt['rate']:.0%})")

    # ── Follow-up ─────────────────────────────────────────────────────
    fu = report.followup_stats
    if fu.get("with_followup_pct", 0) > 0:
        lines.append("")
        lines.append("<b>\U0001f501 Follow-up:</b>")
        lines.append(f"  Qamrov: {fu['with_followup_pct']:.0%} lidlar")
        lines.append(
            f"  O'rtacha (won): {fu['avg_followups_won']} | " f"(lost): {fu['avg_followups_lost']}"
        )
        if report.best_followup_type:
            from core.services.followup_brain_service import FU_TYPE_LABELS

            best = report.best_followup_type
            fu_label = FU_TYPE_LABELS.get(best["type"], best["type"])
            lines.append(f"  \U0001f3c6 Eng yaxshi: {fu_label} ({best['rate']:.0%})")

    # ── Conversation health ─────────────────────────────────────────
    if report.avg_health_score > 0:
        lines.append("")
        lines.append("<b>\U0001f3e5 Suhbat salomatligi:</b>")
        lines.append(f"  O'rtacha: {report.avg_health_score}/100")
        hd = report.health_distribution
        lines.append(
            f"  \U0001f7e2 Sog'lom: {hd['healthy']} | "
            f"\U0001f7e1 Xavfli: {hd['at_risk']} | "
            f"\U0001f534 Kritik: {hd['critical']}"
        )
        if report.cooling_count:
            lines.append(f"  \u2744\ufe0f Sovumoqda: {report.cooling_count} lid")
        if report.top_signals:
            from core.services.conversation_intelligence_service import SIGNAL_LABELS

            sig_parts = []
            for s in report.top_signals[:4]:
                label = SIGNAL_LABELS.get(s["signal"], s["signal"])
                sig_parts.append(f"{label}({s['count']})")
            lines.append(f"  \U0001f4e1 Signallar: {', '.join(sig_parts)}")

    # ── Autopilot metrics ───────────────────────────────────────────
    has_autopilot = (
        report.opportunity_count
        or report.at_risk_count
        or report.closing_ready_count
        or report.autopilot_action_distribution
    )
    if has_autopilot:
        lines.append("")
        lines.append("<b>\U0001f916 Sales Autopilot:</b>")
        lines.append(
            f"  \U0001f525 Imkoniyatlar: {report.opportunity_count} | "
            f"\u26a0\ufe0f Xavfli: {report.at_risk_count} | "
            f"\U0001f3af Yopishga tayyor: {report.closing_ready_count}"
        )
        if report.autopilot_action_distribution:
            from core.services.next_best_action_service import ACTION_LABELS

            act_parts = []
            for ad in report.autopilot_action_distribution[:4]:
                label = ACTION_LABELS.get(ad["action"], ad["action"])
                act_parts.append(f"{label}({ad['count']})")
            lines.append(f"  \U0001f4cb Amallar: {', '.join(act_parts)}")

    # ── Closing readiness ────────────────────────────────────────────
    has_closing = (
        report.close_opportunity_count
        or report.close_loss_risk_count
        or any(v > 0 for v in report.closing_readiness_distribution.values())
    )
    if has_closing:
        lines.append("")
        lines.append("<b>\U0001f3af AI Closer:</b>")
        crd = report.closing_readiness_distribution
        lines.append(
            f"  \U0001f534 Tayyor: {crd.get('READY_TO_CLOSE', 0)} | "
            f"\U0001f7e1 Yaqin: {crd.get('NEAR_CLOSE', 0)} | "
            f"\u26aa Tayyor emas: {crd.get('NOT_READY', 0)}"
        )
        if report.close_loss_risk_count:
            lines.append(f"  \u26a0\ufe0f Yo'qotish xavfi: {report.close_loss_risk_count} lid")
        if report.closing_tactic_distribution:
            from core.services.closing_readiness_service import TACTIC_LABELS

            tactic_parts = []
            for td in report.closing_tactic_distribution[:4]:
                label = TACTIC_LABELS.get(td["tactic"], td["tactic"])
                tactic_parts.append(f"{label}({td['count']})")
            lines.append(f"  \U0001f3c6 Taktikalar: {', '.join(tactic_parts)}")

    # ── Auto-seller ────────────────────────────────────────────────────
    has_auto = report.auto_reply_count or report.auto_escalation_count
    if has_auto:
        lines.append("")
        lines.append("<b>\U0001f916 Auto-Seller:</b>")
        lines.append(
            f"  \U0001f4ac Avto-javob: {report.auto_reply_count} lid | "
            f"\U0001f6a8 Escalation: {report.auto_escalation_count}"
        )
        if report.auto_reply_confidence_avg > 0:
            lines.append(f"  \U0001f3af Ishonch: {report.auto_reply_confidence_avg:.0%}")

    # ── AI Tactic Outcomes (outcome-based learning) ──────────────────
    if tactic_perf_report and tactic_perf_report.total_resolved > 0:
        lines.append("")
        lines.append("<b>\U0001f9ea AI Taktikalar (outcome):</b>")
        lines.append(
            f"  \U0001f4ca Kuzatilgan: {tactic_perf_report.total_tracked} | "
            f"Hal qilingan: {tactic_perf_report.total_resolved}"
        )
        if tactic_perf_report.best_negotiation_tactic:
            from core.services.negotiation_engine_service import TACTIC_LABELS as _NTL

            label = _NTL.get(
                tactic_perf_report.best_negotiation_tactic,
                tactic_perf_report.best_negotiation_tactic,
            )
            lines.append(f"  \U0001f3c6 Muzokara: {label}")
        if tactic_perf_report.worst_negotiation_tactic:
            from core.services.negotiation_engine_service import TACTIC_LABELS as _NTL2

            label = _NTL2.get(
                tactic_perf_report.worst_negotiation_tactic,
                tactic_perf_report.worst_negotiation_tactic,
            )
            lines.append(f"  \u274c Eng yomon: {label}")
        if tactic_perf_report.best_closer_action:
            lines.append(f"  \U0001f3af Closer: {tactic_perf_report.best_closer_action}")
        if tactic_perf_report.best_followup_type:
            from core.services.followup_brain_service import FU_TYPE_LABELS as _FTL

            label = _FTL.get(
                tactic_perf_report.best_followup_type,
                tactic_perf_report.best_followup_type,
            )
            lines.append(f"  \U0001f501 Follow-up: {label}")
        # Top 3 tactics by success rate
        for t in tactic_perf_report.tactics[:3]:
            lines.append(f"  {t.tactic_name}: {t.success_rate:.0%} " f"({t.total_samples} ta)")

    # ── Recommendations ───────────────────────────────────────────────
    if report.recommendations:
        lines.append("")
        lines.append("<b>\U0001f4a1 Tavsiyalar:</b>")
        for i, rec in enumerate(report.recommendations, 1):
            lines.append(f"  {i}. {rec}")

    return "\n".join(lines)


_STAGE_LABELS_SHORT: dict[str, str] = {
    "NEW": "Yangi",
    "PACKAGE_SELECTED": "Paket",
    "CONTACTED": "Bog'lanilgan",
    "MEASUREMENT": "O'lchov",
    "QUOTE": "Narx",
    "DEAL": "Kelishilgan",
    "INSTALLATION": "O'rnatish",
    "COMPLETED": "Tugallangan",
    "LOST": "Yo'qotilgan",
}
