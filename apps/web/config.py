"""
apps.web.config
~~~~~~~~~~~~~~~
Web dashboard configuration — reads from environment variables.

Keeps API_INTERNAL_TOKEN on the server side only (never sent to browser).
"""

from __future__ import annotations

import os


def get_api_base_url() -> str:
    """Return the base URL for the CeilingCRM REST API."""
    return os.environ.get("API_BASE_URL", "http://localhost:8000")


def get_api_token() -> str | None:
    """Return the internal API token (server-side only, never exposed to client)."""
    return os.environ.get("API_INTERNAL_TOKEN")


def get_web_username() -> str | None:
    """Return the dashboard Basic Auth username (server-side only)."""
    return os.environ.get("WEB_DASHBOARD_USERNAME")


def get_web_password() -> str | None:
    """Return the dashboard Basic Auth password (server-side only)."""
    return os.environ.get("WEB_DASHBOARD_PASSWORD")


def is_development() -> bool:
    """Return True when APP_ENV is 'development' (or unset, defaults to dev)."""
    return os.environ.get("APP_ENV", "development") == "development"
