"""
apps.web.main
~~~~~~~~~~~~~
Minimal internal web dashboard for CeilingCRM.

Server-side rendered with Jinja2 — the API Bearer token never reaches the
browser.  All data is fetched from the existing REST API via httpx.

Run locally::

    API_BASE_URL=http://localhost:8000 \
    API_INTERNAL_TOKEN=your-token \
    WEB_DASHBOARD_USERNAME=admin \
    WEB_DASHBOARD_PASSWORD=secret \
    uvicorn apps.web.main:app --host 0.0.0.0 --port 8001 --reload
"""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from apps.web.api_client import api_get
from apps.web.auth import require_dashboard_auth

_TEMPLATES_DIR = Path(__file__).parent / "templates"

app = FastAPI(
    title="CeilingCRM Dashboard",
    docs_url=None,
    redoc_url=None,
    dependencies=[Depends(require_dashboard_auth)],
)

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

# ── Auth routes (no dashboard auth required) ───────────────────────────
from apps.web.admin_auth_routes import router as _auth_router  # noqa: E402

app.include_router(_auth_router)


# ── Helpers ─────────────────────────────────────────────────────────────


def _fmt_number(value: int | float | None) -> str:
    """Format a number with thousand separators (Jinja2 filter)."""
    if value is None:
        return "0"
    if isinstance(value, float):
        return f"{value:,.1f}"
    return f"{value:,}"


def _fmt_percent(value: float | None) -> str:
    """Format a float as a percentage string."""
    if value is None:
        return "0%"
    return f"{value * 100:.1f}%"


# Register template filters
templates.env.filters["fmt_number"] = _fmt_number
templates.env.filters["fmt_percent"] = _fmt_percent


# ── Routes ──────────────────────────────────────────────────────────────


@app.get("/", response_class=RedirectResponse)
async def root():
    """Redirect root to dashboard."""
    return RedirectResponse(url="/dashboard", status_code=302)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard home — summary cards from analytics API."""
    data = await api_get("/api/v1/analytics", params={"period": "month"})
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "data": data},
    )


@app.get("/leads", response_class=HTMLResponse)
async def leads(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Leads list — paginated table."""
    data = await api_get(
        "/api/v1/leads",
        params={"page": page, "page_size": page_size},
    )
    return templates.TemplateResponse(
        "leads.html",
        {"request": request, "data": data, "page": page, "page_size": page_size},
    )


@app.get("/pipeline", response_class=HTMLResponse)
async def pipeline(request: Request):
    """Pipeline kanban — 5-column board."""
    data = await api_get("/api/v1/pipeline/kanban", params={"limit_per_column": 50})
    return templates.TemplateResponse(
        "pipeline.html",
        {"request": request, "data": data},
    )


@app.get("/analytics", response_class=HTMLResponse)
async def analytics(
    request: Request,
    period: str = Query("week"),
):
    """Analytics summary — cards and tables."""
    data = await api_get("/api/v1/analytics", params={"period": period})
    return templates.TemplateResponse(
        "analytics.html",
        {"request": request, "data": data, "period": period},
    )


@app.get("/agent", response_class=HTMLResponse)
async def agent_dashboard(
    request: Request,
    hours: int = Query(24, ge=1, le=168),
):
    """Agent system dashboard — metrics, health, executions."""
    overview = await api_get(
        "/api/v1/admin/agent/metrics/overview",
        params={"hours": hours},
    )
    pending = await api_get(
        "/api/v1/admin/agent/executions/pending",
        params={"limit": 20},
    )
    control = await api_get("/api/v1/admin/agent/control/status")
    return templates.TemplateResponse(
        "agent.html",
        {
            "request": request,
            "overview": overview,
            "pending": pending,
            "control": control,
            "hours": hours,
        },
    )


@app.get("/crm", response_class=HTMLResponse)
async def crm_contacts(
    request: Request,
    q: str = Query(""),
    status: str = Query(""),
    temperature: str = Query(""),
):
    data = await api_get(
        "/api/v1/admin/crm/contacts",
        params={"q": q, "status": status, "temperature": temperature, "limit": 50},
    )
    return templates.TemplateResponse(
        "crm_contacts.html",
        {"request": request, "data": data, "q": q, "status": status},
    )


@app.get("/crm/{contact_id}", response_class=HTMLResponse)
async def crm_contact_detail(request: Request, contact_id: int):
    contact = await api_get(f"/api/v1/admin/crm/contacts/{contact_id}")
    messages = await api_get(
        f"/api/v1/admin/crm/contacts/{contact_id}/messages",
        params={"limit": 100},
    )
    return templates.TemplateResponse(
        "crm_contact_detail.html",
        {"request": request, "contact": contact, "messages": messages},
    )


@app.get("/admin/security", response_class=HTMLResponse)
async def admin_security(
    request: Request,
    hours: int = Query(24, ge=1, le=720),
):
    """Admin Security Audit Dashboard — read-only."""
    data = await api_get(
        "/api/v1/admin/security/dashboard",
        params={"hours": hours},
    )
    return templates.TemplateResponse(
        "security.html",
        {"request": request, "data": data, "hours": hours},
    )


@app.get("/crm/campaigns", response_class=HTMLResponse)
async def crm_campaigns(request: Request):
    """CRM Campaigns page — draft list and segment overview."""
    data = await api_get("/api/v1/admin/crm/campaigns/segments")
    drafts = await api_get("/api/v1/admin/crm/campaigns/drafts")
    return templates.TemplateResponse(
        "crm_campaigns.html",
        {"request": request, "segments": data, "drafts": drafts},
    )
