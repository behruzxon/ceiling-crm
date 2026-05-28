> Status: AUDIT REPORT. Deploy: NO. VPS: NO. Flags: NOT ENABLED. Stage 1: NOT APPLIED.
> Live sender: NOT ENABLED. Campaign send: NOT ENABLED. Operator reply live send: NOT ENABLED.

# 134 — Pre-deploy Blockers and Stage 1 Decision

This document collects every blocker that must be cleared before the VPS bring-up, and gives a
clear Stage 1 verdict.

---

## Stage 1 verdict

**CONDITIONAL GO.**

Stage 1 = `AGENT_DECISION_ENGINE_ENABLED=true` and `AGENT_DECISION_LOG_ONLY=true`, plus the
companion log-only flags for the response orchestrator, dynamic offer, and conversation policy.
No sends. No customer impact.

This is safe to enable today, *after* the four blockers in §1 below are closed. Without those
four, the dry-run check (doc 129) and the runbook (doc 128) cannot be trusted end-to-end.

---

## 1. Hard blockers (Stage 1 cannot start)

| # | Blocker | Why | Owner | Exit criteria |
|---|---|---|---|---|
| 1 | **Real `pg_dump` / `pg_restore` drill on a copy** | Runbook (doc 128) lists the commands; we have not actually executed them end-to-end. | Ops | Dump + restore + `SELECT count(*) FROM leads` matches source. |
| 2 | **`scripts/production_deploy_dry_run_check.py` JSON output committed** | Doc 129 names the script; the JSON record is the audit trail. | Ops | `--json` output saved to `docs/AI_AGENT_SYSTEM/_artifacts/dry_run_<date>.json`. |
| 3 | **Phone-masking sweep across every log/notification site** | At least `_notify_admin` paths can include the raw phone today. | Eng | `grep -rE "phone[^_]" core/ apps/` audited; raw phone gone from logs. |
| 4 | **CSRF middleware wired into web app** | The service is built but is not mounted. Any web POST is unprotected. | Eng | `apps/web/main.py` mounts middleware; unit test exercises a 403 on missing token. |

---

## 2. Conditional GO checklist (close these *during* or *immediately after* Stage 1)

| # | Item | Notes |
|---|---|---|
| 5 | Architecture-lint test asserting `apps/` does not import `infrastructure/` directly. | Pure test; no behavioral risk. |
| 6 | Regression test: `DEFAULT_BASE_PRICES` is never imported by any bot handler. | Single grep + assert; protects the price story. |
| 7 | Replace browser `confirm()` for execution approve/reject with typed modal that shows the actual message. | Pure UI change. |
| 8 | Add a "kill switch" Telegram command (admin only) that sets `AGENT_RESPONSE_ORCHESTRATOR_ENABLED=false` at runtime. | Requires runtime settings store. |
| 9 | Document Stage 1 daily summary email/Telegram delivery (`crm_daily_report_delivery_enabled` stays OFF; a *one-line* Telegram DM is fine). | Decide a delivery channel before enabling. |
| 10 | Add a per-decision audit log row exposed on `/agent`. | Already partly in `agent_metrics_service`; surface it. |

---

## 3. Required pre-deploy security checklist

Before any production rollout (independent of Stage 1):

- [ ] `APP_ENV=production` set on the host
- [ ] `APP_DEBUG=false`
- [ ] `APP_SECRET_KEY` rotated and at least 64 random bytes
- [ ] `BOT_TOKEN` set, never committed
- [ ] `BOT_WEBHOOK_URL` and `BOT_WEBHOOK_SECRET` set
- [ ] `SENTRY_DSN` set with `SENTRY_ENVIRONMENT=production`
- [ ] `OPENAI_API_KEY` set, rotated
- [ ] `API_INTERNAL_TOKEN` set and ≥ 32 random bytes
- [ ] `WEB_DASHBOARD_USERNAME` and `WEB_DASHBOARD_PASSWORD` set
- [ ] `ADMIN_SESSION_AUTH_ENABLED=true` (web behind session, not just basic)
- [ ] `ADMIN_CSRF_ENABLED=true` after middleware wired
- [ ] `ADMIN_RBAC_ENABLED=true` with at least one assigned owner
- [ ] `ADMIN_IP_RULES_ENABLED=true` if the platform sits on the internet
- [ ] `ADMIN_IP_BLOCK_ENFORCEMENT_ENABLED=true` only after rules are tested in shadow
- [ ] `AGENT_EXECUTION_LIVE_SENDER_ENABLED=false`
- [ ] `AGENT_EXECUTION_AUTO_EXECUTE_APPROVED=false`
- [ ] `AGENT_SETTINGS_ALLOW_LIVE_FLAGS=false`
- [ ] `CRM_CAMPAIGN_SEND_ENABLED=false`
- [ ] `CRM_OPERATOR_REPLY_ENABLED=false`
- [ ] `CRM_OPERATOR_DIGEST_DELIVERY_ENABLED=false`
- [ ] `AGENT_FOLLOWUPS_ENABLED=false`
- [ ] `AGENT_ADMIN_ESCALATION_ENABLED=false`
- [ ] `ADMIN_SECURITY_ACTIONS_ENABLED=false`
- [ ] Postgres backups scheduled (cron + `pg_dump` to off-host)
- [ ] Redis persistence policy chosen
- [ ] Docker containers run as non-root
- [ ] nginx + TLS in front (or equivalent) with rate-limit
- [ ] `/healthz` smoke check wired to uptime monitor
- [ ] Smoke imports green: `python -c "import apps.api.main"`, `apps.web.main`,
  `apps.scheduler.main`, `apps.bot.main.build_dispatcher`
- [ ] Test suite green: `pytest tests/unit/ -q` and integration green where applicable

---

## 4. Rollback playbook

If anything goes wrong after Stage 1 flip:

1. **First**: set `AGENT_RESPONSE_ORCHESTRATOR_ENABLED=false` and restart the bot pod. The agent
   reverts to silent observation.
2. **Then**: set `AGENT_DECISION_ENGINE_ENABLED=false`. Decisions are no longer evaluated.
3. **Then**: tail the bot logs for the next 5 minutes — look for `safety_flags` containing
   anything other than `terminal_state` or `daily_cap`.
4. **If a customer received a message** (which should be impossible in LOG_ONLY): open the
   contact-detail page, click "Open conversation in Telegram", apologize manually. Mark the
   incident in `docs/AI_AGENT_SYSTEM/_incidents/`.
5. **Open** an incident doc with: timestamp, env, exact flag state at the moment, last 10
   commits, what the user saw.
6. **Database rollback**: `alembic downgrade -1` only if the latest migration is the cause.
7. **Full rollback to previous tag**: `docker-compose pull <prev-tag> && docker-compose up -d`
   (per doc 128).

---

## 5. Final recommendation

We recommend the following sequence:

1. Close blockers 1–4 (§1).
2. Run the dry-run check and attach the JSON to `_artifacts/`.
3. Bring up the VPS in **API-only + Bot-only + Web-only** modes one at a time, with the
   scheduler **down**.
4. Smoke-test each (`/healthz`, `/dashboard` with Basic Auth, `/start` on Telegram).
5. Bring up the scheduler.
6. Wait 30 minutes; check logs.
7. Flip Stage 1 flags (decision engine on; LOG_ONLY).
8. Wait 30 minutes; check `safety_flags` distribution.
9. If clean, proceed to Stage 2 (proposal queue, no sends).
10. Do **not** flip live sender for at least 7 days after Stage 1 is clean.

Stage 1 status today: **NOT APPLIED.** Verdict: **CONDITIONAL GO** once §1 blockers clear.
