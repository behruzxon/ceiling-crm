# 125 — Stage 1 LOG_ONLY Readiness Review (after Fresh Start Steps 1–9)

Read-only review. No production code changed by this step. Stage 1 is
**NOT APPLIED**, deploy is **NO**, VPS is **NO**, flags are **NOT ENABLED**.

## Current main commit

- Branch: `main`
- HEAD: `4e34024 feat(crm): add handoff auto-expire job`
- Working tree: clean
- PR #1 (vash-ai-hardening-session) merged.

## Completed Fresh Start steps

| # | Step | Doc |
|---|------|-----|
| 1 | Project Map | 115_FRESH_START_PROJECT_MAP.md |
| 2 | Handoff Queue API + Web Page | (covered in handoff feature docs) |
| 3 | AI Trace Viewer (contact detail) | — |
| 4 | Missed Leads Dashboard | — |
| 5 | Analytics Charts | — |
| 6 | Conversation Replay (contact detail) | 120_CONVERSATION_REPLAY.md |
| 7 | Price Estimate History (contact detail) | 122_PRICE_ESTIMATE_HISTORY.md |
| 8 | Operator Assignment UI | 123_OPERATOR_ASSIGNMENT_UI.md |
| 9 | Handoff Auto-Expire Job | 124_HANDOFF_AUTO_EXPIRE_JOB.md |

All nine steps merged. No outstanding work blocks readiness from
Steps 1–9.

## Web / CRM feature map

| Surface | Path | Status |
|---------|------|--------|
| Handoff Queue | `/crm/handoffs` | ✅ live, expired filter added in Step 9 |
| Missed Leads | `/crm/missed-leads` | ✅ live |
| Analytics Charts | `/analytics` | ✅ live (CSS-only charts, API data) |
| Contact Detail — Conversation Replay | `/crm/{id}` | ✅ live |
| Contact Detail — Price Estimate History | `/crm/{id}` | ✅ live |
| Contact Detail — AI Trace Viewer | `/crm/{id}` | ✅ live |
| Operator Workload + Assign / Take / Unassign | `/crm/handoffs` + `/api/v1/admin/crm/handoffs/operators/summary` | ✅ live |

All surfaces are read-only or operator-only and do **not** send anything
to end users. They render data from the existing tables.

## No-send safety verdict

- Web layer: no Telegram / OpenAI imports in new code.
- Handoff API endpoints: status-mutation only (assigned / contacted /
  resolved / cancelled / expired). No outbound messages.
- Handoff auto-expire job: imports only SQLAlchemy + service; module
  asserts (via tests) that `aiogram`, `openai`, and `send_message` are
  absent.
- AI Trace Viewer / Conversation Replay / Price Estimate History: pure
  reads. No external calls.

Verdict: **SAFE.** No new code path sends a Telegram message or calls
OpenAI in the user direction.

## Scheduler safety verdict

- New job `crm_handoff_auto_expire` registered, interval 15 min.
- Disabled by default — `CRM_OPERATOR_HANDOFF_AUTO_EXPIRE_ENABLED=false`.
- When disabled the job opens no DB session and dispatches nothing.
- All errors caught at every layer (config / session / service / query /
  commit). Job can never crash the scheduler.
- No other scheduler changes from Steps 1–9.

Verdict: **SAFE.**

## Flags matrix (production-critical defaults)

| Flag | Default | Intent |
|------|---------|--------|
| `AGENT_EXECUTION_LIVE_SENDER_ENABLED` | OFF | Live agent → user sender disabled |
| `CRM_CAMPAIGN_SEND_ENABLED` | OFF | Mass campaign send disabled |
| `CRM_CAMPAIGN_SEND_DRY_RUN_ONLY` | ON | Belt-and-suspenders: any campaign send is dry-run |
| `AGENT_FOLLOWUPS_ENABLED` | OFF | Auto follow-ups disabled |
| `CRM_OPERATOR_REPLY_ENABLED` | OFF | Operator → user direct replies disabled |
| `CRM_OPERATOR_HANDOFF_AUTO_EXPIRE_ENABLED` | OFF | Step 9 job is no-op |
| `ADMIN_SECURITY_ACTIONS_ENABLED` | OFF | Mutating admin security actions disabled |
| `ADMIN_IP_BLOCK_ENFORCEMENT_ENABLED` | OFF | IP block enforcement disabled |
| `AGENT_DECISION_ENGINE_ENABLED` | OFF | Decision engine disabled |
| `AGENT_DECISION_LOG_ONLY` | ON | If turned on later, stays log-only |
| `AGENT_EXECUTION_API_APPROVAL_ENABLED` | OFF | Execution approval API disabled |
| `AGENT_EXECUTION_AUTO_EXECUTE_APPROVED` | OFF | No auto-execute on approval |
| `CRM_OPERATOR_HANDOFF_ADMIN_NOTIFY_ENABLED` | OFF | No admin push from handoff write path |
| `CRM_CAMPAIGN_SEND_REQUIRE_CONFIRMATION` | ON | Confirmation required if send ever flips on |

