# 128 — Production Deployment Runbook (Step 13)

> **Status:** PREPARATION ONLY. This runbook does **not** mean the app
> has been deployed. Nothing in this document has been executed on a
> VPS. Deploy: NO. VPS: NO. Flags: NOT ENABLED. Stage 1 LOG_ONLY: NOT
> APPLIED.

## 1. Purpose

A safe, ordered procedure for taking CeilingCRM from local main into
a production VPS. Captures the preconditions, env groups, backup
procedure, migration sequence, smoke checks, observation window, and
rollback. Pair with `129_STAGE_1_LOCAL_DRY_RUN_CHECK.md` to validate
locally before touching the VPS.

## 2. Preconditions

Before starting, ensure:

- VPS SSH access confirmed for the operator.
- DNS / domain pointing to the VPS (or IP allowlisted).
- Docker + Docker Compose installed on the VPS (Compose v2).
- PostgreSQL reachable from the VPS (managed instance or local
  container).
- Redis reachable from the VPS.
- A writable backup directory exists (e.g. `/var/backups/ceilingcrm/`).
- Sentry DSN populated and the error channel confirmed.
- Operator on standby for the first 30 min after apply.
- `pg_dump` of the production DB taken and verified restorable in a
  scratch instance.

## 3. Required services

| Service | Role |
|---------|------|
| `api` | FastAPI app (`apps.api.main`) |
| `bot` | Telegram bot (`apps.bot.main`) |
| `scheduler` | APScheduler (`apps.scheduler.main`) |
| `web` | Admin/CRM web (`apps.web.main`) |
| `postgres` | Primary data store |
| `redis` | Cache + FSM + Celery broker |
| `nginx` (optional) | TLS termination + reverse proxy |

## 4. Required env groups

The deploy `.env` (placeholders only — see `.env.example` in repo)
must define:

- **Application**: `APP_ENV=production`, `APP_DEBUG=false`,
  `APP_SECRET_KEY=<random>`, `LOG_LEVEL=INFO`.
- **Bot**: `BOT_TOKEN`, `BOT_WEBHOOK_URL`, `BOT_WEBHOOK_SECRET`,
  `BOT_ADMIN_GROUP_ID`, `BOT_MAIN_GROUP_ID`.
- **Postgres**: `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`,
  `POSTGRES_PASSWORD`, `POSTGRES_DB`.
- **Redis**: `REDIS_HOST`, `REDIS_PORT`, optional `REDIS_PASSWORD`.
- **OpenAI / AI**: `OPENAI_API_KEY` (placeholder — never commit a
  real key).
- **Admin auth / session**: `ADMIN_SESSION_AUTH_ENABLED`,
  `ADMIN_SESSION_COOKIE_NAME`, `ADMIN_SESSION_TTL_HOURS`,
  `ADMIN_OWNER_IDS`, `ADMIN_ADMIN_IDS`, `ADMIN_OPERATOR_IDS`.
- **Security / actions**: keep `ADMIN_SECURITY_ACTIONS_ENABLED=false`
  and `ADMIN_IP_BLOCK_ENFORCEMENT_ENABLED=false` for first apply.
- **Agent flags**: all execution / live-sender / followup / approval
  flags OFF; see §5.
- **CRM flags**: handoff / digest / operator-reply send flags OFF; see
  §5.
- **Web / API**: `API_INTERNAL_TOKEN` (required in production),
  `API_PORT`, `WEB_PORT`. CORS / origins for the admin domain.
- **Sentry**: `SENTRY_DSN`, `SENTRY_ENVIRONMENT=production`.

> No real secret values are tracked here. The runbook uses
> placeholders only. Real values live in the VPS-side `.env` and the
> operator's password manager.

## 5. Must-stay-OFF flags (first apply)

| Flag | Required default |
|------|------------------|
| `AGENT_EXECUTION_LIVE_SENDER_ENABLED` | `false` |
| `AGENT_EXECUTION_AUTO_EXECUTE_APPROVED` | `false` |
| `AGENT_EXECUTION_API_APPROVAL_ENABLED` | `false` |
| `CRM_CAMPAIGN_SEND_ENABLED` | `false` |
| `CRM_CAMPAIGN_SEND_DRY_RUN_ONLY` | `true` |
| `AGENT_FOLLOWUPS_ENABLED` | `false` |
| `CRM_OPERATOR_REPLY_ENABLED` | `false` |
| `CRM_OPERATOR_HANDOFF_AUTO_EXPIRE_ENABLED` | `false` (flip later if desired) |
| `CRM_OPERATOR_HANDOFF_ADMIN_NOTIFY_ENABLED` | `false` |
| `CRM_OPERATOR_DIGEST_ENABLED` | `false` |
| `CRM_OPERATOR_DIGEST_DELIVERY_ENABLED` | `false` |
| `ADMIN_SECURITY_ACTIONS_ENABLED` | `false` |
| `ADMIN_IP_BLOCK_ENFORCEMENT_ENABLED` | `false` |

A violation of any of these on first apply is grounds to roll back
before any user-visible activity begins.

## 6. Stage 1 LOG_ONLY flags

Only after §5 is verified OFF in the running container, flip:

- `AGENT_DECISION_ENGINE_ENABLED=true`
- `AGENT_DECISION_LOG_ONLY=true`

Every send flag from §5 stays OFF during Stage 1.

## 7. Backup procedure

