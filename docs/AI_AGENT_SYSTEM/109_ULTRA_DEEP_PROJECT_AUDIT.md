# Ultra Deep Project Audit

**Date**: 2026-05-27 | **Commit**: 155a7e5 | **Status**: NOT DEPLOYED, Stage 1 NOT APPLIED

## Scores

| Module | Score | Verdict |
|--------|-------|---------|
| Git/CI | 7/10 | F821 globally ignored — risky; mypy may fail |
| Architecture | 8.5/10 | Clean layers, consistent DI, centralized constants |
| Telegram Bot | 8/10 | 10 commands, 15 buttons, 7 FSM flows, safe fallbacks |
| AI Assistant | 8.5/10 | Deterministic price path, knowledge hardened, 6 quick buttons |
| AI Agent/Orchestrator | 8/10 | Full pipeline, LOG_ONLY safe, no-send verified |
| Price Calculator | 9/10 | Source-of-truth service, taxminiy warnings, discounts |
| Operator Handoff | 7.5/10 | Queue foundation, ETA-safe, missing API/web UI |
| CRM/Web | 7.5/10 | Design system, CRM inbox, missing charts/queue view |
| Database/Migrations | 8/10 | 43+ migrations, linear chain, proper indexes |
| Security/Privacy | 8.5/10 | 20 flags OFF, injection firewall, phone masking |
| Config/Flags | 9/10 | Safe defaults, documented, no accidental enables |
| Scheduler | 7.5/10 | Jobs registered, dangerous ones gated, missing expire job |
| Tests | 8.5/10 | 5552 tests, strong services/AI coverage, weak handler mocking |
| Performance | 7/10 | Indexes present, Redis caching, no load tests |
| Deploy Readiness | 7/10 | Dockerfile exists, no health checks, no automated backup |

**Overall: 8.0/10**

## Architecture Audit

Layers: `apps → core → shared`, `infrastructure` implements `core` interfaces. Clean separation maintained. DI via factory functions in `infrastructure/di.py`. Constants centralized in `shared/constants/`. Knowledge in `shared/knowledge/uz.md` injected into system prompt at import.

Strengths: pure service functions, frozen dataclasses, consistent session management, event-driven agent pipeline.

Risks: ai_support.py is 1100+ lines (fat handler), some pre-existing circular-import workarounds with noqa, F821 globally ignored hides real undefined-name bugs.

## Bot Audit

10 commands registered, 9 main menu + 6 AI buttons, 50+ callbacks across 13 namespaces, 7 FSM flows. Router priority correct (admin > callbacks > group > private > moderation). AI support last in private (catch-all). Quick buttons handled before general AI handler (no double-reply).

Risks: No async handler behavior tests (all tests check source code, not runtime). User can theoretically get stuck if FSM state corrupts. No timeout on FSM states.

## AI Assistant Audit

Deterministic paths: price query with area+design (PriceCalculatorService), objection detection (130+ keywords + fuzzy regex), stop handling (12+ words), greeting, catalog, measurement. OpenAI called only when no deterministic path matches. Rate limit 100/day. Injection firewall 14 patterns. Output leak guard 15 markers. Memory: Redis 30-day + DB 12-message rolling.

Risks: OpenAI unavailable = failsafe message (acceptable). No photo/voice. Catalog is URL-only.

## AI Agent Audit

Full pipeline: signal → decision → offer → policy → orchestrator → sandbox. LOG_ONLY mode only writes traces to memory_data. User experience unchanged in LOG_ONLY. No sends, no followups, no auto-execute. All gated by flags defaulting to FALSE.

Stage 1 readiness: YES (CONDITIONAL GO). Stage 2 needs more testing.

## Security Audit

20 dangerous flags all default FALSE. Injection firewall active. Phone masked in memory/traces. Tokens redacted. Admin auth disabled by default (should enable ADMIN_SESSION_AUTH before production web access). CSRF disabled by default. No raw phone in logs verified. No token leak in responses verified.

Critical: ADMIN_SESSION_AUTH_ENABLED and ADMIN_CSRF_ENABLED should be TRUE in production.

## Database Audit

43+ migrations, linear chain. Latest: crm_operator_handoff_requests. Proper indexes on all major tables. Nullable fields used appropriately. JSON columns for flexible metadata. Enum columns use values_callable pattern.

Risk: No automated backup. Migration must be run before Stage 1.

## Deploy Audit

Dockerfile exists. docker-compose for dev/prod. No health check endpoints for bot. No automated backup script. No nginx/TLS config visible. Restart policies likely need review.

Blockers for production: backup automation, health checks, TLS.
