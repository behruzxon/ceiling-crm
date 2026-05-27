"""Conversation replay builder — pure functions, no DB I/O."""

from __future__ import annotations

import hashlib
import re

from core.schemas.crm_conversation_replay import (
    ConversationReplayEvent,
    ConversationReplayResult,
    ConversationReplaySummary,
)

_TOKEN_RE = re.compile(r"(sk-[a-zA-Z0-9]{8,}|bot\d{5,}:[A-Za-z0-9_-]{20,}|Bearer\s+\S{10,})", re.I)
_PHONE_RE = re.compile(r"\+?\d[\d\s\-]{7,14}\d")
_SECRET_PATTERNS = re.compile(r"(postgresql://\S+|redis://\S+|OPENAI_API_KEY\s*=\s*\S+)", re.I)

VALID_EVENT_TYPES = frozenset(
    {
        "user_message",
        "bot_reply",
        "ai_detected_intent",
        "price_estimate",
        "objection_detected",
        "handoff_requested",
        "handoff_status_changed",
        "phone_shared",
        "order_started",
        "measurement_requested",
        "catalog_viewed",
        "stop_requested",
        "operator_reply",
        "system_event",
    }
)

ICON_MAP: dict[str, str] = {
    "user_message": "user",
    "bot_reply": "bot",
    "ai_detected_intent": "brain",
    "price_estimate": "calculator",
    "objection_detected": "alert-triangle",
    "handoff_requested": "phone-forwarded",
    "handoff_status_changed": "refresh",
    "phone_shared": "phone",
    "order_started": "shopping-cart",
    "measurement_requested": "ruler",
    "catalog_viewed": "image",
    "stop_requested": "x-circle",
    "operator_reply": "headphones",
    "system_event": "settings",
}

INTENT_KEYWORDS: dict[str, list[str]] = {
    "price": ["narx", "qancha", "price", "necha"],
    "measurement": ["o'lchov", "measurement", "o'lchash"],
    "catalog": ["katalog", "catalog", "dizayn", "rasm"],
    "order": ["buyurtma", "zakaz", "order"],
    "stop": ["kerak emas", "stop", "rahmat", "to'xta", "bas"],
    "operator": ["operator", "odam", "jonli"],
    "phone": ["telefon", "raqam", "nomer"],
    "objection_price": ["qimmat", "arzon", "expensive", "cheap"],
    "objection_delay": ["keyin", "keyinroq", "later", "hali"],
    "objection_compare": ["raqobatchi", "boshqa", "compare"],
}


def _make_event_id(event_type: str, ts: str | None, index: int = 0) -> str:
    raw = f"{event_type}:{ts or ''}:{index}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def sanitize_preview(text: str | None, max_len: int = 200) -> str | None:
    if not text:
        return None
    cleaned = _TOKEN_RE.sub("[REDACTED]", text)
    cleaned = _SECRET_PATTERNS.sub("[REDACTED]", cleaned)
    cleaned = cleaned.replace("<", "&lt;").replace(">", "&gt;")
    return cleaned[:max_len]


def sanitize_metadata(metadata: dict | None) -> str | None:
    if not metadata:
        return None
    safe_keys = [
        "intent",
        "area_m2",
        "district",
        "ceiling_type",
        "design_type",
        "lead_score",
        "temperature",
        "objection_type",
        "handoff_status",
        "price_estimate",
    ]
    parts = []
    for k in safe_keys:
        v = metadata.get(k)
        if v is not None:
            parts.append(f"{k}: {v}")
    return " | ".join(parts) if parts else None


def mask_phone_in_text(text: str) -> str:
    def _mask(m: re.Match) -> str:
        digits = m.group()
        if len(digits) < 6:
            return digits
        return digits[:4] + "****" + digits[-2:]

    return _PHONE_RE.sub(_mask, text)


def detect_intent(text: str) -> str | None:
    lower = text.lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return intent
    return None