```text
# Placeholder commands — replace <PLACEHOLDER> with VPS values.
pg_dump -h <POSTGRES_HOST> -U <POSTGRES_USER> -d <POSTGRES_DB> \
    -F c -f /var/backups/ceilingcrm/$(date +%Y%m%d_%H%M)_pre_stage1.dump
ls -lh /var/backups/ceilingcrm/
```

Verification (mandatory):

```text
# Restore the dump into a scratch database before continuing.
createdb -h <POSTGRES_HOST> -U <POSTGRES_USER> ceilingcrm_verify
pg_restore -h <POSTGRES_HOST> -U <POSTGRES_USER> \
    -d ceilingcrm_verify /var/backups/ceilingcrm/<YYYYMMDD_HHMM>_pre_stage1.dump
# Confirm row counts on key tables, then drop the scratch DB.
dropdb -h <POSTGRES_HOST> -U <POSTGRES_USER> ceilingcrm_verify
```

**Never continue without a verified-restorable backup.** If
verification fails, stop and investigate.

## 8. Migration procedure

```text
# Inspect state first.
alembic current
alembic heads

# Run migrations.
alembic upgrade head

# Confirm head matches.
alembic current
```

Rollback note: `alembic downgrade -1` is available, but only as a
last resort. Prefer restoring the pre-apply `pg_dump` if the
migration causes unrecoverable damage.

## 9. Deploy sequence

1. `git fetch origin && git checkout main && git pull --ff-only origin main`
2. `git status` — confirm clean.
3. Run local dry-run check: `python scripts/production_deploy_dry_run_check.py`.
   Must return GREEN (or YELLOW only) before continuing.
4. On the VPS, build images:
   `docker compose -f docker-compose.prod.yml build`.
5. Validate configuration without starting traffic:
   `docker compose -f docker-compose.prod.yml config`.
6. Start dependencies only:
   `docker compose -f docker-compose.prod.yml up -d postgres redis`.
7. Take backup (§7) and verify restore.
8. Apply migrations (§8).
9. Start app services:
   `docker compose -f docker-compose.prod.yml up -d api web scheduler bot`.
10. Run smoke checks (§10).
11. Run 30-minute active observation (§11).
12. Apply Stage 1 LOG_ONLY flags (§6) — only after smoke + observation
    are GREEN.

## 10. Smoke checks

After services start, before flipping any flag:

- **API health**: `curl -fsS http://<host>:<api-port>/healthz` returns 200.
- **Web loads**: `curl -fsS -o /dev/null -w "%{http_code}" http://<host>:<web-port>/dashboard`
  returns a 200 or a redirect to login.
- **Bot import**: `python -c "from apps.bot.main import build_dispatcher; build_dispatcher()"`.
- **Scheduler import**: `python -c "import apps.scheduler.main"`.
- **DB connection**: API `/healthz` includes db-status; check it.
- **Redis connection**: API `/healthz` includes redis-status; check it.
- **No-send verification**: `curl -fsS http://<host>:<api-port>/api/v1/admin/agent/observation/recent`
  returns at most LOG_ONLY entries — no `live_sent=true` rows.

## 11. Observation checklist

- First 30 min: active. Operator watches:
  - Sentry for new error patterns.
  - `/agent/observation/recent` API for live-send markers (must stay 0).
  - `/crm/handoffs` for stuck queue.
  - `/crm/missed-leads` for new criticals.
  - Scheduler logs for unexpected job activity.
- 24–48h: passive. Daily check:
  - Agent decision audit log — does it look sane?
  - CRM handoffs count + severity from the Daily Operator Digest.
  - No new severities introduced.
  - No-sends remain at 0.

## 12. Rollback

In severity order:

1. **Flag-level**: set the offending flag back to `false` and
   `docker compose -f docker-compose.prod.yml restart <service>`.
   For Stage 1, that's a single flip
   (`AGENT_DECISION_ENGINE_ENABLED=false`).
2. **Service-level**: `docker compose -f docker-compose.prod.yml restart <api|bot|scheduler|web>`.
3. **App-level**: revert to the previous commit
   (`git checkout <previous-sha>`), rebuild images, restart.
4. **DB-level**: only if a migration caused unrecoverable damage —
   restore the pre-apply `pg_dump`. Stop scheduler before restoring.
5. **Emergency stop**: `docker compose -f docker-compose.prod.yml stop bot scheduler`
   halts all outbound activity while keeping API/web available for
   investigation.

## 13. Do-not-do list

- Do **not** force-push to `main` or any deployed branch.
- Do **not** edit the production DB directly outside migrations.
- Do **not** flip `AGENT_EXECUTION_LIVE_SENDER_ENABLED` on first apply.
- Do **not** flip `CRM_CAMPAIGN_SEND_ENABLED` on first apply.
- Do **not** flip `CRM_OPERATOR_REPLY_ENABLED` until operator training
  is documented and acknowledged.
- Do **not** commit real secrets to git. `.env` is in `.gitignore`.
- Do **not** skip the backup-restore verification step.
- Do **not** apply Stage 1 outside business hours unless the operator
  is explicitly on-call.

---

Companion: `129_STAGE_1_LOCAL_DRY_RUN_CHECK.md` for the local
validation, `125_STAGE_1_READINESS_REVIEW_AFTER_FRESH_START.md` for
the readiness verdict, and `130_STEP_13_PRODUCTION_DRY_RUN_REPORT.md`
for the most recent dry-run output.
