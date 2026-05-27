"""
core.services.operator_assistant_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Generates short, actionable operator reply suggestions based on lead state.

Produces four pre-written Uzbek replies tuned to the lead context:
  - **soft** — gentle informational opener
  - **close** — strong closing push
  - **budget** — budget-oriented alternative
  - **call_script** — short phone call script

This is an **on-demand** service — the admin taps a button to get
suggestions rather than receiving them automatically.

Usage::

    from core.services.operator_assistant_service import build_operator_assist

    assist = build_operator_assist(
        name="Aziz",
        score=65,
        buyer_type="fast_buyer",
        decision_stage="close_ready",
        area_m2=20.0,
        district="Qarshi",
    )
    # assist.operator_reply_close == "Aziz, bugun ustamiz ..."
"""
from __future__ import annotations

from dataclasses import dataclass

# ── Result dataclass ─────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class OperatorAssist:
    """Structured operator reply suggestions for a lead."""

    operator_reply_soft: str
    """Gentle informational opener."""

    operator_reply_close: str
    """Strong closing push."""

    operator_reply_budget: str
    """Budget-oriented alternative offer."""

    operator_call_script: str
    """Short phone call talking points."""

    operator_action_reason: str
    """Human-readable reason for the suggestion set."""


# ── Template fragments ───────────────────────────────────────────────────────

# Soft openers by buyer type
_SOFT_BY_BUYER: dict[str, str] = {
    "quality_buyer": (
        "{name}siz uchun premium dizaynlarimiz bor — "
        "xonangizga mos variantni ko'rsatib beraymi?"
    ),
    "fast_buyer": (
        "{name}nima kerakligini tushundim. "
        "Tez aniq javob beraman — xona maydonini ayting."
    ),
    "research_buyer": (
        "{name}batafsil ma'lumot va namunalar yuboraman. "
        "Qaysi xona uchun kerak?"
    ),
    "price_sensitive": (
        "{name}arzon va sifatli variantlarimiz bor. "
        "Xona maydonini aytsangiz aniq narx chiqaraman."
    ),
}
_SOFT_DEFAULT = (
    "{name}salom! Potolok bo'yicha qanday yordam kerak? "
    "Maydon va tumanni aytsangiz tez hisoblab beraman."
)

# Close pushes by stage / signals
_CLOSE_WITH_AREA = (
    "{name}sizning {area}m\u00b2 xona uchun bepul o'lchov qilib "
    "aniq narx chiqarib beramiz. Bugun yoki ertaga qachon qulay?"
)
_CLOSE_WITH_PHONE = (
    "{name}mutaxassisimiz tez orada qo'ng'iroq qilib, eng yaxshi variantni "
    "taklif qiladi. Qachon qulay?"
)
_CLOSE_DEFAULT = (
    "{name}xohlasangiz bepul o'lchov buyurtma qilsangiz, "
    "ustamiz kelib aniq narx chiqarib beradi. Majburiyat yo'q."
)

# Budget alternatives
_BUDGET_WITH_AREA = (
    "{name}byudjet variant ham bor — sifatli, 80 000 so'm/m\u00b2 dan. "
    "{area}m\u00b2 uchun taxminan {budget_est} so'm. Qiziqarli bo'lsa yozavering."
)
_BUDGET_DEFAULT = (
    "{name}byudjetga mos variant ham bor — sifatli material, "
    "80 000 so'm/m\u00b2 dan boshlanadi. Xona maydonini aytsangiz hisoblayman."
)

# Call scripts
_CALL_WITH_CONTEXT = (
    "Salom {raw_name}, siz {district_or_area} uchun yozgandingiz. "
    "Sizga mos variantni tez tushuntirib beraman. 2-3 daqiqa vaqtingiz bormi?"
)
_CALL_DEFAULT = (
    "Salom {raw_name}, siz potolok bo'yicha yozgandingiz. "
    "Hozir gaplashsak bo'ladimi? 2-3 daqiqa vaqtingiz bormi?"
)


# ── Main builder ─────────────────────────────────────────────────────────────


