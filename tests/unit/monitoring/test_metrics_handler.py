"""Regression: the /metrics handler must not 500 on the Prometheus Content-Type.

prometheus_client's ``CONTENT_TYPE_LATEST`` includes a charset
("text/plain; version=...; charset=utf-8").  aiohttp rejects a charset inside
the ``content_type=`` constructor argument
(``ValueError: charset must not be in content_type argument``), so
``metrics_handler`` must set the full type via a raw header instead.

This was latent until the polling health server (#23) began serving /metrics in
polling mode, at which point /metrics returned HTTP 500.

Offline: calls the handler directly — no server bind, DB, Redis, or network.
"""

from __future__ import annotations

import pytest
from aiohttp import web
from prometheus_client import CONTENT_TYPE_LATEST

from infrastructure.monitoring.prometheus import metrics_handler


class TestMetricsHandler:
    async def test_handler_does_not_raise_and_returns_200(self):
        # The old `content_type=CONTENT_TYPE_LATEST` raised ValueError here.
        resp = await metrics_handler(None)  # handler does not use the request
        assert isinstance(resp, web.Response)
        assert resp.status == 200

    async def test_content_type_header_preserved_exactly(self):
        resp = await metrics_handler(None)
        assert resp.headers["Content-Type"] == CONTENT_TYPE_LATEST
        assert "charset=utf-8" in resp.headers["Content-Type"]

    async def test_body_is_prometheus_bytes(self):
        resp = await metrics_handler(None)
        assert isinstance(resp.body, bytes)
        assert len(resp.body) > 0

    def test_charset_in_content_type_arg_is_rejected_by_aiohttp(self):
        # Pins WHY the handler sets headers={} instead of content_type=:
        # aiohttp's constructor argument rejects a charset.
        with pytest.raises(ValueError):
            web.Response(body=b"x", content_type=CONTENT_TYPE_LATEST)
