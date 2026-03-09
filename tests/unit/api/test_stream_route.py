"""Unit tests for POST /api/chat/stream (SSE streaming endpoint)."""
from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_tenant_id
from apps.api.routes.stream import router
from infrastructure.database.session import get_db

_TENANT_ID = 1
_BASE_PAYLOAD = {"session_id": "sess-stream-123", "message": "Salom"}


def _build_app() -> FastAPI:
    """Minimal app with stream router; tenant resolved via override (no middleware)."""
    app = FastAPI()
    app.include_router(router, prefix="/api/chat")
    app.dependency_overrides[get_tenant_id] = lambda: _TENANT_ID
    app.dependency_overrides[get_db] = lambda: AsyncMock(spec=AsyncSession)
    return app


def _parse_sse(content: bytes) -> list[dict]:
    """Parse raw SSE body into list of event dicts."""
    events = []
    for line in content.decode("utf-8").splitlines():
        line = line.strip()
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


async def _fake_generate_stream(*args, **kwargs) -> AsyncGenerator[str, None]:
    """Fake async generator yielding two tokens."""
    yield "Salom"
    yield "!"


async def test_stream_blocked_prompt_returns_error_event():
    """Blocked prompt → SSE error event, no token events."""
    app = _build_app()
    mock_scan = MagicMock()
    mock_scan.blocked = True
    mock_scan.sanitized_text = "blocked"

    with patch("apps.api.routes.stream.scan_prompt", return_value=mock_scan):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/chat/stream", json=_BASE_PAYLOAD)

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse(resp.content)
    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert "mumkin emas" in events[0]["message"]


