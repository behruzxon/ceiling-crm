> Status: AUDIT REPORT. Deploy: NO. VPS: NO. Flags: NOT ENABLED. Stage 1: NOT APPLIED.
> Live sender: NOT ENABLED. Campaign send: NOT ENABLED. Operator reply live send: NOT ENABLED.

# 131 — Full Codebase, AI, and Web Platform Audit

This is a brutally-honest, read-only audit of the CeilingCRM / Vashpotolok platform on `main`
at commit `0187302` (May 28). No production code was changed. No commit was created.

The docs that would normally sit at numbers 125–129 were already used for recent
implementation/checklist work (`125_STAGE_1_READINESS_REVIEW`, `126_OPERATOR_NOTIFICATION_DIGEST`,
`127_FINAL_CRM_WEB_UX_POLISH`, `128_PRODUCTION_DEPLOYMENT_RUNBOOK`,
`129_STAGE_1_LOCAL_DRY_RUN_CHECK`). To avoid overwriting them, this audit pack is shifted
to **131–135**.

---

## A) Executive Audit Summary

### Scorecard (out of 10)

| Dimension | Score | One-line verdict |
|---|---|---|
| Overall platform | **7.7** | Strong scaffold, default-safe, not yet validated against real traffic. |
| AI agent | **7.4** | Powerful deterministic pipeline + gated LLM; needs a real action surface. |
| Telegram bot | **7.6** | Wide flow coverage; FSM has no timeout; some dead states. |
| Web CRM | **7.0** | Useful read-mostly admin; campaign/operator write paths intentionally inert. |
| Security | **7.2** | Defaults safe; CSRF / RBAC / session auth scaffolded but OFF. |
| Production readiness | **5.5** | Needs gates flipped, smoke deploy, real backup drill, live monitoring. |
| Test quality | **7.5** | ~6,800 tests; strong simulation; weak handler/runtime coverage. |
| Code quality | **7.0** | Layered, but mypy not strict; CI mypy is non-blocking. |
| Business usefulness | **7.5** | Lead capture, pricing, handoff queue, missed-leads board are all real. |

### Verdict by use case

| Use case | Verdict |
|---|---|
| Is this MVP? | **YES** — bot, CRM, AI agent scaffolding all present. |
| Is this production-ready? | **NOT READY** — security gates OFF, no live deploy, no backup drill. |
| Is this enterprise-grade? | **NOT YET** — RBAC/CSRF/IP-allowlist scaffolded only; CI mypy non-blocking. |
| Is this safe for LOG_ONLY? | **CONDITIONAL GO** — defaults are LOG_ONLY; one VPS dry-run away. |
| Is this safe for live sending? | **NOT READY** — needs Stage 2/3/4/5 gating + approval queue UI hardening. |
| Is this ready for a real Vashpotolok operator? | **CONDITIONAL GO** — read flows ready; write flows (operator reply, campaigns) intentionally disabled. |

---

## B) Architecture Audit

### Layering check

Dependency direction `apps → core → shared`, with `infrastructure` implementing `core` interfaces,
is followed. Spot-checked:

- `apps/bot/handlers/private/lead_capture.py` calls `lead_service.create_lead()` (not the repo).
- `apps/web/main.py` only talks to `apps/web/api_client.py` — the API Bearer token never
  reaches the browser.
- `core/services/*` rarely imports `infrastructure/*` directly; DI wiring lives in
  `infrastructure/di.py`.

### Counts

- `apps/`: 161 Python files (bot 100+, api 18, web 6 + 12 templates, scheduler 17 jobs).
- `core/`: 174 files, of which `core/services/` is **109 files** — the heaviest layer.
- `infrastructure/`: 119 files; **43 alembic migrations** in a linear chain (latest
  `20260527_0530_n1o2p3q4r5s6_add_crm_operator_handoff_requests`).
- `shared/`: 24 files (config, constants, i18n, knowledge/uz.md, utils).
- `tests/`: 256 files (unit, integration, simulation, e2e/).
- `docs/`: 100+ docs in `docs/AI_AGENT_SYSTEM/` (latest pre-audit: `130_STEP_13_PRODUCTION_DRY_RUN_REPORT.md`).

### Top architecture strengths

