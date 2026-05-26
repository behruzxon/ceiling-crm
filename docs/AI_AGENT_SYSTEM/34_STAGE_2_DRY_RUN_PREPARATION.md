# Stage 2 — DRY_RUN Preparation

## What is DRY_RUN?

DRY_RUN mode enables the execution sandbox. The agent pipeline runs end-to-end — signal extraction, decision engine, dynamic offer, conversation policy, orchestrator — and produces **real execution payloads**. The sandbox then **validates** each payload (format, safety, policy compliance) but **never sends** it.

Key differences from LOG_ONLY:

| Aspect | LOG_ONLY (Stage 1) | DRY_RUN (Stage 2) |
|--------|--------------------|--------------------|
| Signal extraction | Yes | Yes |
| Decision engine | Yes | Yes |
| Offer selection | Yes | Yes |
| Policy evaluation | Yes | Yes |
| Orchestrator | Trace only | Full pipeline |
| Execution payload | Not built | Built + validated |
| Sandbox validation | N/A | Active |
| Actual send | No | No |
| Metrics tracked | Trace counts | would_execute, blocked, reasons |

In DRY_RUN, every orchestrated action produces a `would_execute` or `blocked` result with full metadata. This lets operators verify the agent's judgment before any real messages are sent.

## Prerequisites

All of these must be true before entering DRY_RUN:

- [ ] **Stage 1 completed** — at least 24h observation with PASS result
- [ ] **Stage 1 observation report** filed (see `24_STAGE_1_OBSERVATION_REPORT_TEMPLATE.md`)
- [ ] **Gate status**: READY or CONDITIONAL (no RED blockers in readiness check)
- [ ] **Zero safety violations** during Stage 1 (no unexpected DMs, no follow-ups, no escalations)
- [ ] **Health status**: GREEN
- [ ] **All migrations applied**: `alembic upgrade head`
- [ ] **Bot smoke test passes**: `python -c "from apps.bot.main import build_dispatcher"`
- [ ] **Scheduler smoke test passes**: `python -c "import apps.scheduler.main"`
- [ ] **Unit tests pass**: `pytest tests/unit/ -q`
- [ ] **Simulation tests pass**: `pytest tests/simulation/ -q`
- [ ] **Control Center `/agent` loads** and shows correct stage

## Required Flags (DRY_RUN Preset)

All of these must be `true` or set to the indicated value:

```
# Signal & Decision (carry forward from Stage 1)
AGENT_LEAD_SIGNAL_ENABLED=true
AGENT_LEAD_SCORING_ENABLED=true
AGENT_TEXT_NORMALIZATION_ENABLED=true
AGENT_FUZZY_INTENT_ENABLED=true
AGENT_DECISION_ENGINE_ENABLED=true

# Offer & Policy (carry forward from Stage 1)
AGENT_DYNAMIC_OFFER_ENABLED=true
AGENT_CONVERSATION_POLICY_ENABLED=true

# Orchestrator (upgrade from log_only)
AGENT_RESPONSE_ORCHESTRATOR_ENABLED=true
AGENT_RESPONSE_ORCHESTRATOR_LOG_ONLY=false
AGENT_RESPONSE_ORCHESTRATOR_TRACE_ENABLED=true

# Sandbox (new for Stage 2)
AGENT_EXECUTION_SANDBOX_ENABLED=true
AGENT_EXECUTION_MODE=dry_run
AGENT_EXECUTION_TRACE_ENABLED=true
```

## Flags That MUST Remain False/Disabled

These flags are **forbidden** in Stage 2. If any is accidentally enabled, rollback immediately.

```
# Execution — must stay off
AGENT_EXECUTION_LIVE_SENDER_ENABLED=false
AGENT_EXECUTION_AUTO_EXECUTE_APPROVED=false

# Follow-ups — must stay off
AGENT_FOLLOWUPS_ENABLED=false
AGENT_CATALOG_FOLLOWUP_ENABLED=false
AGENT_PRICE_FOLLOWUP_ENABLED=false
AGENT_ORDER_FOLLOWUP_ENABLED=false

# Admin escalation — must stay off
AGENT_ADMIN_ESCALATION_ENABLED=false

# Approval queue — must stay off
AGENT_EXECUTION_QUEUE_ENABLED=false
AGENT_EXECUTION_APPROVAL_ADMIN_NOTIFY=false

# AI composer — must stay off
AGENT_AI_COMPOSER_ENABLED=false
```

## Apply Method

### Option A: Control Center UI (recommended)

1. Open `/agent` dashboard
2. Find "Rollout Presets" section
3. Click **Preview** on DRY_RUN
4. Review diff — verify sandbox enabled, live sender OFF, follow-ups OFF
5. Verify no RED blockers
6. Click **Apply DRY_RUN**
7. Confirm in dialog

### Option B: API

```
POST /api/v1/admin/agent/settings/presets/dry_run/preview
POST /api/v1/admin/agent/settings/presets/dry_run/apply
{"confirmation_token": "<from preview>", "reason": "Stage 2 DRY_RUN trial"}
```

### Option C: .env (fallback)

