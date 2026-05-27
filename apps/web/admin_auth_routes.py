"""
apps.web.admin_auth_routes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Login/logout/session web routes for admin session auth.
Backward compatible — when session auth disabled, shows info notice.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from core.services.admin_auth_service import AdminAuthService

_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

router = APIRouter(tags=["admin-auth"])


def _get_session_auth_enabled() -> bool:
    try:
        from shared.config import get_settings

        return get_settings().business.admin_session_auth_enabled
    except Exception:
        return False


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    enabled = _get_session_auth_enabled()
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": error,
            "session_auth_enabled": enabled,
        },
    )


@router.post("/login")
async def login_submit(request: Request):
    enabled = _get_session_auth_enabled()
    if not enabled:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": "Session auth is not enabled. Use existing dashboard auth.",
                "session_auth_enabled": False,
            },
        )
    form = await request.form()
    admin_id = str(form.get("admin_id", "")).strip()
    secret = str(form.get("secret", "")).strip()
    if not admin_id or not secret:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": AdminAuthService.get_generic_login_error(),
                "session_auth_enabled": True,
            },
        )
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "error": AdminAuthService.get_generic_login_error(),
            "session_auth_enabled": True,
        },
    )


@router.post("/logout")
async def logout(request: Request, response: Response):
    enabled = _get_session_auth_enabled()
    if not enabled:
        return RedirectResponse(url="/login", status_code=302)
    try:
        from shared.config import get_settings

        settings = get_settings()
        cookie_name = settings.business.admin_session_cookie_name
    except Exception:
        cookie_name = "vp_admin_session"
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie(cookie_name, path="/")
    return resp


@router.get("/me/session")
async def get_session_info(request: Request):
    enabled = _get_session_auth_enabled()
    if not enabled:
        return {
            "authenticated": False,
            "source": "session_auth_disabled",
            "note": "Session auth is not enabled",
        }
    return {
        "authenticated": False,
        "source": "no_session_cookie",
        "note": "No valid session found",
    }