1. Clean layered split, with `apps → core → shared` respected.
2. Repository ABCs in `core/repositories/`, concrete impls in `infrastructure/database/repositories/`.
3. DI via plain factories (no magic container).
4. `shared/constants/enums.py` and `shared/constants/pricing.py` are the canonical sources.
5. SQLAlchemy enums consistently use `values_callable=lambda x: [e.value for e in x]`
   (per `MEMORY.md` history this was an incident; now fixed).
6. Pure-function services (`shared/utils/lead_scoring.py`, `shared/utils/deal_probability.py`,
   `core/services/revenue_predictor_service.py`, `core/services/negotiation_engine_service.py`)
   are easy to test and easy to compose.
7. Sandbox/queue/sender split (`agent_execution_sandbox_service.py`,
   `agent_execution_queue_service.py`, `approved_execution_sender_service.py`) cleanly separates
   "decide / stage / send" — exactly what a regulated action surface should look like.
8. Default-safe configuration (every dangerous flag defaults False; LOG_ONLY everywhere).
9. Per-pod, per-user FSM strategy (`FSMStrategy.USER_IN_CHAT`).
10. Router order is documented and intentional in `apps/bot/main.py`.

### Top architecture issues

1. **`core/services/` is 109 files** — too many siblings, no internal grouping. Some clearly
   belong together (`agent/`, `crm/`, `ai/`, `stage1..stage5/`, `revenue/`, etc.).
2. Several **god files** — `closing_readiness_service.py` (~992 LOC),
   `next_best_action_service.py` (~915), `sales_analytics_service.py` (~856) —
   trying to do too much in one file.
3. Two parallel "agent" namespaces — `core/services/agent/*` (engine, rules, signal_builder,
   cooldown) and `core/services/agent_*.py` (decision_engine, response_orchestrator…).
   Hard to know which is authoritative; both ship.
4. **Duplicate phone normalization** — done in both `lead_capture.py` and `measurement_lead.py`;
   `shared/utils/phone.py` exists but is not the single source.
5. Pricing has two layers — `core/services/pricing_service.py` and
   `core/services/price_calculator_service.py`. Customer-facing should go through
   `shared/constants/pricing.DESIGN_PRICES_CUSTOMER`; not all call sites are obviously routed.
6. `apps/bot/states/appointment.py` and `apps/bot/handlers/private/catalog.py`
   `CatalogStates.waiting_for_design` are wired to nothing.
7. `apps/web/main.py` — every page calls one or more `/api/v1/...` endpoints over HTTP.
   This is correct (token stays server-side) but adds per-request latency; no batching.
8. No internal event bus consumer for several emitted events (e.g. `LeadCreated` triggers
   admin notify directly inside handler, not through an event subscriber).
9. `infrastructure/cache/keys.py` is the documented single source for Redis keys, but a few
   call sites still build keys inline (audit `grep "rds:" shared/ core/`).
10. `apps/bot/middlewares/security.py` keeps burst state in-memory — won't survive a second
    pod or a restart.
11. `apps/bot/error_handler.py` swallows `True` for all unhandled exceptions; user receives no
    feedback. OK for noise control, bad for diagnosis.
12. `infrastructure/queue/` (Celery) and `apps/scheduler/` (APScheduler) overlap; not all
    contributors will know which to use for a new background job.
13. `apps/web/templates/agent.html` and `apps/web/templates/crm_contacts.html` mix inline
    `<script>` with template variables — fragile; one wrong `{{ }}` can break JS.
14. `docs/AI_AGENT_SYSTEM/` is the only doc index — there's no index page listing all 130 docs.
15. CSRF middleware exists but is not wired into FastAPI app middleware stack — only the service
    is built.
16. Tests at `tests/unit/docs/` are mostly substring assertions on doc text — they validate
    that we wrote the right paragraph, not that anything works.
17. No `__all__` in service `__init__.py` files — explicit imports only.
18. There is no canonical "agent capability matrix" doc; this audit closes that gap.
19. `apps/api/dependencies/auth.py` allows open access in `app_env == "development"` — fine
    locally, but easy to forget in CI environments that aren't tagged development.
20. There is no architecture-level test that asserts `apps/` does not import from
    `infrastructure/` directly (architecture lint).

