"""Price estimate history builder — pure functions, no DB I/O."""

from __future__ import annotations

import hashlib
import re
from collections import Counter

from core.schemas.crm_price_estimate_history import (
    PriceEstimateHistoryItem,
    PriceEstimateHistoryResult,
    PriceEstimateHistorySummary,
)

_TOKEN_RE = re.compile(r"(sk-[a-zA-Z0-9]{8,}|bot\d{5,}:[A-Za-z0-9_-]{20,}|Bearer\s+\S{10,})", re.I)
_SECRET_RE = re.compile(r"(postgresql://\S+|redis://\S+|OPENAI_API_KEY\s*=\s*\S+)", re.I)

TAXMINIY_WARNING = "Taxminiy hisob — yakuniy narx o'lchovdan keyin aniqlanadi"

DESIGN_TITLES: dict[str, str] = {
    "adnatonniy": "Adnatonniy (oddiy)",
    "matt": "Adnatonniy (oddiy)",
    "gulli": "Gulli",
    "hi-tech": "Hi-tech",
    "mramor": "Mramor",
    "naqsh": "Naqsh",
    "kosmos": "Kosmos",
    "osmon": "Osmon",
    "qora uf": "Qora UF",
}


def _make_id(source: str, ts: str | None, index: int = 0) -> str:
    raw = f"price:{source}:{ts or ''}:{index}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def format_uzs(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")


def sanitize_preview(text: str | None, max_len: int = 200) -> str | None:
    if not text:
        return None
    cleaned = _TOKEN_RE.sub("[REDACTED]", text)
    cleaned = _SECRET_RE.sub("[REDACTED]", cleaned)
    cleaned = cleaned.replace("<", "&lt;").replace(">", "&gt;")
    return cleaned[:max_len]


def sanitize_metadata(metadata: dict | None) -> str | None:
    if not metadata:
        return None
    safe_keys = [
        "area_m2",
        "design_key",
        "design_type",
        "rate",
        "total",
        "discount_percent",
        "source",
        "is_estimate",
    ]
    parts = []
    for k in safe_keys:
        v = metadata.get(k)
        if v is not None:
            parts.append(f"{k}: {v}")
    return " | ".join(parts) if parts else None


def extract_from_ai_trace(
    trace: dict,
    contact_id: int = 0,
    index: int = 0,
) -> PriceEstimateHistoryItem | None:
    estimate = trace.get("last_price_estimate") or trace.get("price_estimate")
    if not estimate:
        return None
    area = trace.get("area_m2", 0.0)
    design = trace.get("design_type") or trace.get("design_key") or ""
    ts = str(trace.get("timestamp", ""))[:19] or None
    try:
        area_f = float(area) if area else 0.0
    except (ValueError, TypeError):
        area_f = 0.0
    try:
        total = int(estimate)
    except (ValueError, TypeError):
        total = 0
    rate = int(total / area_f) if area_f > 0 else 0
    title = DESIGN_TITLES.get(design, design.title() if design else "")
    return PriceEstimateHistoryItem(
        estimate_id=_make_id("ai_trace", ts, index),
        contact_id=contact_id,
        timestamp=ts,
        source="ai_trace",
        area_m2=area_f,
        design_key=design,
        design_title=title,
        rate_uzs_per_m2=rate,
        subtotal_uzs=total,
        total_uzs=total,
        is_estimate=True,
        warning=TAXMINIY_WARNING,
        metadata_summary=sanitize_metadata(trace),
    )


def extract_from_replay_event(
    event: dict,
    contact_id: int = 0,
    index: int = 0,
) -> PriceEstimateHistoryItem | None:
    if event.get("event_type") != "price_estimate":
        return None
    ts = event.get("timestamp")
    desc = event.get("description", "")
    meta = event.get("metadata_summary") or ""
    area = 0.0
    total = 0
    design = ""
    if "m²" in desc:
        parts = desc.split("(")
        if len(parts) > 1:
            area_str = parts[1].split("m²")[0].strip()
            try:
                area = float(area_str)
            except (ValueError, TypeError):
                pass
    for token in desc.replace(",", "").split():
        if token.isdigit() and int(token) > 1000:
            total = int(token)
            break
    if "area_m2:" in meta:
        for part in meta.split("|"):
            part = part.strip()
            if part.startswith("area_m2:"):
                try:
                    area = float(part.split(":")[1].strip())
                except (ValueError, TypeError):
                    pass
            elif part.startswith("design_type:"):
                design = part.split(":")[1].strip()
    rate = int(total / area) if area > 0 else 0
    title = DESIGN_TITLES.get(design, design.title() if design else "")
    return PriceEstimateHistoryItem(
        estimate_id=_make_id("replay", ts, index),
        contact_id=contact_id,
        timestamp=ts,
        source="replay",
        area_m2=area,
        design_key=design,
        design_title=title,
        rate_uzs_per_m2=rate,
        subtotal_uzs=total,
        total_uzs=total,
        is_estimate=True,
        warning=TAXMINIY_WARNING,
    )


