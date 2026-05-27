"""
infrastructure.ai.openai_client
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Shared OpenAI client singleton and usage-recording helper.

These utilities are framework-independent and can be used from any layer:
``core/services/``, ``apps/bot/``, or future ``apps/api/``.

The client is created lazily on first call and reused as a module-level
singleton.  Usage metrics are recorded into Prometheus counters (the same
counters exposed at ``/metrics``).
"""

from __future__ import annotations

from typing import Any

import httpx
from openai import AsyncOpenAI

from infrastructure.monitoring.prometheus import (
    openai_request_duration,
    openai_requests_total,
    openai_tokens_completion_total,
    openai_tokens_prompt_total,
)
from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)

# ── OpenAI client (lazy singleton) ───────────────────────────────────────────

_openai_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    """Return the shared ``AsyncOpenAI`` client, creating it on first call."""
    global _openai_client
    if _openai_client is None:
        settings = get_settings()
        api_key = (
            settings.ai.api_key.get_secret_value()
            if settings.ai.api_key
            else settings.openai.api_key.get_secret_value()
        )
        _openai_client = AsyncOpenAI(
            api_key=api_key,
            timeout=httpx.Timeout(30.0, connect=10.0),
        )
    return _openai_client


# Public alias for external callers that prefer a non-underscore name.
get_openai_client = _get_client


# ── Usage recording ──────────────────────────────────────────────────────────


def _record_usage(resp: Any, model: str, duration: float) -> None:
    """Record OpenAI response usage in Prometheus counters. Never raises."""
    try:
        openai_requests_total.labels(model=model, status="ok").inc()
        openai_request_duration.labels(model=model).observe(duration)
        usage = getattr(resp, "usage", None)
        if usage:
            openai_tokens_prompt_total.labels(model=model).inc(
                usage.prompt_tokens or 0,
            )
            openai_tokens_completion_total.labels(model=model).inc(
                usage.completion_tokens or 0,
            )
    except Exception:
        log.warning("_record_usage_error", exc_info=True)


# Public alias.
record_openai_usage = _record_usage
