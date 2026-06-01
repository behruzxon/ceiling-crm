# 152 — Web Platform Agent Control Audit

> **Status banner (read before anything else)**
>
> - Deploy: NO
> - VPS: NO
> - Flags: NOT ENABLED
> - Live sender: NOT ENABLED
> - Campaign send: NOT ENABLED
> - Operator reply live send: NOT ENABLED
> - DB / migrations: NOT MODIFIED
> - Production token: NOT USED
> - Real OpenAI: NOT CALLED
> - This is an **AUDIT-ONLY** document. No code, schema, UI, or config was changed in the pass that produced it.

**Scope.** Audit of the **web platform** (`apps/web` SSR dashboard + `apps/api` REST backend) as the
control surface for the AI agent system after deployment. Answers: can the business *run, watch,
correct, and grow* the agent from the web — or is the agent still developer-controlled?

**Method.** Read-only inspection of `apps/web/main.py`, all templates under `apps/web/templates/`,
every route under `apps/api/routes/`, the agent/control/CRM services under `core/services/`,
`shared/config/settings.py`, `shared/constants/pricing.py`, `shared/constants/catalog.py`,
`apps/bot/ai/`, and docs `144`–`151`. Findings below are grounded in those files with paths.

---

## 0. Platform shape (the one fact that frames everything)

`apps/web` is a **server-side-rendered, read-mostly dashboard**. Every page is a `GET` handler in
`apps/web/main.py` that calls `api_get(...)` against `apps/api` (`apps/web/api_client.py`). The
Bearer token (`API_INTERNAL_TOKEN`) lives server-side and never reaches the browser. All *write*
power lives in `apps/api` POST endpoints, which the templates reach via inline `fetch()`.

Consequence: "can the web control the agent?" reduces to **"which `apps/api` POST endpoints exist,
are they wired into a template, and are they gated by a safe-default flag?"** The answer is uneven —
strong for **runtime flags / rollout**, near-zero for **content** (knowledge, price, catalog) and
**learning** (failed questions, shadow parity).

---

## 1. Scoring table (each area 0–10)

| # | Area | Score | One-line basis |
|---|------|-------|----------------|
| 1 | Agent Control Center | **8/10** | Rich read view + preview/apply/rollback + 6 rollout presets + audit log; gated by `agent_settings_mutation_enabled` (default OFF). Minor template bug (mutation/runtime always "OFF"). |
| 2 | CRM Contact Detail | **7/10** | Full conversation, AI-trace summary, 5-field readiness checklist, next-best-action, lead-risk, price calc, copy-only reply suggestions. Notes/tags/status writes work. |
| 3 | Knowledge Management | **1/10** | `apps/bot/ai/knowledge/uz.md` hardcoded, read at import time. No DB, no UI, no versioning. Editing requires code deploy + bot restart. Two divergent KB files. |
| 4 | Price Management | **2/10** | `shared/constants/pricing.py` hardcoded. District modifiers read from Redis but **no endpoint/UI to set them**. No web edit, no versioning, no audit. |
| 5 | Catalog Management | **1/10** | `shared/constants/catalog.py` + ~80 aliases hardcoded, built at import. No web edit, no click/ask tracking, no unresolved-request capture. |
| 6 | Failed Question Intelligence | **1/10** | OpenAI failures only `log.exception(...)`; no DB capture. Missed-leads API endpoints are **stubs returning empty**. No unknown-questions inbox. |
| 7 | Shadow / SDM Monitoring | **1/10** | Shadow decisions are **log-only** (`sales_dialogue_shadow_decision`), default OFF. No DB table, no API, no parity UI, no feedback loop. |
| 8 | Operator Workflow | **5/10** | Handoff queue take/assign/unassign/contacted/resolve/cancel are live POSTs wired to UI. Reply-send endpoint is a **stub** (`sender_not_configured`). Suggestions are copy-only. |
| 9 | Feature Flags / Safe Enablement | **8/10** | Full preview→confirm-token→apply→rollback, 6 staged presets, audit log, safe defaults; double-gated for live flags. Toggling needs `.env` opt-in first. |
| 10 | Analytics / KPIs | **5/10** | Dashboard + analytics pages render lead counts, conversion, funnel, 6 chart types. But objections/buyer-type/unknown-questions/bot-failure-rate are empty or missing; missed-leads stubbed. |
| 11 | Security / Privacy | **5/10** | Phone masking + token redaction solid; audit-log model exists; API token server-side only. But shared-password basic auth is the default; session-auth + RBAC + CSRF all default OFF. |
| 12 | Post-deploy Upgrade Ability | **2/10** | Flags/rollout: yes. Knowledge/price/catalog/alias/FAQ: no — all need a code deploy + restart. |

