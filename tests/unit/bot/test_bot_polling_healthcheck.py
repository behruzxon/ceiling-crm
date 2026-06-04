"""Tests for the polling-mode health/metrics server wiring.

These cover the fix that makes the bot expose ``/health`` (and ``/metrics``)
while running in long-polling mode, so Docker healthchecks and Prometheus
scrapes have an endpoint to hit.

No real Telegram/OpenAI/DB/Redis calls are made and no port is bound — the
aiohttp ``web.Application`` is inspected at the route level only.
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

# Import at module load (before any monkeypatch) so the heavy import chain
# under apps.bot.main resolves with the real settings.  Tests then patch only
# the get_settings() lookup inside setup_prometheus at call time.
import apps.bot.main as m


def _route_paths(app) -> set[str]:
    """Return the set of canonical route paths registered on an aiohttp app."""
    return {route.resource.canonical for route in app.router.routes()}


class TestBuildHealthApp:
    def test_health_route_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # /health must always be available regardless of the metrics flag.
        monkeypatch.setattr(
            "shared.config.get_settings",
            lambda: SimpleNamespace(prometheus_enabled=True),
        )
        app = m.build_health_app()
        assert "/health" in _route_paths(app)

    def test_metrics_route_present_when_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "shared.config.get_settings",
            lambda: SimpleNamespace(prometheus_enabled=True),
        )
        paths = _route_paths(m.build_health_app())
        assert "/metrics" in paths
        assert "/health" in paths

    def test_metrics_route_absent_when_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "shared.config.get_settings",
            lambda: SimpleNamespace(prometheus_enabled=False),
        )
        paths = _route_paths(m.build_health_app())
        # Metrics endpoint gated by the flag; health endpoint stays available.
        assert "/metrics" not in paths
        assert "/health" in paths


class TestRunPollingWiring:
    def test_health_server_helpers_exist(self) -> None:
        import apps.bot.main as m

        assert inspect.iscoroutinefunction(m._start_health_server)
        assert inspect.iscoroutinefunction(m._stop_health_server)

    def test_run_polling_starts_and_stops_health_server(self) -> None:
        # Wiring check: run_polling must bring the health server up and tear it
        # down cleanly in a finally block, without us starting an event loop or
        # hitting Telegram.
        import apps.bot.main as m

        src = inspect.getsource(m.run_polling)
        assert "_start_health_server" in src
        assert "_stop_health_server" in src
        assert "finally" in src

    def test_stop_health_server_handles_none(self) -> None:
        # Shutdown helper must be a no-op when the server never started.
        import asyncio

        from apps.bot.main import _stop_health_server

        # Should not raise.
        asyncio.run(_stop_health_server(None))
