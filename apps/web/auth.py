"""
apps.web.auth
~~~~~~~~~~~~~
HTTP Basic Auth guard for the internal web dashboard.

Protects all dashboard routes with a username/password from environment
variables.  The browser's native login dialog is triggered via the
``WWW-Authenticate: Basic`` header on 401 responses.

Behavior:
- Reads ``WEB_DASHBOARD_USERNAME`` and ``WEB_DASHBOARD_PASSWORD`` from env.
- **Development** with credentials missing: allows access, logs a warning
  once per startup.
- **Production/staging** with credentials missing: denies access (fail-closed).
- Uses ``secrets.compare_digest`` for constant-time comparison of both
  username and password.
"""

from __future__ import annotations

import logging
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from apps.web.config import get_web_password, get_web_username, is_development

log = logging.getLogger(__name__)

_basic_scheme = HTTPBasic(auto_error=False)

# Track whether the dev-mode warning has been emitted.
_dev_open_warned: bool = False


async def require_dashboard_auth(
    credentials: HTTPBasicCredentials | None = Depends(_basic_scheme),
) -> None:
    """Validate dashboard Basic Auth credentials.

    Raises ``HTTPException(401)`` with ``WWW-Authenticate: Basic`` on
    invalid or missing credentials, which triggers the browser's native
    login dialog.
    """
    global _dev_open_warned  # noqa: PLW0603

    expected_user = get_web_username()
    expected_pass = get_web_password()

    # ── No credentials configured ────────────────────────────────────
    if not expected_user or not expected_pass:
        if is_development():
            if not _dev_open_warned:
                log.warning(
                    "web_dashboard_auth_not_configured -- Dashboard is open in "
                    "development mode. Set WEB_DASHBOARD_USERNAME and "
                    "WEB_DASHBOARD_PASSWORD in .env to enable auth."
                )
                _dev_open_warned = True
            return  # allow through
        # Production / staging: fail closed
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Dashboard authentication is not configured. "
            "Set WEB_DASHBOARD_USERNAME and WEB_DASHBOARD_PASSWORD.",
            headers={"WWW-Authenticate": 'Basic realm="CeilingCRM Dashboard"'},
        )

    # ── Credentials configured but request has none ──────────────────
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": 'Basic realm="CeilingCRM Dashboard"'},
        )

    # ── Constant-time comparison for both username and password ──────
    username_ok = secrets.compare_digest(
        credentials.username.encode("utf-8"),
        expected_user.encode("utf-8"),
    )
    password_ok = secrets.compare_digest(
        credentials.password.encode("utf-8"),
        expected_pass.encode("utf-8"),
    )

    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
            headers={"WWW-Authenticate": 'Basic realm="CeilingCRM Dashboard"'},
        )
