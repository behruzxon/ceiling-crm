# Project Passport

## Identity

| Field | Value |
|-------|-------|
| Project name | **Vashpotolok AI Enterprise CRM** |
| Internal codename | CeilingCRM |
| Business purpose | End-to-end Telegram-based CRM for a stretch ceiling company (Qashqadarya, Uzbekistan) |
| Current product type | Single-tenant Telegram bot CRM with AI sales assistant |
| Primary language | Uzbek (Latin), with Russian/English i18n stubs |
| Currency | UZS (Uzbek som) |
| Timezone | Asia/Tashkent (UTC+5) |

## Current Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Bot framework | aiogram + aiogram-dialog | 3.7 / 2.1 |
| Web framework | FastAPI (declared, **not wired**) | 0.111 |
| ORM | SQLAlchemy (async, asyncpg) | 2.0.30 |
| Database | PostgreSQL | 15.6 |
| Cache / FSM / Broker | Redis (3 DBs: 0=cache, 1=Celery, 2=FSM) | 7.2 |
| Task queue | Celery | 5.4 |
| Scheduler | APScheduler | 3.10 |
| AI provider | OpenAI GPT-4o | openai 1.30 |
| Monitoring | Prometheus + Grafana + Sentry | latest |
| Deployment | Docker Compose (multi-stage, non-root) | — |
| CI/CD | GitHub Actions (lint + test + build) | — |
| Python | CPython | 3.11+ |

## Architecture Layers

```
apps/           Application entry points (bot, scheduler, future API)
core/           Business logic — domain models, repository ABCs, services, events
infrastructure/ Implementation — DB models, concrete repos, cache, queue, DI, monitoring
shared/         Cross-cutting — config, enums, i18n, utils, knowledge base
```

Dependency direction is strictly enforced: `apps -> core -> shared`, with `infrastructure` implementing `core` interfaces.

## Main Folders and Responsibilities

| Folder | Contents |
|--------|----------|
| `apps/bot/handlers/admin/` | 17 admin command handlers (role-gated) |
| `apps/bot/handlers/private/` | 22 DM handlers (lead capture, pricing, catalog, AI, order, payment) |
| `apps/bot/handlers/callbacks/` | 8 inline keyboard callback handlers |
| `apps/bot/handlers/group/` | 11 group event handlers (welcome, moderation, tracking) |
| `apps/bot/middlewares/` | 7 middlewares (auth, security, locale, group context, rate limit, audit, group menu) |
| `apps/bot/states/` | 7 FSM state groups (ai_states.py lives under handlers/private/, not here) |
| `apps/bot/keyboards/` | 8 keyboard builder modules |
| `apps/scheduler/jobs/` | 9 scheduler job files |
| `core/domain/` | 8+ frozen Pydantic domain models |
| `core/repositories/` | 13 abstract repository interfaces (+ 1 generic BaseRepository) |
| `core/services/` | 41 business logic services |
| `core/events/` | Event bus (4 domain events) |
| `infrastructure/database/models/` | 19 SQLAlchemy ORM models |
| `infrastructure/database/repositories/` | 14 concrete PostgreSQL repositories |
| `infrastructure/database/migrations/` | 25 Alembic migration scripts |
| `infrastructure/cache/` | Redis client, cache key registry, TTL constants |
| `infrastructure/queue/tasks/` | Celery task modules (broadcast, notification, export, packages) |
| `infrastructure/di.py` | DI factory functions (no framework, plain factories) |
| `shared/config/settings.py` | Pydantic Settings with env var loading |
| `shared/constants/enums.py` | All business enums (single source of truth) |
| `shared/knowledge/uz.md` | Uzbek product knowledge base for AI |

## Current Production Capabilities

- Lead capture from 4 entry points (direct, measurement, order, packages)
- 9-stage pipeline with event-sourced transitions and kanban view
- AI sales assistant ("Madina") with GPT-4o, intent detection, objection handling
- Lead scoring (0-100) with 12 signal deltas, buyer type classification
- 8-service AI intelligence stack (probability, revenue, negotiation, radar, etc.)
- Rule-chain agent engine (10 rules) with Redis cooldown
- Broadcast system v2 (segment/stage targeting, blocked-chat cleanup)
- Pricing calculator FSM (room dimensions, design selection, quote generation)
- Catalog browser with inline keyboards
- Package system (browse, select, order)
- Payment tracking with status transitions and proof upload
- Warranty management (one per lead)
- Follow-up scheduling (brain-driven, 6 types, max 5 per lead)
- Admin notifications (new lead cards, hot alerts, operator assist)
- Group moderation (link guard, flood guard, welcome messages)
- Deal radar (/radar), sales analytics (/analytics), admin dashboard (/dashboard)
- Prometheus metrics, Grafana dashboards, Sentry error tracking
- Docker Compose deployment (dev + production profiles)
- GitHub Actions CI (lint, test, docker build)

## Current Limitations

- **No REST API** — FastAPI is in dependencies but has zero endpoints
- **No web authentication** — only Telegram user_id auth, no JWT/OAuth
- **Single tenant** — no organization_id on any model, no multi-tenancy
- **No web dashboard** — all admin interaction is via Telegram commands
- **No outbound webhooks** — cannot push events to external systems
- **No invoice generation** — payment model has receipt_url but no generator
- **Export service is stubbed** — 3 methods raise NotImplementedError
- **Single AI provider** — OpenAI only, no fallback
- **Uzbek-only AI** — system prompt and knowledge base are Uzbek-specific
- **No custom fields** — lead schema is fixed
- **No contact/company model** — leads serve as both contacts and deals

## Web Platform Integration Goal

Transform from a single-tenant Telegram bot CRM into a multi-channel SaaS platform:

1. Add a REST API layer (FastAPI) alongside the existing Telegram bot
2. Both channels share the same service/repository layer
3. Add web authentication (JWT) for dashboard access
4. Add a web admin dashboard (separate frontend project)
5. Eventually add multi-tenancy for SaaS deployment

The Telegram bot must continue working identically throughout all phases.

## What Must Never Be Broken

See `docs/DO_NOT_BREAK.md` for the full list. Critical items:

1. Lead capture flow (all 4 entry points)
2. AI sales assistant ("Madina") conversation loop
3. Pipeline stage transitions and kanban view
4. Admin notifications and status keyboards
5. Broadcast system
6. Follow-up scheduling
7. Payment and warranty tracking
8. Docker deployment pipeline
9. Middleware execution order (Auth -> Security -> Locale -> GroupContext -> RateLimit -> Audit)
10. Router registration order in `build_dispatcher()`

## Current Roadmap Phase

**Phase 0: Documentation** (this document set) — completed.

Next phase: **Phase 1 — Foundation Cleanup** (consolidate pricing constants, fix core->apps imports, extract sanitize helpers). See `docs/WEB_INTEGRATION_PLAN.md` and `docs/NEXT_STEPS.md`.