def classify_message_event(
    message: dict,
    index: int = 0,
    contact_id: int | None = None,
) -> ConversationReplayEvent:
    direction = message.get("direction", "")
    sender = message.get("sender_type", "")
    text = message.get("text", "") or ""
    created = message.get("created_at", "")
    ts = str(created)[:19] if created else None

    if direction == "inbound":
        actor = "user"
        event_type = "user_message"
        title = "Mijoz xabari"
    elif sender == "operator":
        actor = "operator"
        event_type = "operator_reply"
        title = "Operator javob berdi"
    else:
        actor = "bot"
        event_type = "bot_reply"
        title = "Bot javob berdi"

    preview = sanitize_preview(text)
    if preview:
        preview = mask_phone_in_text(preview)

    intent = detect_intent(text) if direction == "inbound" else None

    return ConversationReplayEvent(
        event_id=_make_event_id(event_type, ts, index),
        event_type=event_type,
        actor=actor,
        title=title,
        description=text[:80] if text else "",
        message_preview=preview,
        intent=intent,
        severity=None,
        status=None,
        related_contact_id=contact_id,
        icon_key=ICON_MAP.get(event_type, "circle"),
        timestamp=ts,
    )


def build_intent_event(
    text: str,
    intent: str,
    ts: str | None = None,
    contact_id: int | None = None,
    index: int = 0,
) -> ConversationReplayEvent:
    intent_titles = {
        "price": "AI narx qiziqishini aniqladi",
        "measurement": "AI o'lchov so'rovini aniqladi",
        "catalog": "AI katalog qiziqishini aniqladi",
        "order": "AI buyurtma niyatini aniqladi",
        "stop": "AI to'xtatish so'rovini aniqladi",
        "operator": "AI operator so'rovini aniqladi",
        "phone": "AI telefon ulashishini aniqladi",
        "objection_price": "AI narx e'tirozini aniqladi",
        "objection_delay": "AI kechiktirish e'tirozini aniqladi",
        "objection_compare": "AI solishtirish e'tirozini aniqladi",
    }
    return ConversationReplayEvent(
        event_id=_make_event_id("ai_detected_intent", ts, index),
        event_type="ai_detected_intent",
        actor="ai",
        title=intent_titles.get(intent, f"AI intent aniqladi: {intent}"),
        description=f"Intent: {intent}",
        intent=intent,
        severity="info",
        related_contact_id=contact_id,
        icon_key=ICON_MAP["ai_detected_intent"],
        timestamp=ts,
    )


def build_price_event(
    trace_or_memory: dict,
    contact_id: int | None = None,
    index: int = 0,
) -> ConversationReplayEvent:
    ts = str(trace_or_memory.get("timestamp", ""))[:19] or None
    estimate = trace_or_memory.get("price_estimate") or trace_or_memory.get("last_price_estimate")
    area = trace_or_memory.get("area_m2", "")
    design = trace_or_memory.get("design_type", "")
    desc = "Taxminiy narx hisoblandi"
    if estimate:
        desc += f": {estimate} UZS"
    if area:
        desc += f" ({area} m²"
        if design:
            desc += f", {design}"
        desc += ")"
    return ConversationReplayEvent(
        event_id=_make_event_id("price_estimate", ts, index),
        event_type="price_estimate",
        actor="bot",
        title="Taxminiy narx hisoblandi",
        description=desc,
        severity="info",
        status="calculated",
        related_contact_id=contact_id,
        metadata_summary=sanitize_metadata(trace_or_memory),
        icon_key=ICON_MAP["price_estimate"],
        timestamp=ts,
    )