**Weighted overall: ~3.8 / 10.** The platform is excellent at *operating the safety machinery* and
*reading one customer* and *weak* at the two things a growing business needs most: **editing what the
agent knows** and **learning from where it failed**.

---

## 2. Verdict

- **Can the web platform fully control the agent?** **PARTIAL.** It can control *runtime behaviour and
  rollout* (flags, presets, approvals, rollback) and *read* deeply. It **cannot** change *what the
  agent knows or charges or links to* — knowledge, prices, and catalog are all code.
- **Is it ready for production operations?** **PARTIAL / NO.** Security defaults are dev-grade (shared
  password, CSRF off, session-auth off), the Missed-Leads dashboard is wired to **stub** endpoints,
  and there is no failed-question visibility. Operators can manage the handoff queue but **cannot send**.
- **Is it only developer-controlled today?** For **content and learning: effectively YES** — every
  knowledge/price/catalog/alias/FAQ change is a developer code deploy. For **runtime flags: NO** —
  an admin with the mutation flag enabled can drive rollout from the UI.
- **Biggest missing piece:** there is **no feedback loop**. The agent cannot be *taught* from the web.
  Two halves are both absent: (a) **capture** — failed/unknown questions and shadow decisions are never
  persisted; (b) **edit** — knowledge/price/catalog are not editable. Until both exist, every
  improvement is a code change, and the rich shadow/log-only machinery produces data no one can see.

---

## 3. Area-by-area findings

### A) Agent Control Center — 8/10
- **Reads (`agent.html`, `/agent` route `apps/web/main.py:153`):** status pill (ENGINE OFF / LOG_ONLY /
  SAFE / LIVE), last-decision card (id, ts, intent, execution_mode, safety_flags — whitelisted by
  `core/services/agent_control_center_service.py`), rollout-stage timeline (OFF→LOG_ONLY→DRY_RUN→CANARY
  →APPROVAL→LIVE_SEND), KPI grid, follow-up/safety panels, pending-execution queue, Stage-1 observation
  + DRY_RUN gate (JS-loaded).
- **Writes (gated, wired into the template):** `POST /api/v1/admin/agent/settings/preview` → `/apply`
  (confirmation token), `/rollback`, `/presets/{preset}/preview|apply`, `/executions/{id}/approve|reject`
  (`apps/api/routes/admin_agent_settings.py`, `admin_agent_metrics.py`). All require
  `agent_settings_mutation_enabled` / `agent_execution_api_approval_enabled` (both default **False**).
- **`build_agent_control_summary`** safely exposes `engine_on`, `log_only`, `live_send_safe`,
  `status_pill_*`, `safe_text`, and a key-whitelisted `last_decision` — no prompts/tokens leak.
- **Gap:** `agent.html` reads `cc.get("mutation_enabled")` / `cc.get("runtime_enabled")` from the
  control-status snapshot, which does not contain those keys → both always display "OFF". Cosmetic
  but misleading. **Recommendation: keep write paths read-only-by-default in prod for now;** the
  preview/confirm/rollback design is sound and is the right long-term control plane.

### B) CRM Contact Detail / Conversation Control — 7/10
- **Full conversation** rendered with inbound/bot/operator badges (`crm_contact_detail.html:74`),
  sourced from `GET /contacts/{id}/messages`.
