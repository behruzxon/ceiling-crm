# Web Integration Plan

This document outlines the phased approach to adding a REST API and web dashboard to CeilingCRM, eventually reaching multi-tenant SaaS capability.

---

## Why API Must Be Added Before Web Dashboard

1. **The service layer already exists.** 35+ services with clean constructor injection can serve both Telegram and HTTP channels.
2. **The repository pattern is already abstract.** 14 ABCs in `core/repositories/` with concrete PostgreSQL implementations — API routes just need to call the same factories.
3. **The session management already supports FastAPI.** `get_db()` in `session.py` is a ready-to-use FastAPI dependency (currently unused).
4. **Adding the API is additive.** No existing bot code needs to change. The API lives in a new `apps/api/` directory.
5. **The web dashboard is a separate frontend project.** It will consume the API. Building the API first means the frontend can be developed independently.
6. **Multi-tenancy is a data layer concern.** It should be added after the API is stable, not before.

---

## Phase 1: Foundation Cleanup

**Goal:** Remove architectural violations that would complicate API extraction. Zero functional changes.

### Tasks

1. **Create `shared/constants/pricing.py`**
   - Move `DEFAULT_BASE_PRICES` (Decimal, 100k-300k range, for quotes) from `pricing_service.py`
   - Move `ADDON_PRICES` (Decimal) from `pricing_service.py` — eliminates duplicate copy in `revenue_predictor_service.py`
   - Move `_DESIGN_PRICES` (int, 80k-140k range, for AI/customer display) from `deal_probability.py`
   - Move `_DEFAULT_PRICE_PER_M2` from `deal_probability.py`
   - Keep the two price sets as separate named constants — they are intentionally different tiers
   - All three consumer files import from the new single source
   - Verify: `pytest tests/unit/` passes

2. **Create `shared/utils/sanitize.py`**
   - Move `sanitize_user_text_for_prompt()`, `sanitize_ai_reply()`, `detect_prompt_injection()` from `apps/bot/ai/system_prompt.py`
   - Update imports in `apps/bot/ai/system_prompt.py` (re-export for backward compat)
   - Update imports in `core/services/ai_sales_advice.py` and `core/services/deal_closer_service.py`
   - Verify: dependency direction is now `core -> shared` (no `core -> apps`)

3. **Move OpenAI client helpers to infrastructure**
   - Move `_get_client()`, `_record_usage()` from `apps/bot/handlers/private/ai_openai.py` to `infrastructure/ai/openai_client.py`
   - Update imports in `core/services/ai_sales_advice.py`
   - The handler file re-exports for backward compat
   - Verify: `core/` no longer imports from `apps/`

4. **Verify all tests pass**
   - `pytest tests/unit/ -q`
   - `ruff check .`
   - `mypy .` (if configured)

### Files Created
- `shared/constants/pricing.py` (new)
- `shared/utils/sanitize.py` (new)
- `infrastructure/ai/__init__.py` (new)
- `infrastructure/ai/openai_client.py` (new)

### Files Modified (import paths only)
- `core/services/pricing_service.py`
- `shared/utils/deal_probability.py`
- `core/services/revenue_predictor_service.py`
- `apps/bot/ai/system_prompt.py`
- `core/services/ai_sales_advice.py`
- `core/services/deal_closer_service.py`
- `apps/bot/handlers/private/ai_openai.py`

---

## Phase 2: Read-Only FastAPI API

**Goal:** Add a minimal REST API that exposes CRM data for read-only consumption. The Telegram bot continues to be the primary write interface.

### Tasks

1. **Create FastAPI app skeleton**
   - `apps/api/__init__.py`
   - `apps/api/main.py` — FastAPI app with CORS, `/health` endpoint
   - `apps/api/deps.py` — `get_db` dependency (wraps `session.get_db()`)
   - `apps/api/config.py` — API-specific settings (JWT secret, CORS origins)

2. **Add JWT authentication**
   - `core/auth/__init__.py`
   - `core/auth/jwt.py` — `create_token()`, `verify_token()`, `get_current_user()` dependency
   - `core/auth/models.py` — `TokenPayload`, `TokenResponse` Pydantic models
   - `apps/api/routes/auth.py` — `POST /api/v1/auth/login` (Telegram user_id + admin secret for now)

3. **Create API response schemas**
   - `apps/api/schemas/lead.py` — `LeadOut`, `LeadListOut`, `LeadDetail`
   - `apps/api/schemas/pipeline.py` — `KanbanOut`, `StageCountOut`
   - `apps/api/schemas/analytics.py` — `AnalyticsOut`
   - `apps/api/schemas/common.py` — `Page[T]` pagination wrapper

4. **Add read-only endpoints**
   - `apps/api/routes/leads.py` — `GET /api/v1/leads`, `GET /api/v1/leads/{id}`
   - `apps/api/routes/pipeline.py` — `GET /api/v1/pipeline/kanban`, `GET /api/v1/pipeline/stages/{lead_id}`
   - `apps/api/routes/analytics.py` — `GET /api/v1/analytics?days=30`
   - `apps/api/routes/users.py` — `GET /api/v1/users/me`

5. **Wire into Docker Compose**
   - Add `api` service in `docker-compose.yml`
   - Command: `uvicorn apps.api.main:app --host 0.0.0.0 --port 8000`
   - Port: 8000
   - Depends on: postgres, redis