async def test_stream_rate_limited_user_returns_error_event():
    """Per-user rate limit exceeded → SSE error event with 'limit' message."""
    app = _build_app()
    mock_scan = MagicMock(blocked=False, sanitized_text="Salom")

    with patch("apps.api.routes.stream.scan_prompt", return_value=mock_scan):
        with patch(
            "apps.api.routes.stream.check_ai_rate_limit",
            new=AsyncMock(return_value=(False, "user")),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/chat/stream", json=_BASE_PAYLOAD)

    events = _parse_sse(resp.content)
    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert "limit" in events[0]["message"].lower()


async def test_stream_rate_limited_tenant_returns_error_event():
    """Per-tenant daily quota exceeded → SSE error event with 'kunlik' message."""
    app = _build_app()
    mock_scan = MagicMock(blocked=False, sanitized_text="Salom")

    with patch("apps.api.routes.stream.scan_prompt", return_value=mock_scan):
        with patch(
            "apps.api.routes.stream.check_ai_rate_limit",
            new=AsyncMock(return_value=(False, "tenant")),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post("/api/chat/stream", json=_BASE_PAYLOAD)

    events = _parse_sse(resp.content)
    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert "kunlik" in events[0]["message"].lower()


async def test_stream_yields_token_events_then_done():
    """Happy path: token events followed by a done event."""
    app = _build_app()
    mock_scan = MagicMock(blocked=False, sanitized_text="Salom")

    with patch("apps.api.routes.stream.scan_prompt", return_value=mock_scan):
        with patch(
            "apps.api.routes.stream.check_ai_rate_limit",
            new=AsyncMock(return_value=(True, None)),
        ):
            with patch(
                "apps.api.routes.stream._load_context",
                new=AsyncMock(return_value=({}, [], None)),
            ):
                with patch(
                    "apps.api.routes.stream.get_tenant_ai_config",
                    new=AsyncMock(return_value=(None, None)),
                ):
                    with patch(
                        "apps.api.routes.stream._build_context_block",
                        return_value=None,
                    ):
                        with patch(
                            "apps.api.routes.stream.generate_stream",
                            side_effect=_fake_generate_stream,
                        ):
                            with patch(
                                "apps.api.routes.stream._persist_exchange",
                                new=AsyncMock(),
                            ):
                                async with AsyncClient(
                                    transport=ASGITransport(app=app), base_url="http://test"
                                ) as client:
                                    resp = await client.post(
                                        "/api/chat/stream", json=_BASE_PAYLOAD
                                    )

    assert resp.status_code == 200
    events = _parse_sse(resp.content)

    token_events = [e for e in events if e["type"] == "token"]
    done_events = [e for e in events if e["type"] == "done"]

    assert len(token_events) == 2
    assert token_events[0]["data"] == "Salom"
    assert token_events[1]["data"] == "!"

    assert len(done_events) == 1
    done = done_events[0]
    assert done["session_id"] == "sess-stream-123"
    assert done["is_ai"] is True
    assert "intent" in done


async def test_stream_timeout_returns_error_event():
    """OpenAI call exceeds timeout → SSE error event."""
    import asyncio

    app = _build_app()
    mock_scan = MagicMock(blocked=False, sanitized_text="Salom")

    async def _slow_gen(*args, **kwargs) -> AsyncGenerator[str, None]:
        await asyncio.sleep(100)  # will be cancelled by timeout
        yield "never"

    with patch("apps.api.routes.stream.scan_prompt", return_value=mock_scan):
        with patch(
            "apps.api.routes.stream.check_ai_rate_limit",
            new=AsyncMock(return_value=(True, None)),
        ):
            with patch(
                "apps.api.routes.stream._load_context",
                new=AsyncMock(return_value=({}, [], None)),
            ):
                with patch(
                    "apps.api.routes.stream.get_tenant_ai_config",
                    new=AsyncMock(return_value=(None, None)),
                ):
                    with patch(
                        "apps.api.routes.stream._build_context_block",
                        return_value=None,
                    ):
                        with patch(
                            "apps.api.routes.stream.generate_stream",
                            side_effect=_slow_gen,
                        ):
                            with patch(
                                "apps.api.routes.stream.asyncio.timeout",
                                side_effect=TimeoutError,
                            ):
                                async with AsyncClient(
                                    transport=ASGITransport(app=app), base_url="http://test"
                                ) as client:
                                    resp = await client.post(
                                        "/api/chat/stream", json=_BASE_PAYLOAD
                                    )

    events = _parse_sse(resp.content)
    assert any(e["type"] == "error" for e in events)
    error_evt = next(e for e in events if e["type"] == "error")
    assert "vaqt" in error_evt["message"].lower()


async def test_stream_persists_exchange_after_done():
    """After streaming completes, _persist_exchange is called with correct args."""
    app = _build_app()
    mock_scan = MagicMock(blocked=False, sanitized_text="Salom")
    mock_persist = AsyncMock()

    with patch("apps.api.routes.stream.scan_prompt", return_value=mock_scan):
        with patch(
            "apps.api.routes.stream.check_ai_rate_limit",
            new=AsyncMock(return_value=(True, None)),
        ):
            with patch(
                "apps.api.routes.stream._load_context",
                new=AsyncMock(return_value=({}, [], None)),
            ):
                with patch(
                    "apps.api.routes.stream.get_tenant_ai_config",
                    new=AsyncMock(return_value=(None, None)),
                ):
                    with patch(
                        "apps.api.routes.stream._build_context_block",
                        return_value=None,
                    ):
                        with patch(
                            "apps.api.routes.stream.generate_stream",
                            side_effect=_fake_generate_stream,
                        ):
                            with patch(
                                "apps.api.routes.stream._persist_exchange",
                                mock_persist,
                            ):
                                async with AsyncClient(
                                    transport=ASGITransport(app=app), base_url="http://test"
                                ) as client:
                                    resp = await client.post(
                                        "/api/chat/stream", json=_BASE_PAYLOAD
                                    )

    assert resp.status_code == 200
    mock_persist.assert_called_once()
    call_kwargs = mock_persist.call_args.kwargs
    assert call_kwargs["tenant_id"] == _TENANT_ID
    assert call_kwargs["user_text"] == "Salom"
    assert call_kwargs["assistant_text"] == "Salom!"
    assert call_kwargs["extracted"] == {}