def build_objection_event(
    trace: dict,
    contact_id: int | None = None,
    index: int = 0,
) -> ConversationReplayEvent:
    obj_type = trace.get("objection_type", "unknown")
    ts = str(trace.get("timestamp", ""))[:19] or None
    obj_titles = {
        "price": "Mijoz narx bo'yicha e'tiroz bildirdi",
        "delay": "Mijoz kechiktirmoqchi",
        "trust": "Mijoz ishonch muammosini bildirdi",
        "compare": "Mijoz raqobatchi narxini solishtirdi",
    }
    return ConversationReplayEvent(
        event_id=_make_event_id("objection_detected", ts, index),
        event_type="objection_detected",
        actor="user",
        title=obj_titles.get(obj_type, f"E'tiroz: {obj_type}"),
        description=f"E'tiroz turi: {obj_type}",
        severity="warning",
        intent=f"objection_{obj_type}",
        related_contact_id=contact_id,
        icon_key=ICON_MAP["objection_detected"],
        timestamp=ts,
    )


def build_handoff_event(
    handoff: dict,
    contact_id: int | None = None,
    index: int = 0,
) -> ConversationReplayEvent:
    status = handoff.get("status", "pending")
    ts = str(handoff.get("created_at", ""))[:19] or None
    handoff_id = handoff.get("id")
    if status == "pending":
        title = "Operatorga ulash so'raldi"
        event_type = "handoff_requested"
    else:
        title = f"Handoff holati: {status}"
        event_type = "handoff_status_changed"
    reason = handoff.get("reason", "")
    desc = f"Handoff: {status}"
    if reason:
        desc += f" — {reason}"
    return ConversationReplayEvent(
        event_id=_make_event_id(event_type, ts, index),
        event_type=event_type,
        actor="system",
        title=title,
        description=desc,
        severity="warning" if status == "pending" else "info",
        status=status,
        related_contact_id=contact_id,
        related_handoff_id=handoff_id,
        icon_key=ICON_MAP.get(event_type, "phone-forwarded"),
        timestamp=ts,
    )


def build_phone_event(
    ts: str | None = None,
    contact_id: int | None = None,
    index: int = 0,
) -> ConversationReplayEvent:
    return ConversationReplayEvent(
        event_id=_make_event_id("phone_shared", ts, index),
        event_type="phone_shared",
        actor="user",
        title="Mijoz telefon raqamini berdi",
        description="Telefon raqami ulashildi",
        severity="info",
        status="collected",
        related_contact_id=contact_id,
        icon_key=ICON_MAP["phone_shared"],
        timestamp=ts,
    )


def build_stop_event(
    ts: str | None = None,
    contact_id: int | None = None,
    text: str = "",
    index: int = 0,
) -> ConversationReplayEvent:
    preview = sanitize_preview(text) if text else None
    return ConversationReplayEvent(
        event_id=_make_event_id("stop_requested", ts, index),
        event_type="stop_requested",
        actor="user",
        title="Mijoz stop so'radi",
        description="Foydalanuvchi xizmatni to'xtatishni so'radi",
        message_preview=preview,
        severity="warning",
        status="stopped",
        related_contact_id=contact_id,
        icon_key=ICON_MAP["stop_requested"],
        timestamp=ts,
    )


def sort_events_chronologically(
    events: list[ConversationReplayEvent],
) -> list[ConversationReplayEvent]:
    def _sort_key(e: ConversationReplayEvent) -> str:
        return e.timestamp or ""

    return sorted(events, key=_sort_key)


def build_summary(
    events: list[ConversationReplayEvent],
) -> ConversationReplaySummary:
    user_msgs = sum(1 for e in events if e.event_type == "user_message")
    bot_msgs = sum(1 for e in events if e.event_type in ("bot_reply", "operator_reply"))
    prices = sum(1 for e in events if e.event_type == "price_estimate")
    handoffs = sum(
        1 for e in events if e.event_type in ("handoff_requested", "handoff_status_changed")
    )
    objections = sum(1 for e in events if e.event_type == "objection_detected")
    stops = sum(1 for e in events if e.event_type == "stop_requested")

    timestamps = [e.timestamp for e in events if e.timestamp]
    first = min(timestamps) if timestamps else None
    last = max(timestamps) if timestamps else None

    action = _recommend_action(events)

    return ConversationReplaySummary(
        total_events=len(events),
        user_messages=user_msgs,
        bot_replies=bot_msgs,
        price_events=prices,
        handoff_events=handoffs,
        objections=objections,
        stop_events=stops,
        first_seen_at=first,
        last_event_at=last,
        recommended_next_action=action,
    )


