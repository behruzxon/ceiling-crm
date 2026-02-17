# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CeilingCRM is an enterprise Telegram bot CRM for a stretch ceiling business (Uzbekistan market). Built with aiogram 3.7 + aiogram-dialog, async SQLAlchemy 2.0 on PostgreSQL, Redis for caching/FSM/Celery broker, and OpenAI GPT-4o for AI support.

## Development Commands

```bash
# Infrastructure (requires Docker)
docker compose up -d postgres redis

# Install dependencies
pip install -r requirements.txt
pip install -e ".[dev]"

# Run the bot (polling mode for dev)
python -m apps.bot.main

# Run scheduler
python -m apps.scheduler.main

# Database migrations
alembic upgrade head                              # apply all
alembic revision --autogenerate -m "description"  # generate new

# Seed database (set SUPERADMIN_TELEGRAM_ID env var first)
python scripts/seed_db.py

# Tests
pytest tests/unit/
pytest tests/unit/test_foo.py::TestBar::test_baz  # single test
pytest tests/integration/
pytest tests/e2e/

# Linting
ruff check .
mypy .

# Production deployment
docker compose -f docker-compose.prod.yml up -d
```

## Architecture

The codebase follows a layered architecture with strict dependency direction: `apps → core → shared`, with `infrastructure` implementing `core` interfaces.

### Layer responsibilities

- **`apps/bot/`** — Telegram bot application (aiogram). Handlers organized by scope: `handlers/admin/` (role-gated via `RoleFilter`), `handlers/private/` (DM flows), `handlers/group/` (group events), `handlers/callbacks/` (inline keyboards). Middlewares run in order: Auth → Locale → GroupContext → RateLimit → Audit.
- **`apps/scheduler/`** — APScheduler background jobs (follow-ups, reminders).
- **`core/domain/`** — Domain models (Lead, User, Appointment, Quote, Broadcast, Audit). Frozen Pydantic models, no framework dependencies.
- **`core/repositories/`** — Abstract repository interfaces (ABC). `BaseRepository[T, IDType]` defines the generic CRUD contract.
- **`core/services/`** — Business logic services (CRM, Lead, User, Pricing, Analytics, AI, Broadcast, Export). Depend on repository abstractions, not implementations.
- **`core/events/`** — Internal event bus with domain events (LeadCreated, StageChanged, AppointmentBooked, BroadcastCompleted).
- **`infrastructure/database/`** — SQLAlchemy ORM models (`models/`), concrete repository implementations (`repositories/`), async session management (`session.py`), and Alembic migrations.
- **`infrastructure/cache/`** — Redis client with `CacheClient` wrapper. Three separate Redis DBs: db0=cache, db1=Celery, db2=FSM sessions. Rate limiting via sliding window.
- **`infrastructure/storage/`** — File storage adapter (local filesystem or S3). Used for media uploads in admin panel.
- **`infrastructure/di.py`** — Dependency injection wiring. Factory functions: `get_user_service(session)`, `get_lead_service(session)`, `get_crm_service(session)`.
- **`infrastructure/queue/`** — Celery task definitions (broadcast, notification, export).
- **`shared/config/`** — Pydantic Settings loaded from `.env`. Access via `get_settings()` (cached singleton). Nested settings groups with env prefixes (BOT_, POSTGRES_, REDIS_, OPENAI_, SENTRY_, RATE_LIMIT_).
- **`shared/constants/enums.py`** — Single source of truth for all business enums (UserRole, PipelineStage, CeilingCategory, LeadSource, etc.).
- **`shared/i18n/`** — Multilingual support (uz, ru, en). Locale resolved by `LocaleMiddleware`.

### Key patterns

- **Repository pattern**: `core/repositories/` defines ABCs, `infrastructure/database/repositories/` implements them. Services inject repository abstractions.
- **DI wiring**: `infrastructure/di.py` provides factory functions. `AuthMiddleware` opens a session and injects `db_user`, `user_role`, `db_session` into handler data.
- **RBAC**: `RoleFilter` checks `db_user.role` against required roles. Permission hierarchy: SUPERADMIN > ADMIN > MANAGER > INSTALLER > CLIENT. Role changes enforced in `UserService.change_role()`.
- **Session management**: Use `async with get_session() as session` for read-write, `get_readonly_session()` for queries. Sessions auto-commit on success, rollback on exception.
- **Pipeline**: Event-sourced via `pipeline_stages` table. `CRMService.advance_stage()` validates transitions against `ALLOWED_TRANSITIONS` map.
- **Media upload**: Admin photo/video/document uploads routed through `StorageAdapter` (local/S3). Telegram `file_id` stored for re-sending.
- **ORM base**: All models inherit from `infrastructure.database.session.Base` (DeclarativeBase).
- **Bot modes**: Polling locally (no BOT_WEBHOOK_URL), webhook in production.
- **FSM strategy**: `USER_IN_CHAT` — separate FSM state per user per chat.

### RBAC roles

| Role | Access |
|------|--------|
| SUPERADMIN | All admin commands + role management (promote to ADMIN) |
| ADMIN | Dashboard, reports, broadcasts, scheduler, media uploads, role management (promote to MANAGER/INSTALLER) |
| MANAGER | Lead management, pipeline transitions, appointments |
| INSTALLER | Assigned appointments, installation status updates |
| CLIENT | Catalog, pricing calculator, lead submission |

## Code Style

- Python 3.11+, line length 100 (ruff + black)
- Ruff rules: E, F, I, N, UP, ANN, ASYNC, B, C4, T20. Tests exempt from ANN/S101.
- mypy strict mode with pydantic plugin
- pytest with `asyncio_mode = "auto"` — async test functions work without `@pytest.mark.asyncio`