### Do-not-touch list (this audit pass)

- Anything inside `core/services/stage1_observation_report_service.py` …
  `stage5_live_send_readiness_service.py` — these implement the explicit gating contract.
- Alembic migrations — never edit existing.
- `shared/constants/pricing.py` — single source of truth.
- `apps/bot/main.py` router registration order.
- `apps/bot/ai/system_prompt.py` — change only with knowledge-base coordination.

---

## C) AI Agent Capability Audit (summary)

The deep map lives in [`132_AI_AGENT_PLATFORM_CAPABILITY_MAP.md`](132_AI_AGENT_PLATFORM_CAPABILITY_MAP.md).
Headlines:

- **Sees**: sanitized text, FSM state, persisted `AgentMemoryModel` (area, district, phone-masked,
  interested designs, lead temperature), short conversation history (last ~8 messages), recent
  journey events, deterministic signals (intent, objection, urgency, area, budget).
- **Decides**: 15 customer states, 11 action types, priority/confidence scores, deal probability,
  buyer type, revenue estimate, negotiation tactic.
- **Acts (today, by default)**: writes memory, writes traces. Does **NOT** send.
- **Could act (when flags enabled)**: send user DM, send admin alert, escalate handoff, schedule
  followup — all through `approved_execution_sender_service` with revalidation at send time.
- **Blind spots**: cannot see CRM contact tags/notes, cannot see operator workload, cannot see
  price-history events as structured records, cannot see handoff queue state, cannot see web
  audit logs, cannot read across users (correct, by design).
- **Safety posture (default)**: `AGENT_EXECUTION_MODE=log_only`,
  `AGENT_RESPONSE_ORCHESTRATOR_LOG_ONLY=true`, `AGENT_EXECUTION_LIVE_SENDER_ENABLED=false`,
  `AGENT_EXECUTION_AUTO_EXECUTE_APPROVED=false` — all OFF.

**Agent-inside-platform score: 7/10.** The decision pipeline is excellent. The action surface
needs an admin-facing approval UI (proposal-ready) and a per-action audit log before any flag is
flipped.

---

## D) Telegram Bot Audit (summary)

### Bot scope

Commands: `/start`, `/menu`, `/help`, `/cancel`, `/order`, `/price`, `/catalog`, `/ai_off`,
`/ai_reset`, `/ai_help`.

Main-menu buttons: 🛒 Zakaz, 💰 Narx, 📂 Katalog, 🎁 Tayyor paketlar, 📦 Buyurtmalarim,
☎️ Operator, 🎉 Chegirmalar, 🤖 AI yordam, ⭐ Biz haqimizda, 📣 Rassilka (admin).

Callback namespaces (no collisions found): `design:`, `grpmenu:`, `cta:*`, `pay:a:`, `pay:r:`,
`lead:*`, `pipeline:*`, `kanban:*`, `pkg:admin:*`, `agentexec:*`, `agentesc:*`, `agentfu:*`,
`gs:*`, `closer:*`.

Router registration order in `apps/bot/main.py` is documented and intentional: admin → callbacks →
group → private → moderation → group_messages.

### Top 15 bot UX gaps

1. `AppointmentStates` and `CatalogStates.waiting_for_design` are **dead states** — defined,
   never entered.
2. **No FSM timeout** — a user who walks away in `waiting_for_phone` stays there forever.
3. No "back" button on the pricing quote — only "🔄 Qayta hisoblash" or `/menu`.
4. Operator flow accepts `Ha`/`Yo'q` only; any other text falls through silently.
5. Measurement flow jumps straight in from AI without a "are you sure?" confirmation.
6. 13-district keyboard hardcoded; cities outside Tashkent are awkward.
7. Default category `ODNOTONNY` set for every captured lead — the user never picks.
8. Phone normalization duplicated between `lead_capture.py` and `measurement_lead.py`.
9. Pricing calc area is shown but not persisted to a lead until the order flow runs.
10. Group `/start` shows ReplyKeyboard only to the command sender — others see nothing.
11. Packages handler hardcodes 3 packages with inline prices; not DB-driven.
12. Lead capture doesn't check for an existing phone; can create duplicates.
13. AI followup tasks are fire-and-forget; if Celery crashes they vanish silently.
14. AuthMiddleware upserts every user, including likely-bot IDs (mitigated post-incident:
    `tg_user.id > 0` gate).
