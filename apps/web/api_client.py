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


# HTTP methods the browser → API proxy is allowed to forward.
PROXY_METHODS: tuple[str, ...] = ("GET", "POST", "PUT", "PATCH", "DELETE")


async def proxy_api_request(
    method: str,
    path: str,
    *,
    query_string: str = "",
    body: bytes | None = None,
    content_type: str | None = None,
) -> tuple[int, bytes, str]:
    """Forward a browser request to the REST API, server-side.

    The browser calls the web origin (same-origin, no token); this attaches
    the server-side Bearer token and forwards to ``API_BASE_URL``.  Returns
    ``(status_code, content, media_type)``.  Transport failures map to a
    502/504 JSON body so the browser sees a real error rather than a silent
    404 against the web origin.  Feature-flag enforcement stays on the API.
    """
    url = f"{get_api_base_url()}{path}"
    if query_string:
        url = f"{url}?{query_string}"
    headers = _headers()
    if content_type:
        headers["Content-Type"] = content_type
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.request(method, url, headers=headers, content=body)
        media_type = resp.headers.get("content-type", "application/json")
        return resp.status_code, resp.content, media_type
    except httpx.ConnectError:
        return 502, b'{"_error": "Cannot connect to API."}', "application/json"
    except httpx.TimeoutException:
        return 504, b'{"_error": "API request timed out."}', "application/json"
