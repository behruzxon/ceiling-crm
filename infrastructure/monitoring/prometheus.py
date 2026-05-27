"""Prometheus metrics exporter."""
from __future__ import annotations

from aiohttp import web
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
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

# ── OpenAI usage metrics ─────────────────────────────────────────────────
openai_tokens_prompt_total = Counter(
    "openai_tokens_prompt_total",
    "Total OpenAI prompt tokens consumed",
    ["model"],
)
openai_tokens_completion_total = Counter(
    "openai_tokens_completion_total",
    "Total OpenAI completion tokens consumed",
    ["model"],
)
openai_requests_total = Counter(
    "openai_requests_total",
    "Total OpenAI API requests",
    ["model", "status"],
)
openai_request_duration = Histogram(
    "openai_request_duration_seconds",
    "OpenAI API call latency",
    ["model"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)


async def metrics_handler(request: web.Request) -> web.Response:
    """Expose Prometheus metrics at /metrics endpoint."""
    data = generate_latest()
    return web.Response(body=data, content_type=CONTENT_TYPE_LATEST)


async def health_handler(request: web.Request) -> web.Response:
    """Lightweight health check for uptime monitors and load balancers.

    Returns JSON: {"status": "ok", "db": "ok", "redis": "ok", "openai": "ok"}
    HTTP 200 when all services are reachable, 503 otherwise.
    """
    import json

    checks: dict[str, str] = {}

    # ── Database ─────────────────────────────────────────────────────
    try:
        import sqlalchemy as sa

        from infrastructure.database.session import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            await session.execute(sa.text("SELECT 1"))
        checks["db"] = "ok"
    except Exception:
        checks["db"] = "error"

    # ── Redis ────────────────────────────────────────────────────────
    try:
        from infrastructure.cache.client import get_redis

        ok = await get_redis().ping()
        checks["redis"] = "ok" if ok else "error"
    except Exception:
        checks["redis"] = "error"

    # ── OpenAI ───────────────────────────────────────────────────────
    try:
        import httpx

        from shared.config import get_settings

        settings = get_settings()
        api_key = (
            settings.ai.api_key.get_secret_value()
            if settings.ai.api_key
            else settings.openai.api_key.get_secret_value()
        )
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            checks["openai"] = "ok" if resp.status_code == 200 else "error"
    except Exception:
        checks["openai"] = "error"

    all_ok = all(v == "ok" for v in checks.values())
    body = json.dumps({"status": "ok" if all_ok else "degraded", **checks})
    return web.Response(
        body=body,
        content_type="application/json",
        status=200 if all_ok else 503,
    )


def setup_prometheus(app: web.Application) -> None:
    """Register /metrics and /health routes on the aiohttp app."""
    from shared.config import get_settings
    if get_settings().prometheus_enabled:
        app.router.add_get("/metrics", metrics_handler)
    # Health endpoint is always available
    app.router.add_get("/health", health_handler)