Every dangerous flag is OFF. Every safety-gate flag (dry-run-only,
log-only, require-confirmation) is ON. The Stage 1 LOG_ONLY posture is
preserved.

## Migration checklist

- `infrastructure/database/migrations/versions/20260527_0530_n1o2p3q4r5s6_add_crm_operator_handoff_requests.py` is the only handoff-specific migration and it predates Step 9.
- Steps 6–9 require **no new migrations**. Step 9 reuses the existing
  `crm_operator_handoff_requests` table; the `status` column already
  allows the `expired` value.
- Production `alembic upgrade head` must be executed once when the
  branch is first deployed, but that is the same prerequisite as
  before Steps 6–9.

## VPS preconditions (when Stage 1 is later applied)

These remain unchanged from prior Stage 1 docs (see
`104_PRE_STAGE_1_FINAL_CHECKLIST.md` and `113_PRE_STAGE_1_P0_READINESS_RUNBOOK.md`).
Summary:

1. Postgres + Redis reachable from VPS.
2. `.env` populated with bot token, OpenAI key, DB password, admin IDs.
3. `alembic upgrade head` run.
4. Bot, scheduler, web, API services restartable independently.
5. Sentry DSN set if `APP_ENV=production`.

No VPS work is needed for this review.

## DB backup requirement

Before flipping `AGENT_DECISION_ENGINE_ENABLED` or any other Stage 1
"log-only enable" flag, a fresh `pg_dump` of the production database
must be on hand and verified restorable. Stage 1 itself only adds
write activity to a small set of audit tables, but the backup is the
hard prerequisite for rollback.

## Rollback note

If anything misbehaves after Stage 1 apply:

1. Flip the offending flag back to OFF (single env var change).
2. Restart the affected process (bot/scheduler/web/api).
3. If write damage suspected: stop scheduler, restore from `pg_dump`,
   re-apply migrations.
4. For Step 9 specifically: setting
   `CRM_OPERATOR_HANDOFF_AUTO_EXPIRE_ENABLED=false` halts further
   expiry on the next scheduler tick (≤15 min).

No `git revert` is needed for any Stage 1 flag flip.

## Stage 1 GO / NO-GO verdict

**GO from the code side.** All blockers traceable to code (live-send
flags, scheduler safety, web read-only posture, test green) are clear.

Outstanding blockers are **environmental, not code**:

1. Production `pg_dump` taken and restore-verified.
2. Production `alembic upgrade head` run on the live DB.
3. VPS service supervision (`systemd` or equivalent) confirmed for
   bot + scheduler + web + api.
4. Sentry DSN populated, error notification channel confirmed.
5. Operator on standby for the first observation window.

None of those require additional development.

## Test baseline (this review)

- Focused tests for Steps 2–9 web + Step 9 service + Step 9 scheduler +
  Step 9 integration: **378 passed**.
- Full unit + integration sweep: **6199 passed**.
- `ruff check .`: **clean**.
- `black --check .`: **clean** (816 files unchanged).
- Smoke imports: `apps.api.main`, `apps.web.main`, `apps.scheduler.main`,
  `apps.bot.build_dispatcher` all import cleanly.

## Next recommended action

Execute Stage 1 LOG_ONLY apply on the VPS:

1. Take and verify the `pg_dump` backup.
2. `alembic upgrade head` on the live DB.
3. Restart bot + scheduler + web + api.
4. Flip `AGENT_DECISION_ENGINE_ENABLED=true` only (keep
   `AGENT_DECISION_LOG_ONLY=true`). Leave every send flag OFF.
5. Observe the agent-decision audit log for 24–48 h.

If Stage 1 apply is still deferred, the next code step should be
**Operator Notification Digest** — daily summary of expired /
contacted / resolved counts — followed by **Stage 1 LOG_ONLY apply**
when the operator is ready.
