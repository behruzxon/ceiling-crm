"""
apps.bot.handlers.admin.analytics
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
/analytics [days] — Sales Analytics: concise performance summary.

Loads leads for the requested period, enriches a sample with Redis AI
memory, runs ``build_sales_analytics``, and formats a compact admin card.

Access: ADMIN / SUPERADMIN roles.
"""
from __future__ import annotations

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
        _tid = data.get("tenant_id")
        factory = get_session_factory()
        async with factory() as session:
            repo = get_lead_repo(session, tenant_id=_tid)
            leads = await repo.get_leads_for_analytics(days=days, limit=500)

        if not leads:
            await message.answer(
                f"\U0001f4ca Oxirgi {days} kunda lidlar topilmadi."
            )
            return

        # Build signal dicts with optional Redis enrichment
        leads_data = await _build_leads_data(leads)

        # Run analytics
        from core.services.sales_analytics_service import build_sales_analytics
        report = build_sales_analytics(leads_data)

        # Format and send
        text = _format_report(report, days)

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
        try:
            from apps.bot.handlers.private.ai_support import _load_ai_memory
            mem = await _load_ai_memory(lead.user_id)
            if mem:
                ld["buyer_type"] = mem.get("buyer_type")
                ld["last_objection"] = mem.get("last_objection")
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

        result.append(ld)

    return result


def _format_report(report, days: int) -> str:
    """Format SalesAnalytics into a concise Telegram card."""
    lines: list[str] = []

    # ── Header ────────────────────────────────────────────────────────
    lines.append(
        f"\U0001f4ca <b>Sotuv tahlili — {days} kun</b>\n"
    )

    # ── Total summary ─────────────────────────────────────────────────
    lines.append(
        f"\U0001f4cb Jami: {report.total_leads} | "
        f"\u2705 {report.won_leads} | "
        f"\u274c {report.lost_leads} | "
        f"\U0001f504 {report.active_leads}"
    )
    lines.append(
        f"\U0001f3af Konversiya: {report.conversion_rate:.1%}"
    )
    lines.append(
        f"\U0001f4ca O'rtacha ball: {report.avg_score}"
    )

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
        lines.append(
            f"\U0001f4b0 Umumiy daromad: {report.total_estimated_revenue:,} UZS"
        )
        lines.append(
            f"\U0001f4b5 Har bir lid: {report.avg_revenue_per_lead:,} UZS"
        )

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
        label = _STAGE_LABELS_SHORT.get(
            report.largest_dropoff_stage, report.largest_dropoff_stage
        )
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
            lines.append(
                f"  {label}: {bt['count']} | "
                f"\u2705{bt['won']} ({bt['rate']:.0%})"
            )

    # ── Follow-up ─────────────────────────────────────────────────────
    fu = report.followup_stats
    if fu.get("with_followup_pct", 0) > 0:
        lines.append("")
        lines.append("<b>\U0001f501 Follow-up:</b>")
        lines.append(
            f"  Qamrov: {fu['with_followup_pct']:.0%} lidlar"
        )
        lines.append(
            f"  O'rtacha (won): {fu['avg_followups_won']} | "
            f"(lost): {fu['avg_followups_lost']}"
        )
        if report.best_followup_type:
            from core.services.followup_brain_service import FU_TYPE_LABELS
            best = report.best_followup_type
            fu_label = FU_TYPE_LABELS.get(best["type"], best["type"])
            lines.append(
                f"  \U0001f3c6 Eng yaxshi: {fu_label} ({best['rate']:.0%})"
            )

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
