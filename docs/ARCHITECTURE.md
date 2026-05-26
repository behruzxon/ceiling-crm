# Architecture

## Current Architecture Diagram

```
                    ┌───────────────────────────────┐
                    │        Telegram API            │
                    └──────────────┬────────────────┘
                                   │
                    ┌──────────────▼────────────────┐
                    │    apps/bot/main.py            │
                    │    (Dispatcher + Middlewares)   │
                    │                                │
                    │  Middleware chain:              │
                    │  Auth→Security→Locale→          │
                    │  GroupCtx→RateLimit→Audit       │
                    └──────────────┬────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                     │
    ┌─────────▼──────┐  ┌─────────▼──────┐  ┌──────────▼─────┐
    │  Admin Router   │  │ Private Router  │  │  Group Router   │
    │  (17 handlers)  │  │ (22 handlers)   │  │  (11 handlers)  │
    └─────────┬──────┘  └─────────┬──────┘  └──────────┬─────┘
              │                    │                     │
              │         ┌─────────▼──────┐              │
              │         │Callbacks Router │              │
              │         │ (8 handlers)    │              │
              │         └─────────┬──────┘              │
              └────────────────────┼────────────────────┘
                                   │
                    ┌──────────────▼────────────────┐
                    │      core/services/           │
                    │  (35+ business logic services) │
                    │  LeadService, CRMService,      │
                    │  PipelineService, AIOrchestrator│
                    │  PricingService, BroadcastSvc   │
                    └──────────────┬────────────────┘
                                   │
                    ┌──────────────▼────────────────┐
                    │    core/repositories/ (ABCs)   │
                    │  14 abstract interfaces        │
                    └──────────────┬────────────────┘
                                   │
         ┌─────────────────────────┼──────────────────────────┐
         │                         │                           │
┌────────▼────────┐  ┌─────────────▼──────────┐  ┌────────────▼───────┐
│ infrastructure/  │  │  infrastructure/cache/ │  │ infrastructure/    │
│ database/        │  │  Redis client          │  │ queue/             │
│ 20 ORM models    │  │  3 DBs (cache/celery/  │  │ Celery tasks       │
│ 14 concrete repos│  │  FSM sessions)         │  │ (broadcast, notif, │
│ 25 migrations    │  │  CacheKeys + CacheTTL  │  │  export, packages) │
└────────┬────────┘  └────────────────────────┘  └────────────────────┘
         │
┌────────▼────────┐
│   PostgreSQL 15  │
│   (single node)  │
└─────────────────┘
```

Side processes:

```
┌───────────────────────┐    ┌──────────────────────┐
│  apps/scheduler/      │    │  Celery Worker        │
│  APScheduler          │    │  infrastructure/queue │
│  9 job groups        │    │  broadcast, export,   │
│  (followup, analytics,│    │  notification tasks   │
│   broadcast, cache,   │    └──────────────────────┘
│   autopilot, closing) │
└───────────────────────┘

┌───────────────────────┐    ┌──────────────────────┐
│  Prometheus           │    │  Grafana              │
│  :9090/metrics        │    │  :3000 (dashboards)   │
│  scrapes bot metrics  │    │  reads from Prometheus│
└───────────────────────┘    └──────────────────────┘
```

---

## Layer Details

### Bot Layer (`apps/bot/`)

**Entrypoint:** `apps/bot/main.py` — builds Dispatcher, registers middlewares and routers, selects polling vs webhook mode.

**Middleware execution order** (outermost to innermost):
1. `AuthMiddleware` — upserts Telegram user, injects `db_user`, `user_role`, `db_session`
2. `SecurityMiddleware` — burst detection, message size limits, callback sanitization
3. `LocaleMiddleware` — resolves locale, injects `_` translator function
4. `GroupContextMiddleware` — resolves ceiling category from group metadata
5. `RateLimitMiddleware` — per-user sliding window (Redis)
6. `AuditMiddleware` — fire-and-forget audit log writing
7. `GroupMenuInjectorMiddleware` — message outer middleware, sends group menu to first-time senders

