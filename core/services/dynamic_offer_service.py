"""
core.services.dynamic_offer_service
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Deterministic rule-based engine that selects the best offer/CTA for a
customer based on their intent, objection, urgency, lead score, and
journey state.  Pure functions — no I/O, no side effects.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from core.schemas.dynamic_offer import DynamicOffer, OfferContext
from shared.constants.enums import (
    CustomerIntent,
    ObjectionType,
    OfferCTA,
    OfferPriority,
    OfferType,
)

# ── Terminal / blocked states ─────────────────────────────────────────────────

_TERMINAL_STATES: frozenset[str] = frozenset(
    {
        "stopped",
        "lost",
        "closed",
    }
)

# ── Message hints ─────────────────────────────────────────────────────────────

_HINTS: dict[str, str] = {
    OfferType.PRICE_CALCULATION.value
    + ":no_area": ("Kvadratingizni yozsangiz, taxminiy narxni hisoblab beraman."),
    OfferType.PRICE_CALCULATION.value
    + ":has_area": ("Qaysi turini tanlaysiz: oddiy, gulli yoki premium?"),
    OfferType.CHEAPER_OPTION.value: (
        "Arzonroq variantdan ham hisoblab berish mumkin. " "Operator bilan kelishiladi."
    ),
    OfferType.WARRANTY_TRUST.value: ("Bajarilgan ishlar va kafolat bo'yicha ma'lumot berish."),
    OfferType.PORTFOLIO_SOCIAL_PROOF.value: ("Oldingi mijozlar ishlarini ko'rsatish."),
    OfferType.DESIGN_HELP.value: ("Shoshilmasdan katalogdan mos model tanlashga yordam berish."),
    OfferType.FAST_INSTALLATION.value: ("Tezkor o'lchov yoki operatorga ulash."),
    OfferType.OPERATOR_CONSULTATION.value: ("Operatorimiz sizga batafsil maslahat beradi."),
    OfferType.ORDER_CONTINUE.value: ("Buyurtmani davom ettiramizmi?"),
    OfferType.CALLBACK_REQUEST.value: (
        "Telefon raqamingizni yuborsangiz, operatorimiz siz bilan bog'lanadi."
    ),
    OfferType.DISCOUNT_DISCUSSION.value: ("Chegirma bo'yicha operator bilan kelishiladi."),
    OfferType.MEASUREMENT_VISIT.value: ("Usta kelib bepul o'lchov qilib beradi."),
    OfferType.PREMIUM_OPTION.value: ("Premium variantda qo'shimcha imkoniyatlar mavjud."),
}

# ── Recommended button sets ───────────────────────────────────────────────────

_BUTTONS: dict[str, list[tuple[str, str]]] = {
    OfferCTA.ASK_AREA.value: [
        ("📐 Maydon hisoblash", "ai:start_price"),
    ],
    OfferCTA.ASK_DESIGN_TYPE.value: [
        ("🎨 Katalog", "ai:show_catalog"),
        ("💰 Narx hisoblash", "ai:start_price"),
    ],
    OfferCTA.OPEN_PRICE_CALCULATOR.value: [
        ("💰 Narx hisoblash", "ai:start_price"),
    ],
    OfferCTA.CONTINUE_ORDER.value: [
        ("✅ Davom etish", "agentfu:resume"),
        ("👨‍💼 Operator", "agentfu:operator"),
    ],
    OfferCTA.CONTACT_OPERATOR.value: [
        ("👨‍💼 Operator", "agentfu:operator"),
    ],
    OfferCTA.SHOW_CATALOG.value: [
        ("🎨 Katalog", "ai:show_catalog"),
    ],
    OfferCTA.SEND_PHOTO.value: [
        ("📸 Rasm yuborish", "ai:send_photo"),
    ],
    OfferCTA.REQUEST_PHONE.value: [
        ("📞 Telefon yuborish", "agentfu:phone"),
        ("👨‍💼 Operator", "agentfu:operator"),
    ],
}

# ── No-offer singleton ────────────────────────────────────────────────────────

_NO_OFFER = DynamicOffer(
    offer_type=OfferType.NO_OFFER.value,
    cta=OfferCTA.WAIT.value,
    priority=OfferPriority.LOW.value,
    confidence_score=0,
    reason="",
)


class DynamicOfferService:
    """Rule-based offer selection engine."""

    @staticmethod
    def choose_offer(
        memory: dict[str, Any],
        lead_signal: dict[str, Any] | None = None,
        recent_events: list[dict[str, Any]] | None = None,
    ) -> DynamicOffer:
        signal = lead_signal or {}
        events = recent_events or []

        ctx = DynamicOfferService._build_context(memory, signal, events)
        safety = DynamicOfferService._check_safety(ctx, memory)
        if safety is not None:
            return safety

        offer = DynamicOfferService._select_offer(ctx, memory, events)
        return DynamicOfferService._apply_post_rules(offer, ctx)

    @staticmethod
    def choose_offer_type(ctx: OfferContext) -> str:
        return DynamicOfferService._select_offer_type(ctx)

    @staticmethod
    def choose_cta(offer_type: str, ctx: OfferContext) -> str:
        return DynamicOfferService._select_cta(offer_type, ctx)

    @staticmethod
    def calculate_offer_priority(
        offer_type: str,
        ctx: OfferContext,
    ) -> str:
        if ctx.urgency == "high":
            return OfferPriority.URGENT.value
        if ctx.lead_temperature == "hot" or ctx.lead_score >= 70:
            return OfferPriority.HIGH.value
        if ctx.lead_temperature == "warm" or ctx.lead_score >= 31:
            return OfferPriority.MEDIUM.value
        return OfferPriority.LOW.value

    @staticmethod
    def build_message_hint(offer_type: str, ctx: OfferContext) -> str:
        if offer_type == OfferType.PRICE_CALCULATION.value:
            key = offer_type + (":has_area" if ctx.area_m2 else ":no_area")
            return _HINTS.get(key, "")
        return _HINTS.get(offer_type, "")

    @staticmethod
    def build_recommended_buttons(cta: str) -> list[tuple[str, str]]:
        return list(_BUTTONS.get(cta, []))

    @staticmethod
    def validate_offer(offer: DynamicOffer) -> tuple[bool, str]:
        if not offer.offer_type:
            return False, "missing_offer_type"
        if not offer.cta:
            return False, "missing_cta"
        if "eng arzon" in offer.message_hint.lower():
            return False, "unsafe_claim_cheapest"
        if "bugun qilamiz" in offer.message_hint.lower():
            return False, "unsafe_promise_today"
        return True, "ok"

    @staticmethod
    def store_offer_to_memory(
        memory_data: dict[str, Any],
        offer: DynamicOffer,
    ) -> dict[str, Any]:
        updated = dict(memory_data)
        updated["last_dynamic_offer"] = {
            "offer_type": offer.offer_type,
            "cta": offer.cta,
            "priority": offer.priority,
            "confidence_score": offer.confidence_score,
            "reason": offer.reason,
            "message_hint": offer.message_hint,
            "should_notify_admin": offer.should_notify_admin,
            "created_at": datetime.now(UTC).isoformat(),
        }
        return updated

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _build_context(
        memory: dict[str, Any],
        signal: dict[str, Any],
        events: list[dict[str, Any]],
    ) -> OfferContext:
        md = memory.get("memory_data") or {}
        intent = signal.get("intent") or md.get("last_intent") or "unclear"
        objection = signal.get("objection_type") or md.get("objection_type")
        urgency = signal.get("urgency") or md.get("urgency") or "low"
        lead_score = md.get("lead_score", 0)
        if isinstance(signal.get("lead_score_delta"), int):
            lead_score = max(0, min(lead_score + signal["lead_score_delta"], 100))
        temp = memory.get("lead_temperature") or "cold"
        area = memory.get("area_m2") or md.get("area_m2")
        has_phone = bool(memory.get("phone_masked"))
        has_image = any(e.get("event_type") == "image_sent" for e in events)
        followup_enabled = memory.get("followup_enabled", True)
        state = memory.get("customer_state") or md.get("customer_state") or "new_visitor"

        return OfferContext(
            intent=intent,
            objection_type=objection,
            urgency=urgency,
            lead_score=lead_score,
            lead_temperature=temp,
            area_m2=area,
            has_phone=has_phone,
            has_image=has_image,
            followup_enabled=followup_enabled,
            customer_state=state,
        )

    @staticmethod
    def _check_safety(
        ctx: OfferContext,
        memory: dict[str, Any],
    ) -> DynamicOffer | None:
        flags: list[str] = []

        if not ctx.followup_enabled:
            flags.append("followup_disabled")
        if ctx.customer_state in _TERMINAL_STATES:
            flags.append("terminal_state")
        if ctx.intent == CustomerIntent.STOP_REQUEST.value:
            flags.append("stop_request")

        if flags:
            cta = OfferCTA.STOP.value if "stop_request" in flags else OfferCTA.WAIT.value
            return DynamicOffer(
                offer_type=OfferType.NO_OFFER.value,
                cta=cta,
                priority=OfferPriority.LOW.value,
                confidence_score=0,
                reason="; ".join(flags),
                safety_flags=flags,
            )
        return None

    @staticmethod
    def _select_offer(
        ctx: OfferContext,
        memory: dict[str, Any],
        events: list[dict[str, Any]],
    ) -> DynamicOffer:
        offer_type = DynamicOfferService._select_offer_type(ctx)
        cta = DynamicOfferService._select_cta(offer_type, ctx)
        priority = DynamicOfferService.calculate_offer_priority(offer_type, ctx)
        hint = DynamicOfferService.build_message_hint(offer_type, ctx)
        buttons = DynamicOfferService.build_recommended_buttons(cta)
        confidence = DynamicOfferService._compute_confidence(ctx)
        reason = DynamicOfferService._build_reason(offer_type, ctx)
        notify = DynamicOfferService._should_notify(offer_type, ctx)

        return DynamicOffer(
            offer_type=offer_type,
            cta=cta,
            priority=priority,
            confidence_score=confidence,
            reason=reason,
            message_hint=hint,
            recommended_buttons=buttons,
            should_notify_admin=notify,
        )

    @staticmethod
    def _select_offer_type(ctx: OfferContext) -> str:
        # High urgency overrides most other signals
        if ctx.urgency == "high":
            return OfferType.FAST_INSTALLATION.value

        # Objection-based offers
        if ctx.objection_type == ObjectionType.PRICE.value:
            return OfferType.CHEAPER_OPTION.value
        if ctx.objection_type == ObjectionType.TRUST.value:
            return OfferType.WARRANTY_TRUST.value
        if ctx.objection_type == ObjectionType.NOT_READY.value:
            return OfferType.DESIGN_HELP.value
        if ctx.objection_type == ObjectionType.COMPARING.value:
            return OfferType.PORTFOLIO_SOCIAL_PROOF.value
        if ctx.objection_type == ObjectionType.SPOUSE_FAMILY_DECISION.value:
            return OfferType.DESIGN_HELP.value

        # Intent-based offers
        if ctx.intent == CustomerIntent.WANTS_OPERATOR.value:
            return OfferType.OPERATOR_CONSULTATION.value
        if ctx.intent == CustomerIntent.WANTS_ORDER.value:
            return OfferType.ORDER_CONTINUE.value
        if ctx.intent == CustomerIntent.WANTS_MEASUREMENT.value:
            return OfferType.MEASUREMENT_VISIT.value
        if ctx.intent == CustomerIntent.WANTS_PRICE.value:
            return OfferType.PRICE_CALCULATION.value
        if ctx.intent == CustomerIntent.WANTS_CATALOG.value:
            return OfferType.DESIGN_HELP.value
        if ctx.intent == CustomerIntent.WANTS_DISCOUNT.value:
            return OfferType.DISCOUNT_DISCUSSION.value

        # Score-based offers
        if ctx.lead_score >= 70:
            if ctx.has_phone:
                return OfferType.OPERATOR_CONSULTATION.value
            return OfferType.CALLBACK_REQUEST.value

        # Image sent
        if ctx.has_image:
            return OfferType.DESIGN_HELP.value

        # Cold + unclear → no offer
        if ctx.lead_temperature == "cold":
            return OfferType.NO_OFFER.value

        # Warm lead with no specific signal
        if ctx.lead_temperature == "warm":
            if ctx.area_m2:
                return OfferType.PRICE_CALCULATION.value
            return OfferType.DESIGN_HELP.value

        return OfferType.NO_OFFER.value

    @staticmethod
    def _select_cta(offer_type: str, ctx: OfferContext) -> str:
        if offer_type == OfferType.NO_OFFER.value:
            return OfferCTA.WAIT.value

        if offer_type == OfferType.PRICE_CALCULATION.value:
            if ctx.area_m2:
                return OfferCTA.ASK_DESIGN_TYPE.value
            return OfferCTA.ASK_AREA.value

        if offer_type == OfferType.CHEAPER_OPTION.value:
            return OfferCTA.OPEN_PRICE_CALCULATOR.value

        if offer_type in (
            OfferType.WARRANTY_TRUST.value,
            OfferType.PORTFOLIO_SOCIAL_PROOF.value,
        ):
            return OfferCTA.SHOW_CATALOG.value

        if offer_type == OfferType.DESIGN_HELP.value:
            return OfferCTA.SHOW_CATALOG.value

        if offer_type == OfferType.FAST_INSTALLATION.value:
            return OfferCTA.CONTACT_OPERATOR.value

        if offer_type == OfferType.OPERATOR_CONSULTATION.value:
            return OfferCTA.CONTACT_OPERATOR.value

        if offer_type == OfferType.ORDER_CONTINUE.value:
            return OfferCTA.CONTINUE_ORDER.value

        if offer_type == OfferType.CALLBACK_REQUEST.value:
            return OfferCTA.REQUEST_PHONE.value

        if offer_type == OfferType.DISCOUNT_DISCUSSION.value:
            return OfferCTA.CONTACT_OPERATOR.value

        if offer_type == OfferType.MEASUREMENT_VISIT.value:
            return OfferCTA.CONTACT_OPERATOR.value

        if offer_type == OfferType.PREMIUM_OPTION.value:
            return OfferCTA.SHOW_CATALOG.value

        return OfferCTA.WAIT.value

    @staticmethod
    def _compute_confidence(ctx: OfferContext) -> int:
        score = 30
        if ctx.intent != "unclear":
            score += 25
        if ctx.objection_type:
            score += 15
        if ctx.urgency != "low":
            score += 10
        if ctx.area_m2:
            score += 10
        if ctx.lead_score >= 50:
            score += 10
        return min(score, 100)

    @staticmethod
    def _build_reason(offer_type: str, ctx: OfferContext) -> str:
        parts: list[str] = []
        if ctx.intent != "unclear":
            parts.append(f"intent={ctx.intent}")
        if ctx.objection_type:
            parts.append(f"objection={ctx.objection_type}")
        if ctx.urgency != "low":
            parts.append(f"urgency={ctx.urgency}")
        if ctx.lead_score >= 70:
            parts.append("hot_score")
        if ctx.has_image:
            parts.append("image_sent")
        if not parts:
            parts.append(f"temp={ctx.lead_temperature}")
        return f"{offer_type}: {', '.join(parts)}"

    @staticmethod
    def _should_notify(offer_type: str, ctx: OfferContext) -> bool:
        if ctx.lead_temperature == "cold":
            return False
        if ctx.lead_score >= 70:
            return True
        if ctx.has_image:
            return True
        if offer_type in (
            OfferType.OPERATOR_CONSULTATION.value,
            OfferType.CALLBACK_REQUEST.value,
        ):
            return ctx.lead_temperature in ("warm", "hot")
        return False

    @staticmethod
    def _apply_post_rules(
        offer: DynamicOffer,
        ctx: OfferContext,
    ) -> DynamicOffer:
        flags: list[str] = list(offer.safety_flags)

        if ctx.lead_temperature == "cold" and offer.priority in (
            OfferPriority.HIGH.value,
            OfferPriority.URGENT.value,
        ):
            flags.append("cold_lead_priority_downgrade")

        if flags and flags != offer.safety_flags:
            return DynamicOffer(
                offer_type=offer.offer_type,
                cta=offer.cta,
                priority=offer.priority,
                confidence_score=offer.confidence_score,
                reason=offer.reason,
                message_hint=offer.message_hint,
                recommended_buttons=offer.recommended_buttons,
                should_notify_admin=offer.should_notify_admin,
                safety_flags=flags,
                metadata=offer.metadata,
            )
        return offer
