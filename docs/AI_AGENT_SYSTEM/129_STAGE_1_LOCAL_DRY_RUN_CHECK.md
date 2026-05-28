# 129 — Stage 1 Local Dry-Run Check (Step 13)

> Read-only local validation. **No deploy. No VPS. No flag flips. No
> Stage 1 apply.** Use this before any production change to catch
> regressions and missing artefacts on your local machine.

## What this is

A small CLI script — `scripts/production_deploy_dry_run_check.py` —
that audits the local checkout against the prerequisites in
`128_PRODUCTION_DEPLOYMENT_RUNBOOK.md`. It only reads files and
imports modules; it never talks to the network, the DB, Redis,
Telegram, OpenAI, or alembic.

## How to run

```text
# Human-readable summary
python scripts/production_deploy_dry_run_check.py

# Machine-readable JSON for CI / scripts
python scripts/production_deploy_dry_run_check.py --json
```

The script exits `0` unless at least one RED critical failure is
found. YELLOW alone never blocks; it's a heads-up.

## What it checks

- Git branch (expects `main`) and clean working tree.
- Required Step-13 docs present (`125`, `128`, `129`).
- Optional docs present (`113`, `114`, `124`, `126`, `127`).
- Core directories present: `apps/{api,web,scheduler,bot}`, `core`,
  `infrastructure`, `deploy`, `scripts`, alembic versions dir.
- Critical files present: `docker-compose.yml`,
  `docker-compose.prod.yml`, `.env.example`, `alembic.ini`,
  `deploy/docker/Dockerfile`, `deploy/docker/entrypoint.sh`.
- Critical migration `add_crm_operator_handoff_requests` exists.
- Dangerous flags default to OFF
  (live sender, campaign send, followups, operator reply, digest,
  handoff auto-expire, security actions, IP enforcement, auto-execute,
  approval API, digest delivery, admin-notify).
- Safety-gate flags default to ON
  (campaign dry-run-only, agent decision log-only, campaign
  require-confirmation).
- Key imports succeed: `apps.api.main`, `apps.web.main`,
  `apps.scheduler.main`, `apps.bot.main.build_dispatcher`.
- Key services importable: `PricingService`,
  `CRMOperatorHandoffService`, `build_digest`, `build_replay`,
  `build_history`.
- `.env.example` contains placeholders only — no real `sk-…`,
  `AIza…`, or other obvious secret literals.

## GREEN / YELLOW / RED meaning

| Status | Meaning | Action |
|--------|---------|--------|
| GREEN | OK | Continue. |
| YELLOW | Non-blocking gap — usually environmental (missing optional doc, settings can't be loaded because `.env` isn't filled). | Note for the operator. Doesn't block the dry-run itself. |
| RED | Critical failure — would break a real deploy if shipped now. | Stop. Fix before VPS. |

The overall status equals the highest severity present:
RED > YELLOW > GREEN.

## What must be fixed before VPS

Anything RED. Concretely:

- Missing required doc.
- Missing required directory or file.
- Missing critical migration.
- Any dangerous flag defaulting to `true`.
- Any safety-gate flag defaulting to `false`.
- Any import failure in the four entry-point modules
  (`apps.api.main`, `apps.web.main`, `apps.scheduler.main`,
  `apps.bot.main`).
- Real secret literal accidentally checked into `.env.example`.

## What can be ignored until VPS

YELLOW items are allowed to remain when the underlying check is
environmental, e.g.:

- Optional doc missing (e.g. `113`, `114`) — recommended but not
  required for the runbook flow.
- Settings cannot be loaded because the local `.env` isn't filled.
  This is normal on a fresh checkout — production `.env` will be on
  the VPS, never in git.
- Local `git status` is not clean (in-progress work). Production
  uses the pushed `main`, so local untracked files don't ship.
- A service attribute renamed since the last revision. Bring the
  script in sync the next time the surface changes.

## What the script does **not** do

- Does not connect to PostgreSQL.
- Does not connect to Redis.
- Does not call the Telegram Bot API.
- Does not call the OpenAI API.
- Does not run `alembic upgrade` or `alembic downgrade`.
- Does not read or print real `.env` secrets.
- Does not run `docker build` (the `--docker` flag is reserved for
  a future opt-in; today it is acknowledged and otherwise no-op).

## When to run this

- Before opening a deploy-related PR.
- Before applying Stage 1 LOG_ONLY on the VPS.
- After any large dependency or settings change.
- As part of CI (the JSON mode is friendly to CI parsers).

## Output companion

`130_STEP_13_PRODUCTION_DRY_RUN_REPORT.md` captures the latest
authoritative output for the current commit on `main`.