6. **Add tests**
   - `tests/unit/api/test_leads.py`
   - `tests/unit/api/test_auth.py`

### Files Created
- `apps/api/` directory (new, ~10 files)
- `core/auth/` directory (new, ~3 files)
- `tests/unit/api/` directory (new)

### Files Modified
- `docker-compose.yml` (add api service)
- `docker-compose.prod.yml` (add api service)

---

## Phase 3: Full CRUD API

**Goal:** Enable write operations through the API. Admin dashboard can now manage leads, pipeline, broadcasts, payments.

### Tasks

1. **Write endpoints for leads**
   - `POST /api/v1/leads` — create lead
   - `PATCH /api/v1/leads/{id}` — update lead fields
   - `POST /api/v1/leads/{id}/assign` — assign manager
   - `POST /api/v1/leads/{id}/move-stage` — pipeline transition

2. **Write endpoints for pipeline**
   - `POST /api/v1/pipeline/move` — advance/regress stage
   - `POST /api/v1/pipeline/{lead_id}/lost` — mark lost with reason

3. **Appointment endpoints**
   - Full CRUD for appointments
   - Calendar view endpoint: `GET /api/v1/appointments?from=&to=`

4. **Payment endpoints**
   - `POST /api/v1/payments` — create payment record
   - `PATCH /api/v1/payments/{id}/status` — update status
   - `GET /api/v1/payments?lead_id=`

5. **Broadcast endpoints**
   - `POST /api/v1/broadcasts` — create broadcast
   - `POST /api/v1/broadcasts/{id}/send` — trigger send
   - `GET /api/v1/broadcasts` — list with status

6. **User management**
   - `GET /api/v1/users` — list users with filters
   - `PATCH /api/v1/users/{id}/role` — change role (RBAC enforced)

7. **File upload**
   - `POST /api/v1/files/upload` — upload media
   - `GET /api/v1/files/{id}` — download/serve file

8. **API role-based access control**
   - Implement permission decorator checking `user.role` against required roles
   - Mirror the 5-role hierarchy from the bot

---

## Phase 4: Web Dashboard

**Goal:** Build a web frontend that consumes the API. This is a separate project/repo.

### Components (out of scope for this repo, listed for planning)

- Login page (JWT auth)
- Dashboard (stats overview)
- Lead list (table with filters, sorting, pagination)
- Kanban board (drag-and-drop pipeline)
- Lead detail (timeline, actions, AI intelligence card)
- Calendar (appointments)
- Broadcast composer
- Analytics charts
- User management
- Settings

### API Requirements from Dashboard

The Phase 3 API must support:
- Pagination: `?page=1&per_page=20`
- Filtering: `?status=hot&source=group&created_after=2026-01-01`
- Sorting: `?sort=-created_at`
- Search: `?q=phone_number_or_name`
- Bulk operations: `POST /api/v1/leads/bulk-assign`

---

## Phase 5: Multi-Tenancy / SaaS

**Goal:** Support multiple businesses on the same infrastructure.

### Data Layer Changes

1. **Add `Organization` model**
   ```
   id, name, slug, plan (free/pro/enterprise)
   bot_token, admin_group_id, main_group_id
   settings (JSONB), created_at, updated_at
   ```

2. **Add `organization_id` to all tenant-scoped tables**
   - `users`, `leads`, `appointments`, `quotes`, `payments`, `warranties`
   - `broadcasts`, `pipeline_stages`, `audit_logs`, `lead_actions`
   - NOT to: `system_errors` (global), `blocked_chats` (global)

3. **Row-level filtering**
   - Every repository method adds `WHERE organization_id = :org_id`
   - Option A: Inject org_id into repository constructor
   - Option B: PostgreSQL Row-Level Security policies

4. **API authentication changes**
   - JWT token includes `org_id`
   - All API queries scoped to token's org
   - API keys for external integrations (per org)

5. **Bot changes**
   - Each org has its own bot token
   - Bot lookup by incoming token → org resolution
   - Shared process with multiple bot instances, or separate deployments per org

---

## First 10 Safest Implementation Tasks

These tasks carry zero risk to the existing Telegram bot:

| # | Task | Type | Risk |
|---|------|------|------|
| 1 | Create `shared/constants/pricing.py` — consolidate price constants | Refactor (imports only) | Zero |
| 2 | Create `shared/utils/sanitize.py` — break core->apps dependency | Refactor (imports only) | Zero |
| 3 | Create `apps/api/__init__.py` + `main.py` — bare FastAPI with `/health` | New files | Zero |
| 4 | Create `core/auth/jwt.py` — token create/verify service | New files | Zero |
| 5 | Create API schemas in `apps/api/schemas/` | New files | Zero |
| 6 | Add `GET /api/v1/leads` — read-only lead listing | New route | Zero |
| 7 | Add `GET /api/v1/pipeline/kanban` — read-only kanban JSON | New route | Zero |
| 8 | Add `GET /api/v1/analytics` — read-only analytics JSON | New route | Zero |
| 9 | Consolidate `_notify_admin()` helpers into `LeadNotificationService` | Refactor (3 handlers) | Low |
| 10 | Add unit tests for `LeadService` | New test file | Zero |
