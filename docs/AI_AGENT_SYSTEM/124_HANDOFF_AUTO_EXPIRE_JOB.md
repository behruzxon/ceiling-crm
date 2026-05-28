# 124 — Handoff Auto-Expire Job (Step 9)

## Purpose

Background cleanup job that marks stale operator handoff requests as
`expired`, so they drop out of the active queue without manual operator
intervention. Internal-only — no Telegram or OpenAI calls.

## Expiration rules

A handoff row is eligible for expiry **only** if all of the following hold:

1. `status` is one of `{open, waiting_phone, assigned}`.
2. Either:
   - `expires_at` is set and `expires_at <= now`, OR
   - `expires_at` is NULL and `created_at + expire_hours <= now`.

When eligible the row is updated to `status = 'expired'`, `updated_at = now`.
Nothing is deleted.

### Statuses protected (never expired)

`contacted`, `resolved`, `cancelled`, `expired` — these are terminal or
human-managed and the job will leave them untouched even if the SELECT
returns them.

## Scheduler behavior

- Job id: `crm_handoff_auto_expire`.
- Trigger: `interval`, every **15 minutes**.
- Registered in `apps/scheduler/main.py` alongside other jobs.
- **Disabled by default.** When the flag is off the job no-ops on every
  fire (no DB session opened, no service call).
- Errors are caught at every layer: config error, session factory error,
  service exception, query error, commit error. Nothing crashes the
  scheduler process.

## Config flags

| Flag | Default | Purpose |
|------|---------|---------|
| `CRM_OPERATOR_HANDOFF_AUTO_EXPIRE_ENABLED` | `false` | Master switch — the job no-ops while false. |
| `CRM_OPERATOR_HANDOFF_EXPIRE_HOURS` | `24` | Fallback TTL when `expires_at` is NULL. |
| `CRM_OPERATOR_HANDOFF_EXPIRE_BATCH_LIMIT` | `100` | Max rows scanned per fire (clamped 1..1000). |

`expire_hours` was already in settings from earlier work — Step 9 reuses
it. Only `_AUTO_EXPIRE_ENABLED` and `_EXPIRE_BATCH_LIMIT` are new.

## No-send safety

- Service module (`core/services/crm_operator_handoff_service.py`) does
  not import `aiogram` or `openai`.
- Scheduler job module does not import `aiogram`, `openai`, or any
  `send_message` helper.
- The job touches only the `crm_operator_handoff_requests` table; no
  user-facing message is generated.
- Web template adds an `expired` filter option and a neutral expired
  badge — no new send buttons, no ETA strings.

## Tests

- `tests/unit/services/test_step_9_handoff_auto_expire_service.py` — 62
  tests covering the pure `is_handoff_expirable` predicate and the async
  `expire_stale_handoffs` method (status filtering, fallback, limit
  clamping, error paths, no token/phone leak).
- `tests/unit/scheduler/test_step_9_handoff_auto_expire_job.py` — 31
  tests covering registration (id, interval, trigger), disabled no-op,
  enabled dispatch, config propagation, error containment, source-level
  safety guards (no aiogram/openai/send).
- `tests/unit/web/test_step_9_handoff_expired_ui.py` — 17 tests
  confirming the expired filter + badge are present and that no send
  button or ETA text was introduced.
- `tests/integration/agent/test_step_9_handoff_auto_expire_flow.py` —
  18 tests covering the end-to-end transition flow plus Step 8
  regression sanity checks.

All 128 new tests pass. Step 8 + Step 2 + Step CL handoff regression
suite (243 tests) also continues to pass.

## Limitations

- Bulk update is done in Python (one row at a time) rather than a
  single `UPDATE ... WHERE` statement. Acceptable at expected batch
  sizes (≤100/run) and keeps the post-filter safety check.
- No alert is sent to operators about auto-expired handoffs; the
  dashboard can show the count via the existing queue filter.
- Time-zone handling: naive datetimes are coerced to UTC before
  comparison.

## Next step

Step 10 — Stage 1 LOG_ONLY apply readiness review, or alternatively
Step 10 — Operator notification digest (daily summary of expired +
contacted + resolved counts) if Stage 1 is still deferred.