15. `apps/bot/error_handler.py` swallows all exceptions; no user-visible feedback.

### Top 15 bot risk areas

1. Callback data length check warns but does not reject — long IDs could overflow.
2. Security middleware burst detection is in-memory; useless on more than one pod.
3. AI conversation memory has no TTL clean-up; stale memory accumulates.
4. Payment callbacks don't verify the admin owns / is authorized for that specific payment.
5. Rate-limit key is per-user, not per-chat — one busy group can starve other users.
6. No tests for FSM state transition correctness — only direct handler imports.
7. `notify_new_lead` and `notify_hot_lead` are fire-and-forget; failure is silent.
8. Group moderation is registered after private but before group_messages — works today,
   but a future router insertion could break private text taps.
9. No global retry on `TelegramRetryAfter` outside the broadcast worker.
10. Pricing default base prices (`shared/constants/pricing.DEFAULT_BASE_PRICES`) must never leak
    to the customer — there is no automated assertion that customer-facing handlers route through
    `DESIGN_PRICES_CUSTOMER`.
11. Lead capture and measurement flow both create leads asynchronously; downstream code that
    reads "the lead" right after confirmation can race.
12. No per-handler rate limit; only global per-user.
13. Group link guard escalates to mute without admin review.
14. Free-text catch-all (`default_state`) is the last handler — correct, but one misplaced
    handler shadows it.
15. `apps/bot/handlers/private/ai_support.py` is large and concentrates many side effects
    (scoring, notification, deal probability, buyer type, negotiation). Splitting would help.

---

## E) Web CRM Platform Audit (summary)

13 active pages — all SSR via Jinja2, all data fetched from `/api/v1/*` over httpx in
`apps/web/api_client.py`. Auth is HTTP Basic at the FastAPI app level (`apps/web/main.py:35`).

### Page-by-page

| Page | Path | Verdict |
|---|---|---|
| Login | `/login` | ✓ Usable |
| Dashboard | `/dashboard` | ✓ Usable, mobile-friendly |
| Leads | `/leads` | ✓ Usable; pagination basic |
| Pipeline | `/pipeline` | ⚠ Read-only kanban; drag-drop not wired |
| Analytics | `/analytics` | ✓ Usable; async chart fetch with loading text |
| Agent | `/agent` | ⚠ Many async sections; uses `confirm()` dialogs |
| CRM Contacts | `/crm` | ⚠ Live summary polling missing visible code |
| Contact Detail | `/crm/{id}` | ⚠ Reply/notes UI partial; mobile breaks at narrow widths |
| Missed Leads | `/crm/missed-leads` | ✓ Read-only |
| Handoffs | `/crm/handoffs` | ✓ Read-only |
| Campaigns | `/crm/campaigns` | ✗ Scaffolded; sends intentionally disabled |
| Operator Digest | `/crm/operator-digest` | ✓ Async load |
| Security Audit | `/admin/security` | ✓ Read-only KPI |

### Top 10 web security/UX concerns

1. No CSRF token on web POSTs (`login`, `notes`, `reply`, `tags`). Service exists, not wired.
2. `apps/web/api_client.py` returns raw API error text (truncated to 500 chars) into templates —
   could leak SQL paths.
3. `agent.html` builds a `diffHtml` via `+=` of preset keys; if keys come from a hostile source,
   it would XSS. Keys come from server today — defense-in-depth still wanted.
4. Browser `confirm()` for execution approve/reject — replace with a typed-modal that shows the
   actual message to be sent.
5. Contact-detail sidebar lacks responsive layout — breaks on narrow phones.
6. No real-time updates; pages poll. No backoff.
7. Operator reply send is gated by feature flag but **does not check admin RBAC role** at the
   API endpoint — anyone with the Bearer token could trigger it once enabled.
8. Session auth routes (`admin_auth_routes.py`) are scaffolded; the actual session middleware
   path is disabled.
9. No bulk operations on contacts (bulk tag, bulk status).
10. No exports of CRM contacts list (CSV/XLSX) from the web UI.

---