Copy the Required Flags section above into `.env`, ensure all Forbidden Flags are explicitly `false`, then restart bot + scheduler:

```bash
docker compose restart bot scheduler
```

## Post-Apply Verification

Immediately after applying the DRY_RUN preset:

- [ ] Dashboard stage shows: **DRY_RUN**
- [ ] Health: GREEN
- [ ] Sandbox: **ON**
- [ ] Execution mode: **dry_run**
- [ ] Orchestrator log_only: **false** (pipeline runs end-to-end)
- [ ] Live sender: **OFF**
- [ ] Auto execute: **OFF**
- [ ] Follow-ups enabled: **false**
- [ ] Admin escalation: **OFF**
- [ ] Approval queue: **OFF**

## Manual Test Scenarios (Quick Validation)

Send from admin test account immediately after applying:

| # | You Send | Expected Sandbox Result | Must NOT Happen |
|---|----------|------------------------|-----------------|
| 1 | `25 kv metr qancha turadi` | Payload built: price reply. Sandbox: `would_execute`, action_type=`user_dm`, policy=`allowed` | Actual DM sent, follow-up scheduled |
| 2 | `qimmat ekan, arzonroq bormi` | Payload built: negotiation offer. Sandbox: `would_execute`, tactic=`cheaper_alternative` | Agent sends real price offer, admin alert |
| 3 | `нархи қанча 30 кв` | Payload built: price reply. Sandbox: `would_execute`, cyrillic_normalized=true | Bot behavior change, error log |
| 4 | `operator chaqiring` | Payload built: handoff. Sandbox: `would_execute`, policy=`handoff_operator` | Agent follow-up after handoff |
| 5 | `kerak emas rahmat` | No payload built. Sandbox: `blocked`, reason=`stop_signal` | Any further agent action for this user |

## Metrics to Monitor

Track these in the Control Center during DRY_RUN observation:

| Metric | What It Tells You | Expected Range | Hard Stop If |
|--------|-------------------|----------------|-------------|
| `dry_run_payloads_total` | Total payloads sandbox validated | Grows with traffic | 0 after 1h (pipeline broken) |
| `dry_run_would_execute` | Payloads that passed validation | 60-90% of total | 0 (nothing passing) |
| `dry_run_blocked` | Payloads sandbox rejected | 10-40% of total | >80% (policy too aggressive) |
| `dry_run_block_reasons` | Breakdown by reason (stop, cooldown, daily_cap, policy) | Varies | "unknown" reason appearing |
| `dry_run_action_types` | Breakdown by type (user_dm, admin_alert, followup) | Mostly user_dm | followup or escalation appearing |
| `sandbox_validation_errors` | Malformed payloads caught | 0 | >0 (payload construction bug) |
| `health_status` | Overall agent health | GREEN | RED |
| `live_sender_activity` | Real messages sent | 0 | >0 (critical — means sandbox bypassed) |
| `followup_pending_count` | Follow-ups in queue | 0 | >0 (follow-up flag leaked) |
| `executed_actions_count` | Real executed actions | 0 | >0 (sandbox not enforced) |

## Observation Window

- **First 30 min**: Active monitoring, check dashboard every 5 minutes
- **First 2 hours**: Check every 15 minutes
- **First 24 hours**: Check every 1-2 hours during business hours
- **After 24h**: Daily checklist (adapt doc 27 for DRY_RUN)

## PASS / FAIL Criteria

### PASS (all must be true)

- [ ] Health stayed GREEN for 24h
- [ ] Zero actual messages sent by agent (live_sender_activity = 0)
- [ ] Zero follow-ups scheduled (followup_pending_count = 0)
- [ ] Zero admin escalations
- [ ] Zero sandbox validation errors
- [ ] `would_execute` payloads look reasonable (spot-check 10+ traces)
- [ ] `blocked` reasons are correct (stop signals block, cooldowns block, etc.)
- [ ] Bot behavior unchanged for users
- [ ] No user complaints
- [ ] Dashboard activity visible and incrementing

### FAIL (any one triggers)

- Any real message sent by agent
- Any follow-up scheduled
- Health turns RED
- Sandbox validation errors > 0
- `would_execute` rate < 20% (agent blocks almost everything)
- `would_execute` rate > 95% (agent approves everything, no safety)
- `blocked` with reason "unknown"
- User complaint about changed behavior
- Bot errors or crashes

## Rollback

If any FAIL condition triggers:

1. **Apply OFF preset** (Control Center UI or API)
2. Verify dashboard stage: **OFF**
3. Verify health: **GREEN**
4. Restart if needed: `docker compose restart bot scheduler`
5. Report incident to admin group
6. File observation report with failure details

See `25_STAGE_1_ROLLBACK_CARD.md` and `29_EMERGENCY_ROLLBACK_OPERATOR_CARD.md` — the same rollback procedure applies.

## Next Step

After 24h DRY_RUN observation with PASS:
- File Stage 2 observation report (see `36_STAGE_2_DRY_RUN_OBSERVATION_TEMPLATE.md`)
- Review `would_execute` payloads with team
- Evaluate readiness for Stage 3 (Canary)
