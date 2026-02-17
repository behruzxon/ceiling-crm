"""Prometheus metrics exporter."""
from __future__ import annotations
from aiohttp import web
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Histogram,
    Gauge,
    generate_latest,
)

# ── Metric definitions ────────────────────────────────────────────────────
bot_updates_total = Counter(
    "bot_updates_total",
    "Total Telegram updates processed",
    ["update_type", "status"],
)
bot_handler_duration = Histogram(
    "bot_handler_duration_seconds",
    "Handler execution duration",
    ["handler_name"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0],
)
leads_created_total = Counter(
    "leads_created_total",
    "Total leads created",
    ["category", "source"],
)
pipeline_transitions_total = Counter(
    "pipeline_transitions_total",
    "CRM stage transitions",
    ["from_stage", "to_stage"],
)
broadcast_sent_total = Counter(
    "broadcast_sent_total",
    "Broadcast messages sent",
    ["broadcast_id", "status"],
)
active_users_gauge = Gauge(
    "active_users_total",
    "Total registered non-blocked users",
)


async def metrics_handler(request: web.Request) -> web.Response:
    """Expose Prometheus metrics at /metrics endpoint."""
    data = generate_latest()
    return web.Response(body=data, content_type=CONTENT_TYPE_LATEST)


def setup_prometheus(app: web.Application) -> None:
    """Register /metrics route on the aiohttp app."""
    from shared.config import get_settings
    if get_settings().prometheus_enabled:
        app.router.add_get("/metrics", metrics_handler)
