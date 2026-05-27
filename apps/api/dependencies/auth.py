"""
apps.api.dependencies.auth
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Internal Bearer token guard for all /api/v1/* endpoints.

Usage — apply to a router::

    from apps.api.dependencies.auth import require_api_token

    router = APIRouter(dependencies=[Depends(require_api_token)])

Or to an individual endpoint::

    @router.get("/endpoint", dependencies=[Depends(require_api_token)])

Behavior:
- Reads ``API_INTERNAL_TOKEN`` from settings.
- **Development** with no token configured: allows access, logs a warning
  once per startup.
- **Production** with no token configured: rejects all requests (fail-closed).
- Valid ``Authorization: Bearer <token>`` header required when token is set.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from shared.config import get_settings
from shared.logging import get_logger

log = get_logger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)

# Track whether the dev-mode warning has been emitted.
_dev_open_warned: bool = False


async def require_api_token(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ] = None,
) -> None:
    """Validate the internal API Bearer token.

    Raises ``HTTPException(401)`` on invalid or missing credentials.
    """
    global _dev_open_warned  # noqa: PLW0603

    settings = get_settings()
    expected_token = settings.api.internal_token

    # ── No token configured ────────────────────────────────────────
    if expected_token is None:
        if settings.is_development:
            if not _dev_open_warned:
                log.warning(
                    "api_token_not_configured — API is open in development mode. "
                    "Set API_INTERNAL_TOKEN in .env to enable auth."
                )
                _dev_open_warned = True
            return  # allow through
        # Production / staging: fail closed
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API authentication is not configured. "
            "Set API_INTERNAL_TOKEN to enable the API.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Token configured but request has no credentials ────────────
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Use: Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Constant-time comparison ───────────────────────────────────
    if not secrets.compare_digest(
        credentials.credentials,
        expected_token.get_secret_value(),
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
