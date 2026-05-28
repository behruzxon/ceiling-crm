> Status: AUDIT REPORT. Deploy: NO. VPS: NO. Flags: NOT ENABLED. Stage 1: NOT APPLIED.
> Live sender: NOT ENABLED. Campaign send: NOT ENABLED. Operator reply live send: NOT ENABLED.

# 133 — Next 50 Improvements Roadmap

Ranked, phased, opinionated. Each item lists: *what, why, impact, risk, complexity, likely files,
tests needed, migration?, deploy?, before/after Stage 1?* Items are grouped into 11 phases
(Phase 0 first, then 1 → 10).

---

## Phase 0 — Must fix before any VPS / Stage 1

### 1. Wire CSRF middleware into the FastAPI web app

- Why: the service exists (`core/services/admin_csrf_service.py`) but no middleware mounts it;
  any web POST is unprotected.
- Impact: high. Closes the biggest pre-prod gap.
- Risk: low (defaults off; opt-in token).
- Complexity: S.
- Likely files: `apps/web/main.py`, `apps/web/templates/*.html` (token field).
- Tests: unit (token roundtrip), web POST integration.
- Migration: no.
- Deploy: no (local first).
- Before Stage 1.

### 2. Add architecture lint test: `apps/` must not import `infrastructure/` directly

- Why: enforces the layered contract that today is convention only.
- Impact: medium.
- Risk: low.
- Complexity: S.
- Likely files: `tests/unit/architecture/test_layer_isolation.py`.
- Tests: 1.
- Before Stage 1.

### 3. Regression test: `DEFAULT_BASE_PRICES` is never referenced by any bot handler

- Why: customer-facing handlers must use `DESIGN_PRICES_CUSTOMER`; today this is convention.
- Impact: high (price leak prevention).
- Risk: low.
- Complexity: S.
- Likely files: `tests/unit/safety/test_price_source_isolation.py`.
- Before Stage 1.

### 4. Replace browser `confirm()` for agent execution approve/reject with a typed modal

- Why: `confirm()` does not show the actual message. Operators may approve blind.
- Impact: high (the human gate is the safety story).
- Risk: low.
- Complexity: M.
- Likely files: `apps/web/templates/agent.html`.
- Tests: template render + cypress-style smoke (skip if no headless browser).
- Before Stage 1.

### 5. Mask phone numbers in *every* log line, not just AI memory

- Why: at least one repo writes a raw phone to logs (`_notify_admin` path); search and seal.
- Impact: high (privacy).
- Risk: low.
- Complexity: S.
- Likely files: `shared/utils/sanitize.py`, `core/services/notification_service.py`.
- Tests: log capture, assert no 9-12 digit run.
- Before Stage 1.

### 6. Document the rollback for every Stage transition

- Why: doc 128 covers production deploy rollback; not every flag flip has one.
- Impact: medium.
- Risk: low.
- Complexity: S.
- Files: `docs/AI_AGENT_SYSTEM/134_PRE_DEPLOY_BLOCKERS_AND_STAGE1_DECISION.md` (this pack).
- Before Stage 1.

### 7. Confirm a real `pg_dump` / `pg_restore` drill on a copy of production data

- Why: backup is the last line of defense; doc 128 lists the steps but no record of a real run.
- Impact: critical.
- Risk: low (drill on copy).
- Complexity: M.
- Before Stage 1.

### 8. Run `scripts/production_deploy_dry_run_check.py` and attach JSON output to runbook

- Why: doc 129 lists the command; no recorded JSON in the repo.
- Impact: medium.
- Risk: none.
- Complexity: S.
- Before Stage 1.

---

## Phase 1 — Finish local platform polish

### 9. Add a FSM-state timeout job

- Why: users stuck in `waiting_for_phone` forever.
- Impact: medium.
- Risk: low.
- Complexity: M.
- Files: `apps/scheduler/jobs/fsm_timeout_jobs.py` (new), `apps/bot/middlewares/`.
- Tests: scheduler integration.

### 10. Make districts data-driven

- Why: today hardcoded keyboard; add a DB table.
- Impact: small per change, frequent over time.
- Complexity: M.
- Migration: yes.

### 11. Make packages data-driven

- Why: 3 hardcoded packages; ops will want to add a fourth.
- Complexity: M.
- Migration: yes.

### 12. Single-source phone normalization in `shared/utils/phone.py`

- Why: duplicated in `lead_capture.py` and `measurement_lead.py`.
- Complexity: S.
- Tests: unit.

### 13. Remove `AppointmentStates` and `CatalogStates.waiting_for_design` (dead code)

- Why: dead FSM confuses contributors.
- Complexity: S.

### 14. Add a manual price calculator UI on the contact-detail page

- Why: operators want to generate a quote inside the CRM.
- Impact: high (operator productivity).
- Complexity: M.

### 15. Add CSV export of contacts on `/crm`

- Why: ops staple.
- Complexity: S.

### 16. Add bulk operations on the contacts page (tag/status)

- Why: ops staple.
- Complexity: M.

### 17. Add a "what is happening right now" flag-matrix tile on `/admin/security`

- Why: today the runtime values are inferred from many services.
- Complexity: M.

### 18. Add an index page listing all docs under `docs/AI_AGENT_SYSTEM/`

- Why: 130+ docs and no index.
- Complexity: S.

---

## Phase 2 — Stage 1 LOG_ONLY observation

### 19. Build a 30-minute observation harness

- Why: stage 1 needs structured logging into observation reports.
- Complexity: M.
- Files: `core/services/stage1_observation_report_service.py` already exists; wire a scheduler.