## F) CRM Business Workflow Audit

What today's CRM actually does for the operator:

- **Captures every incoming user** via `AuthMiddleware` (`db_user` upsert).
- **Tracks unanswered users** via `crm_missed_leads_service.py` + missed-leads dashboard.
- **Surfaces hot leads** via `lead_notification_service.HOT_SCORE_THRESHOLD=7`.
- **Surfaces operator-needed users** via `crm_operator_handoff_service.py` + handoff queue page.
- **Tracks phone-shared leads** (memory + lead row).
- **Assigns work** via the operator-assignment UI on `/crm/handoffs`.
- **Daily report** via `crm_daily_report_service.py` (delivery OFF by default).
- **Operator digest** via `crm_operator_digest_service.py` + `/crm/operator-digest` page.
- **Lead temperature** + **lead score** persisted on every AI exchange.
- **Export**: scaffold exists (`crm_export_service.py`); web button not visible.
- **Campaign drafts**: scaffolded; send disabled by design (correct).
- **Daily reports / SLA / dashboard analytics**: services exist.

CRM business score: **7.5/10** — read flows are real; write flows (campaign send, operator reply,
followup send) are correctly gated OFF until Stage 1 observations finish.

---

## G) Price System Audit

- `shared/constants/pricing.DESIGN_PRICES_CUSTOMER` is the customer-facing source.
- `shared/constants/pricing.DEFAULT_BASE_PRICES` is the internal source — must never leak.
- `core/services/price_calculator_service.py` formats the quote and applies the auto-discount
  tiers (20m² → 5%, 40m² → 10%).
- `apps/bot/handlers/private/ai_pricing_helpers.py` and `apps/bot/handlers/private/pricing.py`
  use the calculator service. The AI handler validates LLM output: if a price not in memory is
  mentioned, the reply is blocked and replaced with a safe template.
- `core/services/crm_price_estimate_history_service.py` records every quote so the web can show a
  price-history strip on the contact detail page.

Risks:

- There is no automated assertion that `DEFAULT_BASE_PRICES` cannot reach a customer-facing
  handler; this is enforced by code review only.
- "Taxminiy" (estimated) is enforced in the system prompt but not in deterministic templates.
  Adding a generic price-disclaimer footer would harden this.
- Web does not yet have a manual calculator for operators (open the contact, generate a quote).

Price system score: **7.5/10**.

---

## H) Operator Handoff Audit

- `CRMOperatorHandoffService` handles dedup and priority.
- Handoff statuses include `pending`, `assigned`, `resolved`, `expired`.
- `apps/scheduler/jobs/crm_handoff_expire_jobs.py` auto-expires stale handoffs (default OFF,
  batch limit 100 — safe).
- Operator-assignment UI (`/crm/handoffs`) supports take/unassign and shows workload.
- The audit found no fake ETA leaks; "biz tez orada javob beramiz" sits in the system prompt
  forbidden list.

Handoff score: **7.5/10**. Next missing pieces: SLA timer per handoff, escalation if
`assigned_at + 30min < now and resolved_at IS NULL`, slack/email push for the assigned operator.

---

## I) Security / Privacy / Safety Audit

### What is actually ON

- Bot Bearer token validated with `secrets.compare_digest` in `apps/api/dependencies/auth.py`.
- Web Basic Auth validated with `secrets.compare_digest` in `apps/web/auth.py`.
- Bot security middleware: burst 5/3s, length cap 4096, callback regex `[a-zA-Z0-9:_.\-]+`,
  64-byte cap (warn-only).
- `shared/utils/sanitize.detect_prompt_injection` covers 14+ patterns (English, Russian, Uzbek).
- `shared/utils/sanitize.sanitize_ai_reply` blocks 16 system-prompt leak markers.
- Memory writes mask the phone (last 4 + first 4 digits only).
- Production validator forces `app_debug=False`, requires webhook secret + Sentry DSN.

### What is scaffolded but OFF

