# Claude Context

Read this file first when starting a new session on this project.

---

## What This Project Is

**Vashpotolok AI Enterprise CRM** — a production Telegram bot CRM for a stretch ceiling business in Qashqadarya, Uzbekistan. Built with aiogram 3.7, SQLAlchemy 2.0 (async), PostgreSQL 15, Redis 7, OpenAI GPT-4o, Celery, APScheduler, Docker Compose.

The bot handles: lead capture, AI sales conversations (in Uzbek), pipeline management, pricing calculator, catalog browsing, payments, warranties, broadcasts, follow-up scheduling, admin analytics, and deal intelligence.

## Current State

- **Telegram bot:** Fully functional, production-ready
- **REST API:** Does not exist yet (FastAPI is in dependencies but has zero endpoints)
- **Web dashboard:** Does not exist
- **Multi-tenancy:** Not implemented (single-tenant)
- **Documentation:** Complete (see `docs/` folder)

## Target Direction

Add a FastAPI REST API alongside the Telegram bot, sharing the same service and repository layers. Then build a web dashboard that consumes the API. Eventually add multi-tenancy for SaaS.

The Telegram bot must continue working identically throughout all changes.

## Main Rules

1. **Never break the bot.** See `docs/DO_NOT_BREAK.md` for the full checklist.
2. **Dependency direction:** `apps -> core -> shared`. Infrastructure implements core interfaces. Core must NEVER import from apps.
3. **Middleware order matters.** Auth -> Security -> Locale -> GroupContext -> RateLimit -> Audit. Do not reorder.
4. **Router order matters.** admin > callbacks > group > private > moderation > catch-all. Within private, ai_support is always last.
5. **Enum serialization:** Always use `values_callable=lambda x: [e.value for e in x]` on SQLAlchemy Enum columns.
6. **Session pattern:** Use `get_session_factory()` + `async with factory() as session:` in handlers. Use `get_db()` for FastAPI.
7. **DI pattern:** `infrastructure/di.py` has factory functions like `get_lead_service(session)`. No DI framework.
8. **AI services are pure functions.** They take signal dicts and return dataclasses. No I/O, no DB, no Redis inside them.
9. **Celery + asyncio pattern:** Never use global engine inside Celery tasks. Create local engine, dispose in finally.
10. **Single source of enums:** `shared/constants/enums.py` is the only place business enums are defined.

## Key Documentation

| Doc | Purpose |
|-----|---------|
| `docs/PROJECT_PASSPORT.md` | Project identity, stack, capabilities, limitations |
| `docs/ARCHITECTURE.md` | Current + target architecture diagrams |
| `docs/MODULE_MAP.md` | Every module with reusability assessment |
| `docs/CRM_DOMAIN.md` | Lead lifecycle, pipeline, payments, warranties |
| `docs/AI_SYSTEM.md` | AI pipeline, scoring, follow-ups, safety |
| `docs/WEB_INTEGRATION_PLAN.md` | 5-phase roadmap from cleanup to SaaS |
| `docs/DO_NOT_BREAK.md` | Production flows that must never break |
| `docs/NEXT_STEPS.md` | Exact next tasks with file lists |

## Next Step

**Phase 1: Foundation Cleanup** — 3 tasks:
1. Consolidate pricing constants into `shared/constants/pricing.py`
2. Move `sanitize_*` functions to `shared/utils/sanitize.py`
3. Move OpenAI client helpers to `infrastructure/ai/openai_client.py`

All 3 are import-path refactors with re-exports for backward compatibility. Zero functional changes. See `docs/NEXT_STEPS.md` for details.

## Known Issues to Be Aware Of

- `core/services/ai_sales_advice.py` has 3 lazy imports from `apps/bot/` (dependency violation — Phase 1 fix)
- `core/services/deal_closer_service.py` has 1 lazy import from `apps/bot/` (same)
- `ADDON_PRICES` is duplicated identically in `pricing_service.py` and `revenue_predictor_service.py` (Phase 1 fix)
- Two intentionally different price sets exist: `DEFAULT_BASE_PRICES` (100k-300k, for quotes) vs `_DESIGN_PRICES` (80k-140k, for AI/customer display) — do NOT merge them
- AI system prompt (`system_prompt.py` line 49-53) has hardcoded prices that must stay in sync with `_DESIGN_PRICES`
- `ai_support.py` is large (split into sub-modules: ai_detection, ai_memory, ai_scoring, ai_openai, ai_notifications, ai_followups, ai_pricing_helpers)
- Event bus has 4 events defined but only 2 emitted (`LeadCreated`, `StageChanged`), handlers directory is empty
- Export service has 3 stub methods raising NotImplementedError
- Test coverage is limited (17 test files for ~44k LOC)

## File Counts (verified)

- 17 admin handlers, 22 private handlers, 8 callback handlers, 11 group handlers
- 7 middlewares, 7 FSM state files, 8 keyboard files, 9 scheduler job files
- 41 services, 13 abstract repos (+1 base), 14 concrete repos
- 19 ORM models, 25 migrations, 17 test files