- **AI-trace summary** card: last_intent, last_price_estimate, handoff_requested, last_objection,
  safety_status (only when Stage-1 LOG_ONLY on). Not a full reasoning trace.
- **Readiness checklist** (`:138`): phone, area m², district, ceiling type, lead status → `n/5`.
- **Next-best-action** (`crm_next_best_action_service.py`) and **lead-risk** (`lead_risk_service.py`)
  are pure deterministic functions (no AI, no DB write) → safe to render inline.
- **Writes that work:** add note, add/remove tag, `PATCH` status/temperature.
- **CRITICAL — operator reply send is a stub:** `POST /contacts/{id}/reply/send`
  (`apps/api/routes/admin_crm.py`) validates via `CRMOperatorReplyService.preview_reply` then
  **unconditionally returns `{"status": "sender_not_configured"}`** — the template expects `'sent'`,
  so a real send can never succeed today. Operator reply suggestions are **copy-to-clipboard only**.
- **Missing before send-from-web:** real Telegram send wiring, CSRF (off), rate limit (none),
  per-role permission, and an audit-log write on send.

### C) Knowledge Management — 1/10
- `apps/bot/ai/system_prompt.py` does `_KB_PATH.read_text(...)` **at import**; KB is baked into the
  system prompt string. No loader service, no DB, no Redis fallback.
- **Not editable from web.** No knowledge/FAQ endpoint, table, or UI.
- **No versioning, approval, or rollback** (git only). Any change = code deploy + **bot restart**.
- Knowledge is informally sectioned inside one markdown file (company, operators, prices, FAQ,
  objections, prohibited phrases, room recs, escalation, payment) but **not** modeled as separate
  editable categories (FAQ / pricing / catalog / objections / policy / warranty / location).
- **Data risk:** two divergent KB files — `apps/bot/ai/knowledge/uz.md` (used by bot) vs
  `shared/knowledge/uz.md` (used by tests) carry **different prices**. Tests can pass while the bot
  quotes different numbers.

### D) Price Management — 2/10
- `shared/constants/pricing.py` hardcodes: `DEFAULT_BASE_PRICES` (internal quotes),
  `DESIGN_PRICES_CUSTOMER` (customer-facing), `ADDON_PRICES`, `DISCOUNT_TIERS` ((40→10%),(20→5%)).
- `PricingService.get_base_price` checks Redis `price:{cat}` then falls back to constants;
  `get_district_modifier` reads Redis `district_mod:{district}` (default 1.00) — **but no API/UI
  writes either Redis key.**
- **Not editable from web.** No price-settings endpoint. No preview, no history of *config* changes,
  no audit. (Per-customer estimate *history* exists via `crm_price_estimate_history_service`, which is
  a different thing.) Base/customer/addon/discount edits all need code deploy + restart.

### E) Catalog Management — 1/10
- `shared/constants/catalog.py` hardcodes 10 `CatalogSection`s with Telegram folder URLs;
  `catalog_link_resolver_service.py` hardcodes ~80 aliases + ambiguous/generic triggers, all built
  into module-level indexes at import.
- **Not editable from web.** No way to add a design, change a link, or add an alias for messy input
  without a code deploy + restart. **No tracking** of which links are clicked/asked or which catalog
  requests went unresolved.

### F) Failed / Unanswered Question Intelligence — 1/10
- Successful AI exchanges persist to `ai_conversations` (rolling window + summary). **Failures do not
  persist** — `_call_ai` failure path only `log.exception("ai_call_failed")` and shows a failsafe text.
- **No table** for unanswered/low-confidence/fallback questions. No "I don't know" capture.
- **Missed-Leads dashboard is wired to stubs:** `apps/api/routes/admin_crm_missed_leads.py` — `summary`
  calls `build_summary([])` (all zeros), list returns `{"items": [], "count": 0}`. The page renders but
  shows nothing real.
