# Pre-Stage 1 P0 Readiness Runbook

**Date**: 2026-05-27 | **Commit**: 60b3e94 | **Status**: NOT DEPLOYED, NOT APPLIED

## A) Current Baseline

- Branch: feature/vash-ai-hardening-session
- Tests: 5594 passing (5020 unit + 574 simulation)
- All smoke checks: OK
- All safety flags: DEFAULT OFF
- Stage 1 verdict: CONDITIONAL GO

## B) P0 Blockers

| # | Blocker | Status | Action |
|---|---------|--------|--------|
| 1 | VPS access | NOT VERIFIED | SSH into VPS, verify Docker running |
| 2 | DB backup | NOT DONE | Run pg_dump before any migration |
| 3 | ADMIN_SESSION_AUTH | DISABLED | Set =true in production .env |
| 4 | alembic upgrade head | NOT RUN | Run after backup, creates handoff table |

## C) VPS Access Checklist

- [ ] SSH to VPS works
- [ ] Docker is installed and running
- [ ] docker compose is available
- [ ] PostgreSQL container running and accessible
- [ ] Redis container running and accessible
- [ ] Git is installed on VPS
- [ ] Can pull branch: git pull origin feature/vash-ai-hardening-session
- [ ] Python 3.11+ available
- [ ] pip/requirements installed

## D) DB Backup Commands

```bash
# Option 1: pg_dump from Docker
docker compose exec postgres pg_dump -U ceilingcrm ceilingcrm > backup_$(date +%Y%m%d_%H%M).sql

# Option 2: pg_dump from host
pg_dump -h localhost -U ceilingcrm -d ceilingcrm > backup_$(date +%Y%m%d_%H%M).sql

# Verify backup
ls -la backup_*.sql
head -20 backup_*.sql
```

- [ ] Backup file created
- [ ] Backup file size > 0
- [ ] Backup file contains CREATE TABLE statements

## E) Alembic Upgrade Head

```bash
# Run migration
alembic upgrade head

# Expected output: new table crm_operator_handoff_requests
# Verify
python -c "from infrastructure.database.models.crm_operator_handoff import CRMOperatorHandoffModel; print('OK')"
```

- [ ] alembic upgrade head completed without error
- [ ] No data loss
- [ ] New table crm_operator_handoff_requests created

## F) ADMIN_SESSION_AUTH Enablement

In production .env, add or change:
```
ADMIN_SESSION_AUTH_ENABLED=true
```

This enables HTTP Basic Auth for the web dashboard. Without it, the dashboard is accessible without credentials.

- [ ] ADMIN_SESSION_AUTH_ENABLED=true set in .env
- [ ] WEB_DASHBOARD_USERNAME set
- [ ] WEB_DASHBOARD_PASSWORD set (strong password)
- [ ] Restart web service after .env change

## G) Dangerous Flags — Must Remain OFF

| Flag | Required Value | Why |
|------|---------------|-----|
| AGENT_EXECUTION_LIVE_SENDER_ENABLED | false | No auto-sends |
| AGENT_FOLLOWUPS_ENABLED | false | No followup messages |
| AGENT_EXECUTION_AUTO_EXECUTE_APPROVED | false | No auto-execution |
| CRM_CAMPAIGN_SEND_ENABLED | false | No campaign broadcasts |
| CRM_OPERATOR_REPLY_ENABLED | false | No operator live reply |
| ADMIN_SECURITY_ACTIONS_ENABLED | false | No security action enforcement |
| ADMIN_IP_BLOCK_ENFORCEMENT_ENABLED | false | No IP blocking |
| CRM_OPERATOR_HANDOFF_ADMIN_NOTIFY_ENABLED | false | No auto admin notify |

## H) Preflight Commands

```bash
python -c "from apps.bot.main import build_dispatcher; print('Bot OK')"
python -c "import apps.scheduler.main; print('Scheduler OK')"
python -c "from apps.api.main import app; print('API OK')"
python scripts/agent_stage1_readiness_check.py
python scripts/agent_preflight_check.py
```

All must return OK or GREEN/YELLOW (no RED).

## I) Stage 1 LOG_ONLY Apply Sequence

1. Verify all preflight checks pass
2. Open /agent dashboard in browser
3. Navigate to Rollout Presets
4. Select LOG_ONLY -> Preview
5. Review settings (all sends OFF)
6. Click Apply
7. Verify: Stage=LOG_ONLY, Health=GREEN
8. Restart bot: docker compose restart bot
9. Restart scheduler: docker compose restart scheduler
10. Send 6 test messages (see doc 108)
11. Monitor 30 min active
12. Monitor 24h passive

## J) Rollback Plan

If any issue during Stage 1:
1. Open /agent -> Rollout Presets -> OFF -> Apply
2. docker compose restart bot scheduler
3. Verify bot responds normally
4. Check logs for errors
5. Report issue before retry

STOP immediately if:
- Unexpected user message sent
- Followup count > 0
- Live sender count > 0
- Health RED

## K) Do-Not-Do List

- Do NOT enable live sender
- Do NOT enable followups
- Do NOT enable campaign send
- Do NOT enable operator live reply
- Do NOT skip DB backup
- Do NOT apply without monitoring time
- Do NOT change AGENT_EXECUTION_MODE beyond log_only
- Do NOT modify pricing constants
- Do NOT modify catalog behavior
- Do NOT run in production without ADMIN_SESSION_AUTH=true
