# 130 — Step 13 Production Dry-Run Report

> **Status:** report only. No deploy, no VPS, no flag flip, no Stage 1
> apply executed by this step.

## Dry-run result

| Field | Value |
|-------|-------|
| Overall | **YELLOW** |
| GREEN | 50 |
| YELLOW | 1 |
| RED | 0 |
| Total items | 51 |

Exit code: **0** (YELLOW does not block).

## Warnings

The sole YELLOW item is `git_status` — a small set of in-progress
Step-13 files were untracked when the snapshot was taken. The
production deploy uses the pushed `main` tip; local untracked files
never ship.

## Blockers

**None.** Zero RED findings on the current `main` tip after Steps 1–12
were merged.

## What is ready

- All required documents (`125`, `128`, `129`) exist.
- All optional readiness/feature docs (`113`, `114`, `124`, `126`,
  `127`) exist.
- Core directory layout intact: `apps/{api,web,scheduler,bot}`,
  `core`, `infrastructure`, `deploy`, `scripts`, alembic versions.
- Required files present: `docker-compose.yml`,
  `docker-compose.prod.yml`, `.env.example`, `alembic.ini`,
  `deploy/docker/Dockerfile`, `deploy/docker/entrypoint.sh`.
- Critical migration `add_crm_operator_handoff_requests` present.
- Every dangerous flag defaults to OFF.
- Every safety gate (`crm_campaign_send_dry_run_only`,
  `agent_decision_log_only`, `crm_campaign_send_require_confirmation`)
  defaults to ON.
- Entry-point imports succeed:
  `apps.api.main`, `apps.web.main`, `apps.scheduler.main`,
  `apps.bot.main.build_dispatcher`.
- Key services importable: `PricingService`,
  `CRMOperatorHandoffService`, `build_digest`, `build_replay`,
  `build_history`.
- `.env.example` contains placeholders only — no real secret literals.

## What remains manual (VPS-side, not blockers for the code base)

These cannot be validated from the local checkout and stay manual on
the VPS:

1. `pg_dump` taken on the live DB + verified restorable on a scratch
   instance.
2. `alembic upgrade head` applied on the live DB.
3. systemd/supervisor (or Compose) supervising bot + scheduler + web +
   api with restart-on-failure.
4. Sentry DSN populated; error channel confirmed.
5. Operator on standby for the first 30 min of the apply window.

## Why VPS was not touched

This step is preparation only. Per the spec:

- No deploy.
- No VPS.
- No flag flips.
- No production migrations.
- No real Telegram / OpenAI calls.

The dry-run script enforces these guarantees at the code level —
its source contains no aiogram/openai imports, no `connect_database`,
no `connect_redis`, no `subprocess.run(["alembic", …])`, no reads of
`.env`. Tests assert each of those facts.

## Next step recommendation

Two viable paths:

- **Option A — Stage 1 LOG_ONLY apply on the VPS** (preferred once
  pg_dump + alembic + systemd + Sentry are confirmed on the VPS).
  Follow `128_PRODUCTION_DEPLOYMENT_RUNBOOK.md` §7→§12 in order. After
  smoke + 30 min observation are GREEN, flip only:
  - `AGENT_DECISION_ENGINE_ENABLED=true`
  - `AGENT_DECISION_LOG_ONLY=true`
  Every send flag stays OFF.

- **Option B — Defer Stage 1; continue product polish.** If the VPS
  preconditions are not yet ready, keep iterating on internal-only
  CRM/web work. The dry-run remains GREEN/YELLOW after each merge.

Either way, re-run
`python scripts/production_deploy_dry_run_check.py` before any
deploy-related work and confirm the overall status is not RED.