| Gate | Default | File |
|---|---|---|
| CSRF | `False` | `admin_csrf_enabled` (settings.py) |
| RBAC | `False` | `admin_rbac_enabled` |
| Admin session auth | `False` | `admin_session_auth_enabled` |
| IP rules | `False` | `admin_ip_rules_enabled` |
| IP block enforcement | `False` | `admin_ip_block_enforcement_enabled` |
| Live sender | `False` | `agent_execution_live_sender_enabled` |
| Auto-execute approved | `False` | `agent_execution_auto_execute_approved` |
| Campaign send | `False` | `crm_campaign_send_enabled` |
| Operator reply live send | `False` | `crm_operator_reply_enabled` |
| Operator digest delivery | `False` | `crm_operator_digest_delivery_enabled` |
| Followups master switch | `False` | `agent_followups_enabled` |
| Admin escalation | `False` | `agent_admin_escalation_enabled` |
| Allow live flags | `False` | `agent_settings_allow_live_flags` |

This is the right posture: every dangerous switch is OFF and locked behind
`allow_live_flags=False`.

### Production security blockers

1. Enable session auth + RBAC + CSRF before exposing `/admin/*` over the internet.
2. Wire CSRF middleware into the FastAPI app (the service is built, but no middleware mount).
3. Replace web `confirm()` with a typed-modal that shows the exact action.
4. Mask phone numbers everywhere — not just in AI memory.
5. Audit any log line that includes `text=` for raw PII.
6. Add an architecture/lint test asserting `apps/` does not import `infrastructure/` directly.
7. Add a regression test asserting `DEFAULT_BASE_PRICES` is never imported by any bot handler.
8. Add per-endpoint role check for any web write route (operator reply, notes, campaigns).
9. Add a webhook signature check (it exists for production but is not exercised in tests).
10. Replace browser-side error rendering of API error bodies with a generic message.

Security score: **7.2/10**.

---

## J) Database / Migrations Audit

- 43 alembic migrations, latest `n1o2p3q4r5s6_add_crm_operator_handoff_requests`.
- Linear `down_revision` chain — no branching heads.
- No data-loss migrations spotted.
- New tables receive indexes (handoff requests index on `(status, created_at)`; agent execution
  records on `execution_id` unique).
- Enum columns consistently use `values_callable=lambda x: [e.value for e in x]` per the
  `MEMORY.md` history. Past incident (broadcast Enum names vs values) is documented and fixed.
- No tests assert "migrations are consistent" / "no two revisions share down_revision".

Migration risk: low. Production readiness for migrations: needs a real backup drill.

---

## K) Config / Flags Audit

`.env.example` has 154 lines and clearly groups flags by domain. Highlights:

- Every dangerous flag defaults False and is commented.
- `AGENT_EXECUTION_MODE` is a single string with 5 documented values
  (`log_only|dry_run|canary|approval_required|live`).
- `AGENT_SETTINGS_ALLOW_LIVE_FLAGS=false` locks the dangerous flags from runtime mutation.
- `AGENT_EXECUTION_REQUIRE_APPROVAL_FOR_USER_DM=true` default is correct.

Risky defaults: none observed in the file.

Missing: a single one-page rendered "flag matrix" page on `/admin/security` showing every
critical flag's *runtime* value (not env value). Today the values are inferred from
`agent_control_center_service.py`; a one-glance page would reduce operator error.

Config score: **8.0/10**.

---

## L) Scheduler / Background Jobs Audit

Jobs in `apps/scheduler/jobs/`:

| Job | Default | Sends? | Idempotent? |
|---|---|---|---|
| `followup_jobs` | OFF | DM | yes |
| `agent_followup_jobs` | OFF | DM | yes |
| `admin_escalation_jobs` | OFF | admin DM | yes |
| `broadcast_jobs` | NOT IMPLEMENTED | — | n/a |
| `analytics_jobs` | OFF | no | yes |
| `cache_jobs` | OFF | no | yes |
| `conversation_intelligence_jobs` | OFF | no | yes |
| `sales_autopilot_jobs` | OFF | DM (if enabled) | yes |
| `closing_jobs` | OFF | DM (if enabled) | yes |
| `auto_sales_jobs` | OFF | DM (if enabled) | yes |
| `outcome_resolver_jobs` | OFF | no | yes |
| `agent_execution_jobs` | OFF | no (queue expiry only) | yes |
| `approved_execution_sender_jobs` | OFF | DM (if enabled) | revalidates before send |
| `crm_daily_report_jobs` | OFF | report channel | yes |
| `crm_handoff_expire_jobs` | OFF | no | yes, batch ≤ 100 |
| `crm_operator_digest_jobs` | OFF | DM/channel | yes |