**Router hierarchy** (registration order = priority):
```
dispatcher
├── admin_router          [RoleFilter(ADMIN, SUPERADMIN)]
│   ├── dashboard, leads, pipeline, radar, analytics, sales_report
│   ├── lead_advice, broadcasts, scheduler, operator_stats
│   ├── reports, media, autopilot, close_advice, stats, system_status
├── callbacks_router      [Inline keyboard callbacks]
│   ├── lead_callbacks, kanban_callbacks, lead_status
│   ├── cta_callbacks, sales_closer_callbacks, operator_callbacks
│   ├── pipeline_callbacks, payment_callbacks, package_callbacks
├── group_router          [Group/supergroup events]
│   ├── group_admin, group_start, admin_group_tracker
│   ├── welcome, member_status
├── private_router        [DM conversations]
│   ├── support, catalog, promotions, about, packages
│   ├── pricing, my_orders, payment, order, operator
│   ├── measurement_lead, lead_capture, ai_support (catch-all last)
├── moderation_router     [Link guard, flood guard]
└── group_messages_router [Silent catch-all]
```

**Handler data dict** — every handler receives:
- `db_user` (ORM User), `user_role` (UserRole enum), `db_session` (AsyncSession)
- `locale` (str), `_` (translator), `category` (CeilingCategory, groups only)
- `group_db` (Group metadata, groups only), `is_group_chat` (bool)

**FSM strategy:** `USER_IN_CHAT` — separate state per user per chat, stored in Redis DB 2.

### Service Layer (`core/services/`)

41 services. Key categories:

**CRM services** (require `AsyncSession` via DI):
- `UserService` — user CRUD, role management
- `LeadService` — lead CRUD, pipeline insertion, action logging
- `CRMService` — pipeline stage advancement with transition validation
- `PipelineService` — kanban views, move stage (admin override), audit logging
- `PricingService` — quote calculation (base price + addons + modifiers)
- `BroadcastService` — broadcast CRUD, status management
- `PaymentService` — payment CRUD, status transitions
- `WarrantyService` — warranty CRUD
- `AdminGroupService` — admin group tracking
- `StatsService` — join tracking, daily stats
- `LeadAnalyticsService` — operator performance from lead_actions

**AI intelligence services** (pure functions, no I/O):
- `AIOrchestrator` — top-level, composes all 8 sub-services
- `SalesBrain` — builds composite `SalesBrainDecision`
- `AutoCloser` — operator reply suggestions
- `DealProbability` — deal closure probability (0-100%)
- `BuyerIntelligence` — 4 buyer type classification
- `RevenuePrediction` — revenue range estimation (UZS)
- `NegotiationEngine` — objection tactic selection (8 tactics)
- `ConversationGraph` — decision stage + engagement trend
- `FollowupBrain` — follow-up type + delay scheduling
- `DealRadar` — lead priority ranking (5 buckets)
- `ConversationIntelligence` — health scoring + signal detection
- `OperatorAssistant` — on-demand reply suggestions

**Agent system** (`core/services/agent/`):
- `AgentDecisionEngine` — priority-ordered rule evaluation
- 10 rules (StaleLeadRule, PhoneCapturedRule, ObjectionRule, etc.)
- `CooldownManager` — Redis-based deduplication
- `SignalBuilder` — constructs signal dict from all CRM data

### Repository Layer (`core/repositories/` + `infrastructure/database/repositories/`)

13 abstract interfaces (+ 1 generic `BaseRepository`) in `core/repositories/`, 14 concrete implementations in `infrastructure/database/repositories/`.

**Generic base:** `BaseRepository[T, IDType]` defines `get_by_id`, `create`, `update`, `delete`.

**Key patterns:**
- `_UNSET` sentinel for partial updates (distinguishes "don't touch" from "set to None")
- Immutable append-only tables: `pipeline_stages`, `audit_logs`, `system_errors`
- `pg_insert(...).on_conflict_do_update()` for upserts
- All enum columns use `values_callable=lambda x: [e.value for e in x]`