def _recommend_action(events: list[ConversationReplayEvent]) -> str:
    if not events:
        return "Hali harakatlar yo'q"

    has_stop = any(e.event_type == "stop_requested" for e in events)
    if has_stop:
        return "Mijoz to'xtatdi — qayta ulanmang"

    has_handoff = any(e.event_type == "handoff_requested" for e in events)
    if has_handoff:
        has_resolved = any(
            e.event_type == "handoff_status_changed" and e.status in ("resolved", "closed")
            for e in events
        )
        if not has_resolved:
            return "Handoff kutilmoqda — operatorga belgilang"

    has_objection = any(e.event_type == "objection_detected" for e in events)
    if has_objection:
        return "E'tiroz bor — maxsus taklif yuboring"

    has_price = any(e.event_type == "price_estimate" for e in events)
    if has_price:
        return "Narx hisoblangan — o'lchov taklif qiling"

    last_user = None
    last_reply = None
    for e in reversed(events):
        if e.event_type == "user_message" and not last_user:
            last_user = e
        if e.event_type in ("bot_reply", "operator_reply") and not last_reply:
            last_reply = e
        if last_user and last_reply:
            break

    if last_user and (not last_reply or (last_user.timestamp or "") > (last_reply.timestamp or "")):
        return "Javobsiz xabar bor — tezroq javob bering"

    return "Kuzatishda davom eting"


def build_replay(
    contact: dict,
    messages: list[dict] | None = None,
    traces: list[dict] | None = None,
    handoffs: list[dict] | None = None,
) -> ConversationReplayResult:
    contact_id = contact.get("id", 0)
    events: list[ConversationReplayEvent] = []

    for i, msg in enumerate(messages or []):
        evt = classify_message_event(msg, index=i, contact_id=contact_id)
        events.append(evt)

        if evt.actor == "user" and evt.intent:
            intent_evt = build_intent_event(
                text=msg.get("text", ""),
                intent=evt.intent,
                ts=evt.timestamp,
                contact_id=contact_id,
                index=i,
            )
            events.append(intent_evt)

            if evt.intent in ("objection_price", "objection_delay", "objection_compare"):
                obj_type = evt.intent.replace("objection_", "")
                obj_evt = build_objection_event(
                    {"objection_type": obj_type, "timestamp": evt.timestamp},
                    contact_id=contact_id,
                    index=i,
                )
                events.append(obj_evt)

            if evt.intent == "stop":
                stop_evt = build_stop_event(
                    ts=evt.timestamp,
                    contact_id=contact_id,
                    text=msg.get("text", ""),
                    index=i,
                )
                events.append(stop_evt)

    for i, trace in enumerate(traces or []):
        if trace.get("last_price_estimate") or trace.get("price_estimate"):
            events.append(build_price_event(trace, contact_id=contact_id, index=i))
        if trace.get("objection_type"):
            events.append(build_objection_event(trace, contact_id=contact_id, index=i))

    for i, ho in enumerate(handoffs or []):
        events.append(build_handoff_event(ho, contact_id=contact_id, index=i))

    if contact.get("phone"):
        phone_ts = str(contact.get("phone_shared_at", contact.get("created_at", "")))[:19] or None
        events.append(build_phone_event(ts=phone_ts, contact_id=contact_id))

    events = sort_events_chronologically(events)
    summary = build_summary(events)

    return ConversationReplayResult(
        contact_id=contact_id,
        events=events,
        summary=summary,
    )