No job imports trigger side effects (verified by `python -c "import apps.scheduler.main"` in the
final report section).

Scheduler score: **8.0/10**.

---

## M) Test Coverage Audit (summary)

Full version: [`135_TEST_AND_CI_HARDENING_AUDIT.md`](135_TEST_AND_CI_HARDENING_AUDIT.md).

- ~6,138 unit tests / 202 files.
- ~463 integration tests / 29 files.
- ~194 simulation tests / 6 files.
- 0 e2e tests.
- `tests/unit/docs/` — 19 files of substring assertions; useful but shallow.
- Mypy is **not** strict and is **continue-on-error: true** in CI.
- Lint is strict; ~40 rules ignored as legacy debt.

Test score: **7.5/10**.

---

## N) Performance / Scale Audit

Hot paths:

- `crm_contacts.html` and `crm_contact_detail.html` each fan out to 2–4 `/api/v1/*` calls.
- Analytics charts are async-fetched after page render — good for perceived perf.
- `crm_missed_leads_service.py` and `crm_realtime_inbox_service.py` summary endpoints
  recompute from base tables on each call. At 10k contacts they will become the bottleneck;
  add a materialized summary table or Redis cache before going wide.
- Web SSR uses async httpx — no blocking IO observed.

Performance score: **7/10** at expected initial scale (≤ 10k contacts).

Top fixes before VPS:

1. Cache `crm_missed_leads_service` summary for 30s.
2. Index `(status, priority, created_at)` on `crm_operator_handoff_requests` (verify).
3. Cache `analytics` chart payloads for 60s.
4. Add `LIMIT` defense to any `repo.list_*` that doesn't already have one.

---

## O) Deployment / VPS Readiness

- Dockerfile and `docker-compose*.yml` exist; not validated in this audit.
- `scripts/production_deploy_dry_run_check.py` is the canonical pre-deploy check
  (per doc 128).
- No backup drill is recorded in `docs/AI_AGENT_SYSTEM/`.
- No nginx + TLS recipe visible at top level.
- Health endpoint (`/healthz`) exists on the API.

VPS readiness: **5.5/10**. See [`134_PRE_DEPLOY_BLOCKERS_AND_STAGE1_DECISION.md`](134_PRE_DEPLOY_BLOCKERS_AND_STAGE1_DECISION.md).

---

## P) Business Value Audit

What this platform will do for Vashpotolok on Day 1:

- Capture every Telegram lead with name, phone (masked), district, area, design choice.
- Show the operator a daily missed-leads board.
- Surface hot leads instantly to the admin group.
- Run the price calculator deterministically.
- Hand off to a human operator with a queue + workload.
- Replay a contact's conversation.
- Keep a price-quote history per contact.
- Show daily/weekly analytics.

What it does **not** do yet:

- Send proactive AI follow-ups (intentionally OFF).
- Run real campaigns (intentionally OFF).
- Push real-time inbox events (polling only).
- Integrate Instagram traffic.
- Generate quotes from the web (calculator UI for operators).
- Export contacts to CSV from the UI.
- Show a single-page "what is happening right now" flag matrix.

Business value score: **7.5/10**.

---

## Final scoreboard

| Dim | Score |
|---|---|
| Architecture | 7.5 |
| AI agent | 7.4 |
| Bot | 7.6 |
| Web CRM | 7.0 |
| CRM workflow | 7.5 |
| Price system | 7.5 |
| Handoff | 7.5 |
| Security | 7.2 |
| Database | 7.5 |
| Config | 8.0 |
| Scheduler | 8.0 |
| Tests | 7.5 |
| Performance | 7.0 |
| Deploy readiness | 5.5 |
| Business value | 7.5 |
| **Overall** | **7.4** |

Verdict for Stage 1 LOG_ONLY: **CONDITIONAL GO** — see
[`134_PRE_DEPLOY_BLOCKERS_AND_STAGE1_DECISION.md`](134_PRE_DEPLOY_BLOCKERS_AND_STAGE1_DECISION.md).
