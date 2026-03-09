"""Unit tests for POST /api/chat/message."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_tenant_id
from apps.api.routes.chat import router
from infrastructure.database.session import get_db

_TENANT_ID = 1
_BASE_PAYLOAD = {"session_id": "sess-abc123", "message": "Salom"}


def _build_app() -> FastAPI:
    """Minimal app with chat router; tenant resolved via override (no middleware)."""
    app = FastAPI()
    app.include_router(router, prefix="/api/chat")
    app.dependency_overrides[get_tenant_id] = lambda: _TENANT_ID
    app.dependency_overrides[get_db] = lambda: AsyncMock(spec=AsyncSession)
    return app


async def test_chat_blocked_prompt_returns_safe_reply():
    """Blocked prompt → 200 with intent='blocked', no AI call."""
    app = _build_app()
    mock_scan = MagicMock()
    mock_scan.blocked = True
    mock_scan.sanitized_text = "blocked-content"

    with patch("apps.api.routes.chat.scan_prompt", return_value=mock_scan):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/chat/message", json=_BASE_PAYLOAD)

    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "blocked"
    assert data["session_id"] == "sess-abc123"
    assert data["is_ai"] is True


async def test_chat_cache_hit_skips_ai_call():
    """Cache hit → _call_ai is NOT invoked."""
    app = _build_app()
    mock_scan = MagicMock(blocked=False, sanitized_text="Salom")
    cached_result = {"intent": "greeting", "reply": "Assalomu alaykum!"}
    mock_call_ai = AsyncMock()

    with patch("apps.api.routes.chat.scan_prompt", return_value=mock_scan):
        with patch("apps.api.routes.chat.check_ai_rate_limit", new=AsyncMock(return_value=(True, None))):
            with patch("apps.api.routes.chat._load_context", new=AsyncMock(return_value=({}, [], None))):
                with patch("apps.api.routes.chat.get_cached_response", new=AsyncMock(return_value=cached_result)):
                    with patch("apps.api.routes.chat._call_ai", mock_call_ai):
                        with patch("apps.api.routes.chat._persist_exchange", new=AsyncMock()):
                            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                                resp = await client.post("/api/chat/message", json=_BASE_PAYLOAD)

    assert resp.status_code == 200
    mock_call_ai.assert_not_called()
    assert resp.json()["reply"] == "Assalomu alaykum!"
    assert resp.json()["intent"] == "greeting"


async def test_chat_persists_exchange():
    """Successful AI exchange → _persist_exchange called with correct args."""
    app = _build_app()
    mock_scan = MagicMock(blocked=False, sanitized_text="Salom")
    ai_result = {"intent": "greeting", "reply": "Assalomu alaykum!"}
    mock_persist = AsyncMock()

    with patch("apps.api.routes.chat.scan_prompt", return_value=mock_scan):
        with patch("apps.api.routes.chat.check_ai_rate_limit", new=AsyncMock(return_value=(True, None))):
            with patch("apps.api.routes.chat._load_context", new=AsyncMock(return_value=({}, [], None))):
                with patch("apps.api.routes.chat.get_cached_response", new=AsyncMock(return_value=None)):
                    with patch("apps.api.routes.chat.get_tenant_ai_config", new=AsyncMock(return_value=(None, None))):
                        with patch("apps.api.routes.chat._build_context_block", return_value=None):
                            with patch("apps.api.routes.chat._call_ai", new=AsyncMock(return_value=ai_result)):
                                with patch("apps.api.routes.chat.store_response", new=AsyncMock()):
                                    with patch("apps.api.routes.chat._persist_exchange", mock_persist):
                                        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                                            resp = await client.post("/api/chat/message", json=_BASE_PAYLOAD)

    assert resp.status_code == 200
    mock_persist.assert_called_once()
    call_kwargs = mock_persist.call_args.kwargs
    assert call_kwargs["tenant_id"] == _TENANT_ID
    assert call_kwargs["user_text"] == "Salom"
    assert call_kwargs["intent"] == "greeting"


async def test_chat_rate_limited_returns_429():
    """Per-user rate limit exceeded → 429."""
    app = _build_app()
    mock_scan = MagicMock(blocked=False, sanitized_text="Salom")

    with patch("apps.api.routes.chat.scan_prompt", return_value=mock_scan):
        with patch("apps.api.routes.chat.check_ai_rate_limit", new=AsyncMock(return_value=(False, "user"))):
            with patch("apps.api.routes.chat._load_context", new=AsyncMock(return_value=({}, [], None))):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    resp = await client.post("/api/chat/message", json=_BASE_PAYLOAD)

    assert resp.status_code == 429
    assert "limit" in resp.json()["detail"].lower()
