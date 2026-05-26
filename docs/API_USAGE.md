# CeilingCRM REST API Usage

Read-only REST API for the CeilingCRM web dashboard.
Runs alongside the Telegram bot as a separate process.

---

## Running Locally

```bash
# 1. Ensure infrastructure is up
docker compose up -d postgres redis

# 2. Set environment (required — production settings block missing token)
export APP_ENV=development

# 3. Start the API server
uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Swagger UI is available at `http://localhost:8000/docs` in development mode only.

---

## Required Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `APP_ENV` | Yes | `development` / `staging` / `production` |
| `POSTGRES_HOST` | Yes | PostgreSQL host |
| `POSTGRES_PORT` | Yes | PostgreSQL port (default `5432`) |
| `POSTGRES_USER` | Yes | Database user |
| `POSTGRES_PASSWORD` | Yes | Database password |
| `POSTGRES_DB` | Yes | Database name |
| `REDIS_HOST` | Yes | Redis host |
| `REDIS_PORT` | Yes | Redis port (default `6379`) |
| `API_INTERNAL_TOKEN` | Prod: Yes | Bearer token for `/api/v1/*` endpoints |

In **development** mode with `API_INTERNAL_TOKEN` unset, all endpoints are
accessible without authentication (a warning is logged once at startup).

In **production/staging**, `API_INTERNAL_TOKEN` **must** be set or all
`/api/v1/*` requests will be rejected with 401.

---

## Endpoints

### Public

#### `GET /health` — Liveness Probe

No authentication required. Returns immediately with no external calls.

```bash
curl http://localhost:8000/health
```

```json
{"status": "ok", "service": "ceilingcrm-api"}
```

---

### Protected (require `Authorization: Bearer <token>`)

All `/api/v1/*` endpoints require a valid Bearer token (unless running in
development mode without a token configured).

#### `GET /api/v1/health` — Readiness Probe

Checks PostgreSQL and Redis connectivity.

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/v1/health
```

```json
{
  "status": "ok",
  "service": "ceilingcrm-api",
  "environment": "development",
  "checks": {
    "database": {"status": "ok"},
    "redis": {"status": "ok"}
  }
}
```

---

#### `GET /api/v1/leads` — Paginated Lead List

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | int | `1` | Page number (1-based) |
| `page_size` | int | `20` | Items per page (1-100) |
| `stage` | string | `null` | Filter by pipeline stage (e.g. `new`, `contacted`, `measurement`) |

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     "http://localhost:8000/api/v1/leads?page=1&page_size=10"
```

```json
{
  "items": [
    {
      "id": 42,
      "user_id": 123456789,
      "category": "matte",
      "source": "group",
      "name": "Ali",
      "phone": "+998901234567",
      "district": "Chilonzor",
      "room_area": "25.5",
      "current_stage": "new",
      "score": 45,
      "lead_status": null,
      "lead_temperature": "warm",
      "closing_confidence": 0.55,
      "next_follow_up_at": "2026-05-01T14:30:00",
      "follow_up_count": 1,
      "created_at": "2026-04-28T10:15:00",
      "updated_at": "2026-04-30T08:22:00"
    }
  ],
  "page": 1,
  "page_size": 10,
  "total": 128,
  "total_pages": 13,
  "has_next": true,
  "has_prev": false
}
```

---

#### `GET /api/v1/pipeline/kanban` — Kanban Board

Returns 5 kanban columns (new, hot, measurement, won, lost) with lead counts
and top leads per column.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit_per_column` | int | `20` | Max leads per column (1-100) |

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     "http://localhost:8000/api/v1/pipeline/kanban?limit_per_column=5"
```

```json
{
  "columns": [
    {
      "key": "new",
      "title": "Yangi",
      "count": 12,
      "items": [
        {
          "id": 42,
          "name": "Ali",
          "phone": "+998901234567",
          "district": "Chilonzor",
          "current_stage": "new",
          "score": 45,
          "lead_status": null,
          "room_area": "25.5",
          "next_follow_up_at": null,
          "created_at": "2026-04-28T10:15:00",
          "updated_at": "2026-04-30T08:22:00"
        }
      ]
    },
    {
      "key": "hot",
      "title": "Issiq",
      "count": 5,
      "items": []
    }
  ]
}
```

Kanban column mapping:
- **new** — pipeline stages: `new`, `package_selected`
- **hot** — pipeline stages: `contacted`
- **measurement** — pipeline stages: `measurement`, `quote_sent`
- **won** — pipeline stages: `deal_closed`, `installation`, `completed`
- **lost** — pipeline stages: `lost`

---

#### `GET /api/v1/analytics` — Sales Analytics Report

Returns a full analytics report for a given time period.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `period` | string | `week` | One of: `today`, `week`, `month`, `all` |