### Database Layer (`infrastructure/database/`)

**19 ORM models** inheriting from `Base(DeclarativeBase)`.

**Session management** (`infrastructure/database/session.py`):
- `get_session()` — async context manager, auto-commit/rollback
- `get_readonly_session()` — never commits, for analytics queries
- `get_db()` — FastAPI dependency (exists but unused)
- Engine singleton with connection pooling (pool_size=20, max_overflow=10, recycle=3600s)
- asyncpg with JIT disabled, 60s command timeout

**25 Alembic migrations** — forward-only, no data-loss operations.

### AI Layer

See `docs/AI_SYSTEM.md` for full details. Summary:

- OpenAI GPT-4o with 8,000 token budget per request
- Prompt injection firewall (pre-flight + post-flight)
- Rolling 12-message conversation window with auto-summary every 10 turns
- Redis-backed lead scoring (0-100) and AI memory (30-day TTL)
- 8 pure-function intelligence services composed into `SalesBrainDecision`
- Rule-chain agent engine with 10 rules and Redis cooldown

### Scheduler / Celery Layer

**APScheduler** (`apps/scheduler/main.py`):
- 9 job files: followup, broadcast, analytics, cache, conversation intelligence, sales autopilot, closing, auto-sales, outcome resolver
- Runs as separate process with its own DB/Redis connections
- Timezone: Asia/Tashkent

**Celery** (`infrastructure/queue/`):
- Broker: Redis DB 1
- Task modules: broadcast_tasks, notification_tasks, export_tasks, package_tasks
- Pattern: async implementation inside Celery via `asyncio.run()` with local engine creation

### Monitoring / Deploy Layer

**Prometheus:**
- Bot: updates_total, handler_duration, leads_created, pipeline_transitions, broadcast_sent, active_users
- OpenAI: tokens_prompt, tokens_completion, requests, request_duration
- Health endpoint: `/health` returns DB/Redis/OpenAI status

**Alert rules** (6): high error rate, high latency, pool exhaustion, Redis memory, OpenAI errors, OpenAI latency.

**Docker Compose:**
- Dev: postgres, redis, bot, worker, scheduler (live code mount)
- Prod: adds resource limits, Prometheus, Grafana, Redis auth, media volume

---

## Target Architecture (with FastAPI + Web Dashboard)

```
                    ┌────────────────────────────────────┐
                    │          nginx (API Gateway)        │
                    │    SSL termination, rate limiting    │
                    └────────┬──────────────┬────────────┘
                             │              │
                    ┌────────▼──────┐  ┌────▼────────────┐
                    │  FastAPI      │  │  Telegram API    │
                    │  /api/v1/     │  │  (webhook/poll)  │
                    │  JWT auth     │  │                  │
                    │  OpenAPI docs │  │  aiogram 3.7     │
                    └────────┬──────┘  └────┬────────────┘
                             │              │
                    ┌────────▼──────────────▼────────────┐
                    │     Shared Service Layer            │
                    │  (same services, same repos)        │
                    └────────────────┬───────────────────┘
                                     │
                    ┌────────────────▼───────────────────┐
                    │      Repository Abstractions        │
                    └────────────────┬───────────────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                       │
    ┌─────────▼────────┐  ┌─────────▼──────┐  ┌─────────────▼────┐
    │  PostgreSQL       │  │    Redis        │  │    Celery         │
    │  (+ read replica) │  │  (3 DBs)        │  │  (task workers)   │
    └──────────────────┘  └────────────────┘  └──────────────────┘

                    ┌────────────────────────────────────┐
                    │    Web Dashboard (SPA frontend)     │
                    │    Calls /api/v1/* via JWT           │
                    │    (separate repo, not in scope)     │
                    └────────────────────────────────────┘
```

**Key change:** FastAPI and aiogram both depend on the same service layer. The bot continues using middleware-injected sessions; FastAPI uses `Depends(get_db)` for request-scoped sessions. Both share repositories, domain models, and enums.