- **No unknown-questions inbox**, no convert-to-FAQ flow. Missing model:
  `unanswered_questions(id, user_id, question_text, intent_detected, confidence, fallback_reason,
  created_at, reviewed_by, status, promoted_faq_id)`.

### G) Shadow / SDM Monitoring — 1/10
- `apps/bot/handlers/private/sales_dialogue_shadow.py` emits a structured `sales_dialogue_shadow_decision`
  **log line** (sdm_intent, sdm_next_action, sdm_confidence, order_readiness_score, missing_fields,
  live_route per doc 148) — **log-only, default OFF**, never persisted.
- **No DB table, no API route, no web view.** Admin cannot compare live-vs-SDM route, see mismatches,
  readiness, suggested question, confidence; cannot filter or mark correct/wrong; **no feedback loop.**
- Docs 146–151 describe the shadow architecture and oracle alignment but the *visualization* layer
  does not exist. Missing: `sdm_shadow_decisions` table + parity API + `/crm/sdm-parity` page.

### H) Operator Workflow — 5/10
- **Handoff queue works:** `crm_handoffs.html` buttons → `POST /handoffs/{id}/{take|assign|unassign|
  contacted|resolve|cancel}` (`admin_crm_handoffs.py`) mutate status and reload. Operator sees
  phone/district/readiness on the contact page.
- **Cannot send to customer from web** (reply-send stub, see §B). Suggestions are copy-only.
- `approved_execution_sender_service` *can* `bot.send_message` to customers for approved agent
  executions, but it is driven by the execution queue/scheduler — **not** wired to the operator-reply
  endpoint.
- **Safety gaps for send-from-web:** CSRF off by default, no rate limit, no per-role check, no send
  audit entry. **Recommendation: keep send-from-web disabled until session auth + CSRF are enabled.**

### I) Feature Flags / Safe Enablement — 8/10
- ~50 agent flags in `shared/config/settings.py`. **All dangerous defaults are safe:**
  `agent_execution_live_sender_enabled=False`, `agent_execution_auto_execute_approved=False`,
  `agent_settings_allow_live_flags=False`, `agent_response_orchestrator_log_only=True`,
  `agent_decision_log_only=True`, `agent_execution_mode="log_only"`,
  `sales_dialogue_manager_enabled=False`, `sales_dialogue_manager_shadow_enabled=False`.
- Toggling from web requires `agent_settings_mutation_enabled=true` (set via `.env` only); live flags
  are *double-gated* by `agent_settings_allow_live_flags`. Preview shows risk + blockers; apply needs a
  confirmation token; rollback reverts individual settings; 6 presets give staged rollout.
- **Recommendation:** flags should remain `.env`-bootstrapped for the *mutation* master switch, with
  per-flag tuning from the web — the current design already matches this. Add a plain-language
  "what happens if I enable this" panel per flag.

### J) Analytics / KPIs — 5/10
- Dashboard (`/api/v1/analytics` → `build_sales_analytics`, **DB-only**) + analytics page render: total/
  active/won/lost leads, conversion rate, score distribution, source performance, 8-stage funnel.
- Chart endpoint (`admin_crm_analytics_charts.py`) gives 6 series: temperature, intent breakdown,
  missed-lead severity, handoff status, top districts, top ceiling types.
- **Empty or missing** (the analytics endpoint explicitly skips Redis enrichment): top objections,
  buyer-type stats, conversation health, autopilot effectiveness, **top unknown questions**,
  **bot failure rate**. Missed-lead KPIs render from **stub** data.
- **Add first:** bot failure/fallback rate, unknown-questions top-N, objection mix — i.e. the metrics
  that tell the owner *where the agent is losing customers*.

### K) Security / Privacy / Audit — 5/10
- **Auth:** default is **shared-password HTTP basic** (`apps/web/auth.py`, constant-time compare,
  fail-closed in prod). Per-user **session auth** (`admin_auth_routes.py`, cookie `vp_admin_session`)
  and **RBAC** (`admin_rbac_service.py`: owner/admin/operator/analyst/viewer) exist but **default OFF**.
