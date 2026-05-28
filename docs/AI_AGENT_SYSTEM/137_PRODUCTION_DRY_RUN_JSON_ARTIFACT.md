> Status: ARTIFACT RECORD. Deploy: NO. VPS: NO. Flags: NOT ENABLED.
> Stage 1 LOG_ONLY: NOT APPLIED. Production migrations: NOT RUN.
> Telegram / OpenAI APIs: NOT CALLED.

# 137 — Production Dry-Run JSON Artifact

This document closes blocker §1.2 in
`docs/AI_AGENT_SYSTEM/134_PRE_DEPLOY_BLOCKERS_AND_STAGE1_DECISION.md`:

> "`scripts/production_deploy_dry_run_check.py` JSON output committed —
> the JSON record is the audit trail."

It records when and how the JSON artifact was generated, what the
result was, and where it lives so future operators can reproduce the
check before any VPS bring-up.

---

## 1. Command run

```bash
python scripts/production_deploy_dry_run_check.py --json \
  > docs/AI_AGENT_SYSTEM/_artifacts/production_deploy_dry_run_latest.json
```

The dry-run script is **read-only**. Its hard guarantees (per the
docstring at the top of `scripts/production_deploy_dry_run_check.py`):

- No DB connection attempt.
- No Redis connection attempt.
- No Telegram API call.
- No OpenAI API call.
- No `alembic upgrade` invocation.
- No reading of secret values out of `.env`.
- Docker build is skipped (no `--docker` was passed).

---

## 2. Artifact path

`docs/AI_AGENT_SYSTEM/_artifacts/production_deploy_dry_run_latest.json`

The `_artifacts/` directory is the canonical location for read-only
audit-trail records referenced by the runbook in doc 128 and the
blocker tracker in doc 134.

---

## 3. Result summary

- Overall: **YELLOW**
- Counts: GREEN=50, YELLOW=1, RED=0
- Sole YELLOW item: `git_status` reported a single uncommitted file —
  the dry-run artifact itself, generated immediately before the
  commit that introduces this document. After the commit lands the
  working tree is clean, and a re-run flips that item to GREEN.
- No RED findings. Every dangerous flag is OFF, every safety gate is
  ON, every required import resolves, `.env.example` contains
  placeholders only.

---

## 4. Date / time of run

- Generated: 2026-05-28 (local main checkout).
- Git branch at run: `main`.
- Latest commit at run: `01ea438` (merge of PR #2 — CSRF middleware +
  phone masking).

---

## 5. Scope guardrails honoured

- Deploy: **NO** — script is read-only.
- VPS: **NO** — script never touches a remote host.
- Flags: **NOT ENABLED** — all `must-be-OFF` flags verified OFF.
- Stage 1 LOG_ONLY: **NOT APPLIED** — no settings were written.
- Production migrations: **NOT RUN** — script never invokes alembic.
- Telegram / OpenAI APIs: **NOT CALLED** — script imports modules but
  never calls outbound APIs.

A grep of the artifact for `BOT_TOKEN`, `OPENAI`, `DATABASE_URL`,
`postgres://`, `Bearer`, and `sk-` returned **zero matches**. The
artifact is safe to commit.

---

## 6. Remaining blocker

Blocker §1.2 in doc 134 (JSON artifact committed) is now **CLEARED**.

The remaining hard blocker before Stage 1 can begin is:

- **§1.1 — Real `pg_dump` / `pg_restore` drill on a copy.** The
  runbook (doc 128) lists the commands; we have not yet executed
  them end-to-end. Exit criteria: dump + restore +
  `SELECT count(*) FROM leads` matches source. Owner: Ops.

Blockers §1.3 (phone-masking sweep) and §1.4 (CSRF middleware wired)
were closed by PR #2 (commit `c9049b5`, merged via `01ea438`).

---

## 7. Reproducing this artifact

To regenerate the JSON artifact on a fresh checkout:

```bash
python scripts/production_deploy_dry_run_check.py --json \
  > docs/AI_AGENT_SYSTEM/_artifacts/production_deploy_dry_run_latest.json

# Verify the artifact is valid JSON without printing it to stdout.
python -m json.tool \
  docs/AI_AGENT_SYSTEM/_artifacts/production_deploy_dry_run_latest.json \
  > /dev/null

# Scan for accidentally leaked secrets before committing.
rg -n "BOT_TOKEN|OPENAI|DATABASE_URL|postgres://|Bearer|sk-" \
  docs/AI_AGENT_SYSTEM/_artifacts/production_deploy_dry_run_latest.json
```

If the secrets scan ever returns a hit, **do not commit**. Redact the
artifact and fix the script before retrying.