### 20. Pre-Stage-1 dry-run check published as a CI artifact

- Why: every PR should attach the dry-run JSON.
- Complexity: M.
- CI: yes.

### 21. Stage 1 daily summary delivered to admin DM

- Why: avoid hand-running the report.
- Complexity: S.
- Default off — opt-in.

### 22. Add a "no agent send happened today" canary alert

- Why: positive control that the gate is doing what it should.
- Complexity: S.

---

## Phase 3 — Operator workflow hardening

### 23. SLA timer per handoff

- Why: today no clock; we cannot prove "operator answered within X minutes".
- Impact: high.
- Complexity: M.
- Migration: yes.

### 24. Auto-escalate handoff to the next operator if SLA broken

- Why: complements 23.
- Complexity: M.

### 25. Wire operator reply send (after security gate)

- Why: today disabled; service exists.
- Risk: high (real sends).
- Complexity: M.
- Must come *after* CSRF + RBAC.

### 26. CRUD operator notes / tags from the contact-detail page

- Why: today read-only.
- Complexity: M.

### 27. Add "assigned operator presence" indicator

- Why: hot lead routed to offline operator wastes time.
- Complexity: M.

### 28. Daily operator NPS prompt (1-tap thumbs)

- Why: needed to evaluate live-send readiness.
- Complexity: S.

---

## Phase 4 — Agent stronger intelligence

### 29. Add `handoff_queue_size`, `operator_online`, `prior_orders` to agent memory context

- Why: see doc 132 § 5.
- Complexity: M.

### 30. Add "next best action" surfacing on the contact-detail page

- Why: `next_best_action_service.py` exists; never rendered.
- Complexity: M.

### 31. Add "deal probability" + "buyer type" + "revenue estimate" to the contact-detail page

- Why: these services already compute; surface them.
- Complexity: S.

### 32. Add structured-output schema validation for every LLM reply

- Why: defense-in-depth against unparseable JSON.
- Complexity: M.

### 33. Add fuzz tests for prompt injection in `tests/unit/safety/`

- Why: today we have 14 patterns; we don't test the long tail.
- Complexity: M.

### 34. Add a memory-TTL job pruning `AiMemoryModel` older than 60 days

- Why: storage hygiene.
- Complexity: S.

---

## Phase 5 — Customer experience upgrades

### 35. Add Russian translation layer

- Why: market is dual-language.
- Complexity: L.

### 36. Add "send me a sample photo" intent + media bot reply

- Why: ceiling design is visual; words are weak.
- Complexity: M.

### 37. Add voice-note transcription (premium, later)

- Why: real Uzbek users send voice notes constantly.
- Complexity: L.

### 38. Add measurement-booking calendar (not free-text time)

- Why: 70% of leads end up rebooking; calendar reduces back-and-forth.
- Complexity: M.

---

## Phase 6 — Analytics / owner dashboard upgrades

### 39. Add a "deals closed today" tile to the dashboard

- Why: owner wants one number.
- Complexity: S.

### 40. Add a "cost per lead" tile

- Why: needs an ad-spend input.
- Complexity: M.

### 41. Add a "revenue forecast" panel using `revenue_predictor_service.py`

- Why: service exists; never rendered to the owner.
- Complexity: M.

### 42. Add a weekly PDF report emailed (or Telegram-DM'd) to the owner

- Why: cadence beats dashboards.
- Complexity: M.

---

## Phase 7 — Safe live-send preparation

### 43. Per-send audit log row separate from the queue row

- Why: queue row tracks proposal; sends must be reconstructable independently.
- Complexity: M.
- Migration: yes.

### 44. One-button agent kill switch (admin command)

- Why: a real emergency stop visible from Telegram.
- Complexity: S.

### 45. Per-user-per-day send counter exposed on `/admin/security`

- Why: today the cap exists in code, not in any UI.
- Complexity: S.

### 46. 24-hour rolling agent reputation score with circuit breaker

- Why: pre-Level-5 requirement.
- Complexity: L.

---

## Phase 8 — Premium AI features

### 47. Catalog/photo understanding (multimodal)

- Why: "this design like the third row, left photo" intent.
- Complexity: L.
- After Stage 1.

### 48. Operator-side AI assist ("suggest a reply")

- Why: speed up human operators with AI assist that requires a human tap to send.
- Complexity: M.
- After Stage 1.

### 49. Lead lost-risk detector

- Why: predict before the user goes cold.
- Complexity: M.

### 50. Outcome learning loop

- Why: `tactic_outcome_logger.py` exists; feed-back loop not yet closed.
- Complexity: L.

---

## Phase 9 — Production security hardening

(Same items as Phase 0 #1 + extensions: WAF rules, IP allowlist enforcement, dual sign-off on
live-send flag, security review of every web POST, dependency upgrade cadence.)

---

## Phase 10 — Scale / performance hardening

- Materialize `crm_missed_leads` summary.
- Cache analytics chart payloads for 60 seconds.
- Index review on `(status, created_at)` columns.
- Move FSM Redis to a dedicated logical DB if not already (it is — db2).
- Move bot security middleware burst state to Redis (multi-pod safe).

---

## How to use this roadmap

Phase 0 items are pre-conditions for Stage 1.
Phase 1 items are nice-to-haves for the local platform polish before VPS.
Phase 2 items happen *during* Stage 1.
Phase 3+ items happen *after* Stage 1 passes, in roughly this order.

For each item, the recommended next step is *not* "implement it now". The next step is "open a
short design doc under `docs/AI_AGENT_SYSTEM/` referencing this roadmap line by number". Then
implement.