- **CSRF** (`csrf_middleware.py`) is wired but **default OFF** (`admin_csrf_enabled`). All current
  write POSTs (handoff actions, notes, tags, status) run **without CSRF** in default config.
- **API auth:** every route depends on `require_api_token` (Bearer); token is server-side only.
- **Privacy strengths:** phone masking (`shared/utils/phone.py`, `+998****67`) at notification/log/
  replay boundaries; token + bot-token redaction across audit/security services; audit-log model
  (`admin_audit_log_service.py`) covers ~41 action types with sanitization.
- **Blockers for prod:** (1) move off shared password to session-auth + RBAC; (2) enable CSRF;
  (3) add login rate-limiting/lockout enforcement; (4) ensure every web *write* writes an audit entry.

### L) Deployment / Post-deploy Upgrade Workflow — 2/10
| After deploy, admin wants to… | Possible from web today? | What it needs |
|---|---|---|
| Add a new FAQ | ❌ No | Knowledge table + CRUD API + UI + hot-reload |
| Change a price | ❌ No (Redis writable, no endpoint) | Price-settings table/endpoint + UI + audit |
| Update a catalog link | ❌ No | Catalog table + CRUD API + UI |
| Add a design alias | ❌ No | Alias table + CRUD API + resolver DB-load |
| Fix an unknown question | ❌ No | Unknown-questions capture + inbox + promote-to-FAQ |
| See a failed answer | ❌ No (logs only) | Capture-to-DB + viewer |
| Enable shadow | ⚠️ `.env` only | (acceptable for now) |
| Collect parity data | ❌ No | Shadow decisions table + ingestion |
| Promote SDM to live for a flow | ⚠️ flag only, all-or-nothing | Per-flow rollout flags + parity gate |
| Tune a runtime flag | ✅ Yes (if mutation enabled) | already built |

---

## 4. Top 30 missing features

Priority key: **P0** = blocks safe business operation / highest ROI · **P1** = needed soon ·
**P2** = valuable · **P3** = nice-to-have. "Risk" = risk of the *change itself*.

### 1. Unknown-questions capture (bot → DB)
- **Priority:** P0 · **Why:** today every failed/low-confidence answer is lost to logs; this is the
  raw material for all agent improvement. · **Files:** new model `unanswered_questions`, migration,
  `apps/bot/handlers/private/ai_support.py`/`ai_openai.py` fallback path, repo. · **Risk:** low (additive
  write, no customer impact). · **Order:** 1.

### 2. Unknown-questions inbox (web view)
- **Priority:** P0 · **Why:** lets admin *see* what the bot can't answer and triage it. · **Files:**
  `apps/api/routes/admin_unknown_questions.py`, `apps/web/templates/crm_unknown_questions.html`,
  `apps/web/main.py`. · **Risk:** low (read-only). · **Order:** 2.

### 3. Promote-unknown-question → FAQ
- **Priority:** P0 · **Why:** closes the loop from "bot failed" to "bot learns". · **Files:** knowledge
  table, `admin_unknown_questions.py` (promote action), inbox UI. · **Risk:** medium (changes bot
  knowledge). · **Order:** after #5.

### 4. Knowledge base table + loader (DB-backed, hot-reload)
- **Priority:** P0 · **Why:** removes the "every wording fix is a deploy + restart" tax; foundation
  for §3-K. · **Files:** new `knowledge_blocks` model + migration, `apps/bot/ai/system_prompt.py`
  loader (Redis-cached, file fallback). · **Risk:** medium (touches live prompt). · **Order:** 3.

### 5. Knowledge base CRUD API + UI
- **Priority:** P0 · **Why:** non-dev staff can edit FAQ/objections/policy without code. · **Files:**
  `admin_knowledge.py` route, `knowledge.html` template. · **Risk:** medium. · **Order:** 4.

