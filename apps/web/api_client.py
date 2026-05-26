"""
apps.web.api_client
~~~~~~~~~~~~~~~~~~~
Async HTTP client for server-side calls to the CeilingCRM REST API.

All API calls go through this module so the Bearer token stays server-side.
The browser never sees the token — only rendered HTML is returned.
"""
from __future__ import annotations

from typing import Any

import httpx

from apps.web.config import get_api_base_url, get_api_token

# Reusable timeout (seconds)
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def _headers() -> dict[str, str]:
    """Build request headers with Bearer token if configured."""
    token = get_api_token()
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


async def api_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Make a GET request to the API and return parsed JSON.

    Raises ``httpx.HTTPStatusError`` on 4xx/5xx responses.
    Returns an error dict on connection failure (never crashes the web app).
    """
    url = f"{get_api_base_url()}{path}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, headers=_headers(), params=params)
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        return {"_error": "Cannot connect to API. Is the API server running?"}
    except httpx.HTTPStatusError as exc:
        return {
            "_error": f"API returned {exc.response.status_code}",
            "_detail": exc.response.text[:500],
        }
    except httpx.TimeoutException:
        return {"_error": "API request timed out."}