def extract_from_memory_payload(
    payload: dict,
    contact_id: int = 0,
    ts: str | None = None,
    index: int = 0,
) -> PriceEstimateHistoryItem | None:
    total = payload.get("last_price_total")
    if not total:
        return None
    area = payload.get("last_price_area_m2", 0.0)
    design = payload.get("last_price_design", "")
    source = payload.get("last_price_source", "price_calculator")
    try:
        area_f = float(area) if area else 0.0
    except (ValueError, TypeError):
        area_f = 0.0
    try:
        total_i = int(total)
    except (ValueError, TypeError):
        total_i = 0
    rate = int(total_i / area_f) if area_f > 0 else 0
    title = DESIGN_TITLES.get(design, design.title() if design else "")
    return PriceEstimateHistoryItem(
        estimate_id=_make_id(source, ts, index),
        contact_id=contact_id,
        timestamp=ts,
        source=source,
        area_m2=area_f,
        design_key=design,
        design_title=title,
        rate_uzs_per_m2=rate,
        subtotal_uzs=total_i,
        total_uzs=total_i,
        is_estimate=payload.get("last_price_is_estimate", True),
        warning=TAXMINIY_WARNING,
        metadata_summary=sanitize_metadata(payload),
    )


def build_summary(
    items: list[PriceEstimateHistoryItem],
) -> PriceEstimateHistorySummary:
    if not items:
        return PriceEstimateHistorySummary()
    totals = [i.total_uzs for i in items if i.total_uzs > 0]
    timestamps = [i.timestamp for i in items if i.timestamp]
    designs = [i.design_key for i in items if i.design_key]
    design_counter = Counter(designs)
    most_design = design_counter.most_common(1)[0][0] if design_counter else ""
    areas = [i.area_m2 for i in items if i.area_m2 > 0]
    handoffs = sum(1 for i in items if i.handoff_after_estimate)
    latest_ts = max(timestamps) if timestamps else None
    latest_item = None
    if latest_ts:
        for i in items:
            if i.timestamp == latest_ts:
                latest_item = i
                break
    return PriceEstimateHistorySummary(
        total_estimates=len(items),
        latest_estimate_at=latest_ts,
        latest_total_uzs=latest_item.total_uzs if latest_item else 0,
        min_total_uzs=min(totals) if totals else 0,
        max_total_uzs=max(totals) if totals else 0,
        most_requested_design=most_design,
        total_area_m2=round(sum(areas), 1),
        handoff_after_estimate_count=handoffs,
        has_recent_estimate=bool(latest_ts),
    )


def build_history(
    contact: dict,
    messages: list[dict] | None = None,
    traces: list[dict] | None = None,
    replay_events: list[dict] | None = None,
) -> PriceEstimateHistoryResult:
    contact_id = contact.get("id", 0)
    items: list[PriceEstimateHistoryItem] = []
    seen_ids: set[str] = set()

    for i, trace in enumerate(traces or []):
        item = extract_from_ai_trace(trace, contact_id=contact_id, index=i)
        if item and item.estimate_id not in seen_ids:
            seen_ids.add(item.estimate_id)
            items.append(item)

    for i, event in enumerate(replay_events or []):
        item = extract_from_replay_event(event, contact_id=contact_id, index=i)
        if item and item.estimate_id not in seen_ids:
            seen_ids.add(item.estimate_id)
            items.append(item)

    md = contact.get("metadata") or contact.get("ai_trace_summary") or {}
    if md.get("last_price_estimate") or md.get("last_price_total"):
        mem_payload = {
            "last_price_total": md.get("last_price_total") or md.get("last_price_estimate"),
            "last_price_area_m2": md.get("area_m2") or md.get("last_price_area_m2"),
            "last_price_design": md.get("design_type") or md.get("last_price_design", ""),
            "last_price_source": md.get("last_price_source", "ai_trace"),
            "last_price_is_estimate": True,
        }
        item = extract_from_memory_payload(
            mem_payload,
            contact_id=contact_id,
            ts=str(md.get("timestamp", ""))[:19] or None,
        )
        if item and item.estimate_id not in seen_ids:
            seen_ids.add(item.estimate_id)
            items.append(item)

    has_handoff = False
    has_operator = False
    for msg in messages or []:
        text = (msg.get("text") or "").lower()
        if "operator" in text or "odam" in text:
            has_operator = True
        if msg.get("sender_type") == "operator":
            has_handoff = True

    if has_handoff or has_operator:
        for item in items:
            item.handoff_after_estimate = True
            item.operator_requested_after_estimate = has_operator

    items.sort(key=lambda x: x.timestamp or "")
    summary = build_summary(items)

    return PriceEstimateHistoryResult(
        contact_id=contact_id,
        items=items,
        summary=summary,
    )