### 6. Knowledge versioning + rollback
- **Priority:** P1 · **Why:** a bad knowledge edit must be revertible like flags are. · **Files:**
  `knowledge_versions` table, diff/restore endpoints. · **Risk:** low. · **Order:** after #5.

### 7. Knowledge approval workflow (draft → review → live)
- **Priority:** P1 · **Why:** prevents un-reviewed copy reaching customers. · **Files:** status column,
  approval endpoint, RBAC `knowledge.approve`. · **Risk:** low. · **Order:** after #6.

### 8. Price-settings table + admin endpoint
- **Priority:** P0 · **Why:** prices change seasonally; today that's a deploy. Redis is already read —
  add the write path + persistence. · **Files:** `price_settings` model, `admin_pricing.py`,
  `pricing_service` read-from-DB. · **Risk:** medium (affects quotes). · **Order:** 5.

### 9. Price-settings UI with preview + history
- **Priority:** P1 · **Why:** safe price edits with before/after preview and audit. · **Files:**
  `pricing.html`, history table. · **Risk:** medium. · **Order:** after #8.

### 10. District modifier manager
- **Priority:** P2 · **Why:** `district_mod:{x}` is read but unmanageable today. · **Files:**
  `admin_pricing.py`, UI. · **Risk:** low. · **Order:** with #9.

### 11. Catalog link manager (DB-backed catalog)
- **Priority:** P1 · **Why:** add a design / fix a Telegram link without a deploy. · **Files:**
  `catalog_sections` model, `admin_catalog.py`, resolver DB-load. · **Risk:** medium. · **Order:** 6.

### 12. Alias / synonym manager
- **Priority:** P1 · **Why:** messy customer input changes constantly; aliases shouldn't be code.
  · **Files:** `catalog_aliases` model, resolver index rebuild, UI. · **Risk:** medium. · **Order:** with #11.

### 13. Unresolved catalog request capture
- **Priority:** P2 · **Why:** shows which design terms the resolver missed → new aliases. · **Files:**
  resolver instrumentation, `catalog_misses` table, analytics tile. · **Risk:** low. · **Order:** after #12.

### 14. Shadow decisions persisted to DB
- **Priority:** P1 · **Why:** the SDM parity data exists only in logs; persist to evaluate promotion.
  · **Files:** `sdm_shadow_decisions` model, shadow handler write. · **Risk:** low (log-only stays
  log-only behaviourally; just also store). · **Order:** 7.

### 15. Live-vs-SDM parity dashboard
- **Priority:** P1 · **Why:** decide if SDM is ready to go customer-facing, per flow. · **Files:**
  `admin_sdm_parity.py`, `crm_sdm_parity.html`. · **Risk:** low (read-only). · **Order:** after #14.

### 16. SDM decision feedback (correct/wrong) loop
- **Priority:** P2 · **Why:** human labels turn parity data into a training signal. · **Files:**
  feedback column + endpoint, parity UI. · **Risk:** low. · **Order:** after #15.

### 17. Operator send-from-web (real Telegram send)
- **Priority:** P1 · **Why:** the reply UI exists but is a stub; operators must be able to answer.
  · **Files:** `admin_crm.py` reply/send wiring → send service, message record. · **Risk:** **high**
  (real customer messages). · **Order:** *after* security #21–#23.

### 18. Bot failure / fallback-rate KPI
- **Priority:** P0 · **Why:** the owner currently can't see how often the agent fails. · **Files:**
  depends on #1 capture; analytics endpoint + dashboard tile. · **Risk:** low. · **Order:** after #1.

### 19. Top-objections & top-unknown-questions analytics tiles
- **Priority:** P1 · **Why:** the analytics endpoint skips Redis-derived objection data; surface it.
  · **Files:** analytics enrichment, dashboard. · **Risk:** low. · **Order:** after #2.