Period-to-days mapping: `today`=1, `week`=7, `month`=30, `all`=365.

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     "http://localhost:8000/api/v1/analytics?period=month"
```

```json
{
  "period": "month",
  "days": 30,
  "total_leads": 87,
  "won_leads": 12,
  "lost_leads": 8,
  "active_leads": 67,
  "conversion_rate": 0.138,
  "top_sources": [
    {"source": "group", "leads": 45, "won": 7, "lost": 3, "rate": 0.156}
  ],
  "buyer_type_stats": [],
  "best_buyer_type": null,
  "top_objections": [],
  "objection_severity_stats": {},
  "objection_lost_correlation": [],
  "tactic_stats": [],
  "best_tactic": null,
  "stage_counts": [
    {"stage": "new", "count": 30},
    {"stage": "contacted", "count": 15}
  ],
  "largest_dropoff_stage": "contacted",
  "followup_stats": {
    "avg_followups_won": 2.1,
    "avg_followups_lost": 0.5,
    "avg_followups_all": 1.2,
    "with_followup_pct": 0.45
  },
  "best_followup_type": null,
  "followup_type_stats": [],
  "score_distribution": {"hot": 10, "warm": 25, "cold": 52},
  "avg_score": 28.5,
  "total_estimated_revenue": 0,
  "avg_revenue_per_lead": 0,
  "avg_health_score": 0.0,
  "health_distribution": {"healthy": 0, "at_risk": 0, "critical": 0},
  "top_signals": [],
  "cooling_count": 0,
  "autopilot_action_distribution": [],
  "opportunity_count": 0,
  "at_risk_count": 0,
  "closing_ready_count": 0,
  "closing_readiness_distribution": {"NOT_READY": 0, "NEAR_CLOSE": 0, "READY_TO_CLOSE": 0},
  "close_opportunity_count": 0,
  "close_loss_risk_count": 0,
  "closing_tactic_distribution": [],
  "auto_reply_count": 0,
  "auto_escalation_count": 0,
  "auto_reply_confidence_avg": 0.0,
  "recommendations": [
    "Lead conversion is below 20% -- review follow-up strategy"
  ]
}
```

> **Note:** Fields like `buyer_type_stats`, `top_objections`, `tactic_stats`,
> conversation health, autopilot, and auto-seller metrics will be empty/zero.
> These require Redis AI memory enrichment which is only available in the
> Telegram bot context, not the REST API.

---

## Authentication Errors

All protected endpoints return 401 with a JSON body on auth failure:

```json
{"detail": "Missing Authorization header. Use: Authorization: Bearer <token>"}
```

```json
{"detail": "Invalid API token."}
```

```json
{"detail": "API authentication is not configured. Set API_INTERNAL_TOKEN to enable the API."}
```

---

## Security

- **Never commit** `API_INTERNAL_TOKEN` to version control.
- Use a strong, random token (64+ characters recommended).
- In production, always set `API_INTERNAL_TOKEN` in your environment or secrets manager.
- The API is **read-only** — no write/delete operations are exposed.
- Swagger UI (`/docs`) and ReDoc (`/redoc`) are disabled in production.
- Token comparison uses `secrets.compare_digest` (constant-time) to prevent timing attacks.

---

## Web Dashboard

The web dashboard is a separate server-side-rendered app that consumes the REST
API above. It runs on a different port and makes all API calls server-side, so
the `API_INTERNAL_TOKEN` is **never exposed to the browser**.

### Running the Web Dashboard

```bash
# 1. Start the API server first (port 8000)
APP_ENV=development uvicorn apps.api.main:app --port 8000

# 2. Start the web dashboard (port 8001)
APP_ENV=development \
API_BASE_URL=http://localhost:8000 \
API_INTERNAL_TOKEN=your-token \
WEB_DASHBOARD_USERNAME=admin \
WEB_DASHBOARD_PASSWORD=change-me \
uvicorn apps.web.main:app --host 0.0.0.0 --port 8001 --reload
```

Then open `http://localhost:8001/dashboard` in a browser.
The browser will show a native login dialog — enter the username and password
from the env vars above.

### Web Dashboard Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_ENV` | No | `development` | Controls auth behavior (see below) |
| `API_BASE_URL` | No | `http://localhost:8000` | URL of the CeilingCRM REST API |
| `API_INTERNAL_TOKEN` | Depends | — | Same token used by the API. Required if the API has auth enabled. |
| `WEB_DASHBOARD_USERNAME` | Prod: Yes | — | HTTP Basic Auth username for dashboard access |
| `WEB_DASHBOARD_PASSWORD` | Prod: Yes | — | HTTP Basic Auth password for dashboard access |

### Web Dashboard Authentication

The dashboard is protected with HTTP Basic Auth. The browser's native login
dialog is triggered automatically.

**Development mode** (`APP_ENV=development`): If `WEB_DASHBOARD_USERNAME` or
`WEB_DASHBOARD_PASSWORD` is unset, the dashboard is accessible without
credentials (a warning is logged once at startup).

**Production/staging mode**: If credentials are not configured, all dashboard
requests are rejected with 401 (fail-closed).

Credentials are compared using `secrets.compare_digest` (constant-time) for
both username and password.

```bash
# Test with curl — no credentials (expect 401 when auth is configured)
curl -v http://localhost:8001/dashboard
# Response: 401 with WWW-Authenticate: Basic header

# Test with curl — valid credentials
curl -u admin:change-me http://localhost:8001/dashboard
# Response: 200 with dashboard HTML
```

### Pages

| Route | Description |
|-------|-------------|
| `/` | Redirects to `/dashboard` |
| `/dashboard` | Summary cards: total leads, conversion rate, won/lost/active, score distribution, recommendations |
| `/leads` | Paginated table of all leads with stage, score, status, area, date |
| `/pipeline` | 5-column kanban board (New, Hot, Measurement, Won, Lost) with lead cards |
| `/analytics` | Full analytics with period selector (today/week/month/all), source performance, funnel, scores, revenue |

### Architecture

```
Browser  ──HTTP──>  apps/web (port 8001)  ──httpx──>  apps/api (port 8000)  ──>  PostgreSQL
                    Jinja2 SSR                        FastAPI + Bearer auth
                    (token server-side)               (reads DB)
```

The web dashboard:
- Uses **Jinja2** for server-side HTML rendering (no SPA, no build step)
- Uses **httpx** for async HTTP calls to the API
- Uses **Tailwind CSS** via CDN for styling
- Stores `API_INTERNAL_TOKEN` in server environment only
- Never sends the token to the browser
- Is **read-only** — no forms, no write actions
- Is protected by HTTP Basic Auth (browser native login dialog)
- Credentials stay in server env — never sent in page HTML