def build_operator_assist(
    *,
    name: str | None = None,
    score: int = 0,
    buyer_type: str | None = None,
    decision_stage: str | None = None,
    engagement_trend: str | None = None,
    last_objection: str | None = None,
    area_m2: float | None = None,
    district: str | None = None,
    design_type: str | None = None,
    phone_captured: bool = False,
    closing_attempted: bool = False,
    deal_probability_percent: int | None = None,
    negotiation_tactic: str | None = None,
    negotiation_escalated: bool = False,
    follow_up_type: str | None = None,
) -> OperatorAssist:
    """Build operator reply suggestions from available CRM signals.

    All parameters are keyword-only with safe defaults.
    Pure function — no I/O, fully deterministic.
    """
    # ── Name prefix (", " after name for personalisation) ───────────
    name_prefix = f"{name}, " if name else ""
    raw_name = name or "do'stim"

    # ── Soft reply ──────────────────────────────────────────────────
    soft_template = _SOFT_BY_BUYER.get(buyer_type or "", _SOFT_DEFAULT)
    soft = soft_template.format(name=name_prefix)

    # ── Close reply ─────────────────────────────────────────────────
    if area_m2 and area_m2 > 0:
        close = _CLOSE_WITH_AREA.format(
            name=name_prefix, area=f"{area_m2:g}"
        )
    elif phone_captured:
        close = _CLOSE_WITH_PHONE.format(name=name_prefix)
    else:
        close = _CLOSE_DEFAULT.format(name=name_prefix)

    # ── Budget reply ────────────────────────────────────────────────
    if area_m2 and area_m2 > 0:
        budget_est = f"{int(area_m2 * 80_000):,}"
        budget = _BUDGET_WITH_AREA.format(
            name=name_prefix, area=f"{area_m2:g}", budget_est=budget_est
        )
    else:
        budget = _BUDGET_DEFAULT.format(name=name_prefix)

    # ── Call script ─────────────────────────────────────────────────
    context_parts: list[str] = []
    if district:
        context_parts.append(district)
    if area_m2 and area_m2 > 0:
        context_parts.append(f"{area_m2:g} m\u00b2 xona")
    if design_type:
        context_parts.append(f"{design_type} dizayn")

    if context_parts:
        district_or_area = ", ".join(context_parts)
        call_script = _CALL_WITH_CONTEXT.format(
            raw_name=raw_name, district_or_area=district_or_area
        )
    else:
        call_script = _CALL_DEFAULT.format(raw_name=raw_name)

    # ── Action reason ───────────────────────────────────────────────
    reason = _build_reason(
        decision_stage=decision_stage,
        engagement_trend=engagement_trend,
        buyer_type=buyer_type,
        last_objection=last_objection,
        score=score,
        deal_probability_percent=deal_probability_percent,
    )

    return OperatorAssist(
        operator_reply_soft=soft,
        operator_reply_close=close,
        operator_reply_budget=budget,
        operator_call_script=call_script,
        operator_action_reason=reason,
    )


def _build_reason(
    *,
    decision_stage: str | None,
    engagement_trend: str | None,
    buyer_type: str | None,
    last_objection: str | None,
    score: int,
    deal_probability_percent: int | None,
) -> str:
    """Build a short reason string explaining the suggestion context."""
    parts: list[str] = []
    if decision_stage:
        from core.services.conversation_memory_graph_service import STAGE_LABELS
        parts.append(STAGE_LABELS.get(decision_stage, decision_stage))
    if engagement_trend:
        from core.services.conversation_memory_graph_service import TREND_LABELS
        parts.append(TREND_LABELS.get(engagement_trend, engagement_trend))
    if buyer_type:
        _bt = {
            "price_sensitive": "narxga sezgir",
            "quality_buyer": "sifat xaridori",
            "fast_buyer": "tez qaror",
            "research_buyer": "tadqiqotchi",
        }
        parts.append(_bt.get(buyer_type, buyer_type))
    if last_objection:
        parts.append(f"e'tiroz: {last_objection}")
    if deal_probability_percent is not None:
        parts.append(f"ehtimol: {deal_probability_percent}%")
    if not parts:
        parts.append(f"ball: {score}")
    return " | ".join(parts)