### 20. Wire Missed-Leads endpoints to real queries
- **Priority:** P0 · **Why:** the dashboard is shipped but backed by **stub** data (returns empty).
  · **Files:** `admin_crm_missed_leads.py` (replace stubs with repo queries). · **Risk:** low. · **Order:** 8.

### 21. Session auth as default (retire shared password)
- **Priority:** P0 · **Why:** shared password is dev-grade; blocks prod. · **Files:**
  `admin_auth_routes.py`, settings default, `auth.py`. · **Risk:** medium (login flow change). · **Order:** 9.

### 22. Enable CSRF on all write forms
- **Priority:** P0 · **Why:** all current write POSTs run without CSRF. · **Files:** `csrf_middleware.py`
  default, templates add token header. · **Risk:** medium. · **Order:** with #21.

### 23. RBAC enforcement on web routes
- **Priority:** P0 · **Why:** operator vs admin vs analyst must differ before send/flags ship.
  · **Files:** RBAC checks in routes, settings. · **Risk:** medium. · **Order:** with #21.

### 24. Audit-log write on every web write action
- **Priority:** P1 · **Why:** handoff/notes/status/flag changes must be attributable. · **Files:**
  route handlers → `admin_audit_log_service`. · **Risk:** low. · **Order:** after #23.

### 25. Login rate-limit / lockout enforcement
- **Priority:** P1 · **Why:** failed-attempt tracking exists but enforcement isn't wired. · **Files:**
  `admin_auth_service`, auth path. · **Risk:** low. · **Order:** after #21.

### 26. Per-flag "what happens if I enable this" explainer
- **Priority:** P2 · **Why:** safe enablement needs plain-language consequences in the UI. · **Files:**
  preset/settings service metadata, `agent.html`. · **Risk:** low. · **Order:** after security.

### 27. Fix agent.html mutation/runtime status display bug
- **Priority:** P2 · **Why:** currently always shows "OFF" (keys absent from snapshot) → misleads ops.
  · **Files:** `agent.html` or control-status snapshot. · **Risk:** low. · **Order:** any.

### 28. Reconcile the two divergent knowledge files
- **Priority:** P1 · **Why:** bot and tests read different prices → tests can pass while bot is wrong.
  · **Files:** consolidate `shared/knowledge/uz.md` vs `apps/bot/ai/knowledge/uz.md`. · **Risk:** low. · **Order:** before #4.

### 29. Per-flow SDM promotion flags + parity gate
- **Priority:** P2 · **Why:** SDM is all-or-nothing today; promotion should be gated by parity per flow.
  · **Files:** settings, orchestrator, parity check. · **Risk:** medium. · **Order:** after #15.

### 30. Agent training queue (review → approve → apply learning)
- **Priority:** P3 · **Why:** unify unknown-questions + shadow feedback + knowledge edits into one
  reviewer workflow. · **Files:** `training_queue` model, queue UI. · **Risk:** medium. · **Order:** last.

---

## 5. Agent upgrade system — roadmap

How to let admins improve the agent **after deployment**, in dependency order:

