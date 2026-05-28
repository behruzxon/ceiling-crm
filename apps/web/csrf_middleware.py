"""
apps.web.csrf_middleware
~~~~~~~~~~~~~~~~~~~~~~~~

CSRF middleware for the admin web app.

Gated on ``business.admin_csrf_enabled`` (env ``ADMIN_CSRF_ENABLED``).
Default OFF — when OFF, every request passes through unchanged and the
middleware is a no-op.

When ON:
* Safe methods (GET/HEAD/OPTIONS) pass through.
* Paths in ``CSRF_EXEMPT_PATHS`` pass through (login predates the session,
  so it cannot carry a session-bound CSRF token).
* Other methods (POST/PATCH/DELETE/PUT) require a valid token in the
  ``X-CSRF-Token`` request header.
* The token is validated against the session cookie (hashed) and the
  app secret using :class:`AdminCSRFService`.
* On failure: ``403`` JSON ``{"detail": "<sanitized>"}``.

The middleware never logs the raw token or the session hash.
"""

from __future__ import annotations

import hashlib

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from core.services.admin_csrf_service import AdminCSRFService

# Paths that bypass CSRF even when the flag is ON.
# /login is anonymous (no session yet → cannot carry a session-bound token).
CSRF_EXEMPT_PATHS: frozenset[str] = frozenset({"/login"})

CSRF_HEADER_NAME = "X-CSRF-Token"


def _hash_session_id(session_id: str) -> str:
    if not session_id:
        return ""
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def _read_session_cookie(request: Request) -> str:
    try:
        from shared.config import get_settings

        cookie_name = get_settings().business.admin_session_cookie_name
    except Exception:
        cookie_name = "vp_admin_session"
    return request.cookies.get(cookie_name, "") or ""


def _is_csrf_enabled() -> bool:
    try:
        from shared.config import get_settings

        return bool(get_settings().business.admin_csrf_enabled)
    except Exception:
        return False


def _get_secret_key() -> str:
    try:
        from shared.config import get_settings

        secret = get_settings().app_secret_key
        # SecretStr -> str
        if hasattr(secret, "get_secret_value"):
            return secret.get_secret_value()
        return str(secret)
    except Exception:
        return ""


class AdminCSRFMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that enforces CSRF on unsafe methods when enabled.

    Idempotent and side-effect free: short-circuits before consuming the
    request body so downstream handlers see the original stream.
    """

    def __init__(self, app: ASGIApp, *, exempt_paths: frozenset[str] | None = None) -> None:
        super().__init__(app)
        self._exempt_paths: frozenset[str] = exempt_paths or CSRF_EXEMPT_PATHS

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if not _is_csrf_enabled():
            return await call_next(request)

        method = request.method.upper()
        if method in AdminCSRFService.exempt_safe_methods():
            return await call_next(request)

        if request.url.path in self._exempt_paths:
            return await call_next(request)

        token = request.headers.get(CSRF_HEADER_NAME, "") or ""
        session_id = _read_session_cookie(request)
        session_id_hash = _hash_session_id(session_id)
        secret_key = _get_secret_key()

        result = AdminCSRFService.validate_csrf_token(
            token,
            session_id_hash,
            secret_key,
            enabled=True,
        )
        if not result.ok:
            return _csrf_forbidden(result.error)

        return await call_next(request)


def _csrf_forbidden(error: str) -> Response:
    safe = AdminCSRFService.sanitize_csrf_error(error or "csrf_validation_failed")
    return JSONResponse(status_code=403, content={"detail": safe})


__all__ = [
    "AdminCSRFMiddleware",
    "CSRF_EXEMPT_PATHS",
    "CSRF_HEADER_NAME",
]
