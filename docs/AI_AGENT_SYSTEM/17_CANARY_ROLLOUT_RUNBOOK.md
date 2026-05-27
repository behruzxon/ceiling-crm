# Canary Rollout Runbook

Step-by-step guide for safely rolling out the AI agent system from LOG_ONLY to LIVE.

**DO NOT skip stages. Each stage must pass before proceeding.**

## A) Pre-flight Checklist

Run `python scripts/agent_preflight_check.py` before each stage.

- [ ] All migrations applied (`alembic upgrade head`)
- [ ] Bot smoke OK (`python -c "from apps.bot.main import build_dispatcher"`)
- [ ] Scheduler smoke OK (`python -c "import apps.scheduler.main"`)
- [ ] All unit tests pass (`pytest tests/unit/ -q`)
- [ ] All simulation tests pass (`pytest tests/simulation/ -q`)
- [ ] Metrics dashboard accessible (`/agent` page loads)
- [ ] BOT_ADMIN_GROUP_ID configured
- [ ] Feature flags at expected defaults
- [ ] Canary user IDs prepared (admin Telegram IDs)
- [ ] Logs visible and accessible
- [ ] DB backup taken

## B) Rollout Stages

### Stage 0 — OFF (current default)

All agent flags false. No agent behavior.

**Verify:** Dashboard works, metrics show zeros, no agent traces.

### Stage 1 — LOG_ONLY

Enable signal extraction + orchestrator in log-only mode:

```
AGENT_LEAD_SIGNAL_ENABLED=true
AGENT_LEAD_SCORING_ENABLED=true
AGENT_TEXT_NORMALIZATION_ENABLED=true
AGENT_FUZZY_INTENT_ENABLED=true
AGENT_DECISION_ENGINE_ENABLED=true
AGENT_DYNAMIC_OFFER_ENABLED=true
AGENT_CONVERSATION_POLICY_ENABLED=true
AGENT_RESPONSE_ORCHESTRATOR_ENABLED=true
AGENT_RESPONSE_ORCHESTRATOR_LOG_ONLY=true
AGENT_RESPONSE_ORCHESTRATOR_TRACE_ENABLED=true
```

**Verify:**
- No user behavior change
- `memory_data.last_orchestrator_trace` populated
- Dashboard shows signal/decision/offer activity
- Health status green

**Duration:** 24-48h observation

### Stage 2 — DRY_RUN

Enable sandbox in dry-run mode:

```
AGENT_EXECUTION_SANDBOX_ENABLED=true
AGENT_EXECUTION_MODE=dry_run
AGENT_EXECUTION_TRACE_ENABLED=true
```

**Verify:**
- `last_execution_sandbox.would_execute` shown in traces
- Blocked reasons visible
- No real sends
- Health green

**Duration:** 24h observation

### Stage 3 — CANARY

Enable follow-ups for canary users only:

```
AGENT_EXECUTION_MODE=canary
AGENT_EXECUTION_CANARY_USER_IDS=<admin1_id>,<admin2_id>
AGENT_FOLLOWUPS_ENABLED=true
AGENT_CATALOG_FOLLOWUP_ENABLED=true
AGENT_PRICE_FOLLOWUP_ENABLED=true
AGENT_ORDER_FOLLOWUP_ENABLED=true
AGENT_CATALOG_FOLLOWUP_DELAY_MINUTES=1
AGENT_PRICE_FOLLOWUP_DELAY_MINUTES=1
AGENT_ORDER_FOLLOWUP_DELAY_MINUTES=1
```

**Verify:**
- Only canary users receive follow-ups
- Non-canary users blocked/dry-run
- Stop words work: "kerak emas" disables
- Dashboard health green/yellow only

**Duration:** Test with admin accounts, 2-4h

### Stage 4 — APPROVAL_REQUIRED

Enable approval queue:

```
AGENT_EXECUTION_MODE=approval_required
AGENT_EXECUTION_QUEUE_ENABLED=true
AGENT_EXECUTION_APPROVAL_ADMIN_NOTIFY=true
AGENT_EXECUTION_AUTO_EXECUTE_APPROVED=false
```

**Verify:**
- Proposed executions appear in queue/dashboard
- Admin can approve/reject via callbacks
- No auto-send
- Approved status but no execution

**Duration:** 1-2 days of admin review

### Stage 5 — APPROVED LIVE SEND

Enable live sender for approved payloads:

```
AGENT_EXECUTION_LIVE_SENDER_ENABLED=true
AGENT_EXECUTION_AUTO_EXECUTE_APPROVED=true
```

**Verify:**
- Only admin-approved payloads sent
- `executed_at` set on success
- `failed_at` set on error
- Dashboard shows executed/failed counts
- No duplicate sends

**Duration:** 2-3 days with admin monitoring

### Stage 6 — LIMITED LIVE

After all stages pass, carefully expand:
- Keep daily caps (3/user/day)
- Keep lifetime caps (5 total)
- Business hours only
- Monitor dashboard continuously
- Gradually remove canary restriction

## C) Live Test Scenarios

See `docs/AI_AGENT_SYSTEM/18_LIVE_TEST_SCENARIOS.md`

## D) Metrics to Monitor

At each stage, check the `/agent` dashboard for:
- Pending followups (should not spike)
- Failed followups (threshold: <5/24h)
- Blocked executions (expected in canary)
- Pending approvals (queue not stuck)
- Executed actions (only after Stage 5)
- Health status (must not be red)
- Stop signals (working correctly)

## E) Stop Rollout Criteria

**Immediately rollback if ANY of these occur:**
- Failed followups > 20 in 24h
- Health status RED
- Non-canary user receives message in canary mode
- Unexpected user DM from agent
- Duplicate sends detected
- Raw phone/token appears in messages
- User spam complaint
- Approval queue stuck (>50 pending)
- Scheduler errors repeated (>5 in 1h)

## F) Rollback Plan

1. Set all agent flags to defaults (see `19_AGENT_FLAGS_REFERENCE.md` rollback column)
2. Restart bot: `docker compose restart bot`
3. Restart scheduler: `docker compose restart scheduler`
4. If approval queue has pending items, they expire automatically (30min TTL)
5. If follow-ups pending, they will be skipped (stale check)
6. Dashboard remains read-only for investigation
7. Preserve logs — do not clear

**One-liner emergency rollback (set in .env):**
```
AGENT_RESPONSE_ORCHESTRATOR_ENABLED=false
AGENT_EXECUTION_SANDBOX_ENABLED=false
AGENT_EXECUTION_QUEUE_ENABLED=false
AGENT_EXECUTION_LIVE_SENDER_ENABLED=false
AGENT_FOLLOWUPS_ENABLED=false
```

## G) Post-Test Report Template

After each stage, fill in:

```
Stage: ___
Flags changed: ___
Canary user IDs: ___
Duration: ___
Scenarios tested: ___/___
Scenarios passed: ___
Scenarios failed: ___
Metrics snapshot:
  - pending followups: ___
  - failed followups: ___
  - blocked executions: ___
  - health status: ___
Issues found: ___
Rollback needed: yes/no
Next stage allowed: yes/no
Approved by: ___
Date: ___
```