1. **Unknown Questions Inbox** — capture (bot→DB) + read-only triage view (#1, #2, #18, #20).
   *The diagnostic layer: see where the agent fails before changing anything.*
2. **Knowledge Base CRUD** — DB-backed knowledge + loader + edit UI (#4, #5, #28).
   *The first real "teach the agent from the web" capability.*
3. **Failed Answer Review → promote to FAQ** — connect inbox to knowledge (#3).
4. **Price Settings UI** — DB-backed prices, preview, history (#8, #9, #10).
5. **Catalog Link Manager + Alias/Synonym Manager** — DB-backed catalog (#11, #12, #13).
6. **Shadow Decision Viewer + Live-vs-SDM Parity Dashboard** — persist + visualize (#14, #15, #16).
7. **Admin Approval Workflow + Knowledge Versioning + Rollback** — make every edit reviewable and
   revertible, the way flags already are (#6, #7).
8. **Agent Training Queue** — one reviewer surface unifying all of the above (#30).

Design principle throughout: mirror the **flag control plane** that already works well —
*preview → confirm → apply → audit → rollback* — for knowledge, price, and catalog too.

---

## 6. What the agent still cannot learn from the web today (be honest)

- **It cannot learn a single new fact.** Knowledge is a markdown file read at import; the web can't
  touch it.
- **It cannot remember a question it failed to answer.** OpenAI failures are `log.exception` only;
  nothing is stored, so nothing can be reviewed or turned into an FAQ.
- **It cannot have its prices corrected from the web.** Prices are Python constants; the one dynamic
  hook (Redis district modifier) has no writer.
- **It cannot gain a catalog link or an alias from the web.** Both are hardcoded and indexed at import.
- **It cannot show anyone its shadow reasoning.** SDM parity data is real but lives only in log lines —
  no table, no screen, no feedback button.
- **The Missed-Leads dashboard teaches nothing** — it is backed by stub endpoints returning empty data.
- **Net:** the web can *operate and observe* the agent, and *tune its runtime flags*, but it cannot yet
  *grow the agent's brain*. Every brain change is still a developer deploy + bot restart.

---

## 7. Recommended next sprint (exactly one, highest ROI)

### → **Unknown Questions Inbox** (capture + read-only triage)

**Why this and not the others:**
- **vs. Knowledge Base CRUD:** CRUD lets you edit, but without capture you're editing *blind* — you
  don't know *what* is failing. The inbox makes the next CRUD sprint *targeted* instead of guesswork.
  Inbox is also lower-risk (read-only on web; additive write in bot) and is a prerequisite for the
  failed-answer→FAQ loop.
- **vs. Shadow Decision Viewer:** valuable, but SDM is still not customer-facing and shadow data only
  helps a developer decide on SDM promotion — it doesn't directly recover lost customers. Lower
  business ROI right now.
- **vs. Operator Send-from-Web:** highest *risk* (real customer messages) and **blocked** on security
  (CSRF off, shared password, no rate limit). Must not ship before §3-K security work.

**Sprint scope (safe, no flags, no sends, no deploy):**
1. Migration + `unanswered_questions` model.
2. Capture hook on the AI fallback path (`ai_support.py` / `ai_openai.py`) — write on failure /
   low-confidence / generic fallback. Phone-masked, token-redacted, no PII leak.
3. Read-only API `GET /api/v1/admin/crm/unknown-questions` (+ summary) and a
   `crm_unknown_questions.html` page (filters: severity, intent, reviewed/unreviewed).
4. A **bot-failure-rate** tile on the dashboard fed by the same capture.
5. Tests: capture-path unit test, route test, redaction test.

This unlocks: bot-failure-rate KPI (#18), top-unknown-questions analytics (#19), and the
promote-to-FAQ loop (#3) once Knowledge CRUD lands. It is the single change that turns the agent from
*un-improvable-from-web* into *measurable-and-improvable*.

---

## 8. Cross-references

- Routing/torture status: `144_ENTERPRISE_BOT_TORTURE_TEST_10000.md`, `151_TORTURE_ORACLE_ALIGNMENT.md`.
- SDM shadow: `146_SALES_DIALOGUE_MANAGER_SHADOW_INTEGRATION.md`,
  `147_LIVE_FLOW_SHADOW_FINDINGS_FIX.md`, `148_REPORT144_DETECTOR_GAPS_AND_ROUTE_LABELS.md`.
- Security rollout: `69_SECURITY_ENABLEMENT_PLAN.md`, `70_SECURITY_PREFLIGHT_RUNBOOK.md`,
  `71_SECURITY_ROLLBACK_CARD.md`.
- Prior platform audits: `81_PLATFORM_READINESS_AUDIT.md`,
  `131_FULL_CODEBASE_AI_WEB_PLATFORM_AUDIT.md`, `134_PRE_DEPLOY_BLOCKERS_AND_STAGE1_DECISION.md`.

*End of audit. No code, schema, UI, flag, or deployment was changed to produce this document.*
