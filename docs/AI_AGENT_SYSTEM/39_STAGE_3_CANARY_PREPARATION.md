# Stage 3 --- CANARY Preparation

## What is CANARY?

CANARY mode is the first stage where the agent sends **real messages** to real Telegram users. Unlike DRY_RUN, the execution pipeline is no longer simulated --- approved payloads are delivered via the Telegram Bot API. However, sends are restricted to a **whitelist of canary test users** (admin Telegram IDs). Every non-canary user continues to receive DRY_RUN treatment (payload built and validated, but never sent).

Key differences from DRY_RUN:

| Aspect | DRY_RUN (Stage 2) | CANARY (Stage 3) |
|--------|--------------------|--------------------|
| Signal extraction | Yes | Yes |
| Decision engine | Yes | Yes |
| Offer selection | Yes | Yes |
| Policy evaluation | Yes | Yes |
| Orchestrator | Full pipeline | Full pipeline |
| Execution payload | Built + validated | Built + validated |
| Sandbox validation | Active | Active |
| Actual send | No | **Yes --- canary users only** |
| Non-canary behavior | `would_execute` / `blocked` | `would_execute` / `blocked` (unchanged) |
| Follow-ups | Not scheduled | **Scheduled for canary users only** |
| Metrics tracked | would_execute, blocked | sent, delivered, blocked, follow_up_sent |

In CANARY, you are testing the full production path end-to-end with a controlled audience. If anything goes wrong, only canary users (your own admin accounts) are affected.

## Prerequisites

All of these must be true before entering CANARY:

- [ ] **Stage 2 completed** --- at least 24h DRY_RUN observation with PASS result
- [ ] **Stage 2 observation report** filed (see `36_STAGE_2_DRY_RUN_OBSERVATION_TEMPLATE.md`)
- [ ] **Gate status**: READY (no RED or YELLOW blockers in readiness check)
- [ ] **Zero safety violations** during Stage 2 (no real sends, no follow-ups, no escalations)
- [ ] **would_execute payloads reviewed** --- at least 10 spot-checked, >= 80% judged correct
- [ ] **blocked payloads reviewed** --- at least 5 spot-checked, >= 80% judged correct
- [ ] **Health status**: GREEN
- [ ] **Canary user IDs selected** --- 1-3 admin Telegram IDs, documented
- [ ] **Canary users briefed** --- they know the bot will send real messages, they know to test stop signals
- [ ] **All migrations applied**: `alembic upgrade head`
- [ ] **Bot smoke test passes**: `python -c "from apps.bot.main import build_dispatcher"`
- [ ] **Scheduler smoke test passes**: `python -c "import apps.scheduler.main"`
- [ ] **Unit tests pass**: `pytest tests/unit/ -q`
- [ ] **Simulation tests pass**: `pytest tests/simulation/ -q`
- [ ] **Control Center `/agent` loads** and shows correct stage
- [ ] **DB backup taken** before applying canary preset

## Required Flags (CANARY Preset)

All of these must be `true` or set to the indicated value:

```
# Signal & Decision (carry forward from Stage 1+2)
AGENT_LEAD_SIGNAL_ENABLED=true
AGENT_LEAD_SCORING_ENABLED=true
AGENT_TEXT_NORMALIZATION_ENABLED=true
AGENT_FUZZY_INTENT_ENABLED=true
AGENT_DECISION_ENGINE_ENABLED=true

# Offer & Policy (carry forward from Stage 1+2)
AGENT_DYNAMIC_OFFER_ENABLED=true
AGENT_CONVERSATION_POLICY_ENABLED=true

# Orchestrator (carry forward from Stage 2)
AGENT_RESPONSE_ORCHESTRATOR_ENABLED=true
AGENT_RESPONSE_ORCHESTRATOR_LOG_ONLY=false
AGENT_RESPONSE_ORCHESTRATOR_TRACE_ENABLED=true

# Sandbox (carry forward from Stage 2, mode changes)
AGENT_EXECUTION_SANDBOX_ENABLED=true
AGENT_EXECUTION_MODE=canary
AGENT_EXECUTION_TRACE_ENABLED=true

# Canary whitelist (NEW for Stage 3)
AGENT_EXECUTION_CANARY_USER_IDS=<admin1_id>,<admin2_id>
AGENT_EXECUTION_MAX_DAILY_ACTIONS_PER_USER=3
```

### Important notes on canary IDs

- `AGENT_EXECUTION_CANARY_USER_IDS` must contain **numeric Telegram user IDs**, comma-separated, no spaces
- These should be admin or team member accounts --- never real customer IDs
- If this list is empty while mode is `canary`, **no messages will be sent** (safe default)
- Example: `AGENT_EXECUTION_CANARY_USER_IDS=123456789,987654321`

## Flags That MUST Remain False/Disabled

These flags are **forbidden** in Stage 3. If any is accidentally enabled, rollback immediately.

```
# Live sender --- must stay off (canary uses sandbox-controlled send path)
AGENT_EXECUTION_LIVE_SENDER_ENABLED=false

# Auto-execute --- must stay off (canary handles execution internally)
AGENT_EXECUTION_AUTO_EXECUTE_APPROVED=false

# Approval queue --- must stay off (not needed until Stage 4)
AGENT_EXECUTION_QUEUE_ENABLED=false
AGENT_EXECUTION_APPROVAL_ADMIN_NOTIFY=false

# Admin escalation --- must stay off
AGENT_ADMIN_ESCALATION_ENABLED=false

# AI composer --- must stay off (templates only, no AI-generated text)
AGENT_AI_COMPOSER_ENABLED=false
```

### Follow-up flags: Initially OFF, then selectively enabled

Follow-ups are enabled in two phases during canary testing:

**Phase A (first 1-2 hours) --- Follow-ups OFF:**

```
AGENT_FOLLOWUPS_ENABLED=false
AGENT_CATALOG_FOLLOWUP_ENABLED=false
AGENT_PRICE_FOLLOWUP_ENABLED=false
AGENT_ORDER_FOLLOWUP_ENABLED=false
```

Run the core test scenarios (price queries, objections, stop signals) without follow-ups. Verify that canary users receive direct responses correctly and non-canary users remain unaffected.

**Phase B (after Phase A passes) --- Follow-ups ON for canary:**

```
AGENT_FOLLOWUPS_ENABLED=true
AGENT_CATALOG_FOLLOWUP_ENABLED=true
AGENT_PRICE_FOLLOWUP_ENABLED=true
AGENT_ORDER_FOLLOWUP_ENABLED=true
AGENT_CATALOG_FOLLOWUP_DELAY_MINUTES=1
AGENT_PRICE_FOLLOWUP_DELAY_MINUTES=1
AGENT_ORDER_FOLLOWUP_DELAY_MINUTES=1
```

Follow-up delays are set to 1 minute (not the production 10 minutes) so you can observe the full cycle quickly. Follow-ups are only delivered to canary user IDs; non-canary follow-ups remain in `would_execute` state.

## Apply Method

### Option A: Control Center UI (recommended)

1. Open `/agent` dashboard
2. Find "Rollout Presets" section
3. Click **Preview** on CANARY
4. Review diff --- verify mode=canary, canary IDs set, live sender OFF, auto-execute OFF
5. Verify no RED blockers
6. Click **Apply CANARY**
7. Confirm in dialog

### Option B: API

```
POST /api/v1/admin/agent/settings/presets/canary/preview
POST /api/v1/admin/agent/settings/presets/canary/apply
{"confirmation_token": "<from preview>", "reason": "Stage 3 CANARY trial"}
```

### Option C: .env (fallback)

Copy the Required Flags section above into `.env`, ensure all Forbidden Flags are explicitly `false`, replace `<admin1_id>,<admin2_id>` with actual Telegram IDs, then restart bot + scheduler:

```bash
docker compose restart bot scheduler
```

## Post-Apply Verification

Immediately after applying the CANARY preset:

- [ ] Dashboard stage shows: **CANARY**
- [ ] Health: GREEN
- [ ] Sandbox: **ON**
- [ ] Execution mode: **canary**
- [ ] Canary user IDs: visible in dashboard, count matches expected
- [ ] Orchestrator log_only: **false**
- [ ] Live sender: **OFF**
- [ ] Auto execute: **OFF**
- [ ] Approval queue: **OFF**
- [ ] Admin escalation: **OFF**
- [ ] AI composer: **OFF**
- [ ] Follow-ups enabled: **false** (Phase A) or **true** (Phase B)

## Manual Test Scenarios (Quick Validation)

Run these from a **canary user account** immediately after applying. Each must produce a real Telegram message to the canary user.

| # | You Send (as canary) | Expected Result | Must NOT Happen |
|---|----------------------|-----------------|-----------------|
| 1 | `25 kv qancha turadi` | Real price reply delivered to your DM | Non-canary user gets a message |
| 2 | `qimmat ekan` | Negotiation tactic delivered to your DM | Follow-up scheduled (Phase A) |
| 3 | `operator kerak` | Handoff action --- no agent follow-up | Agent sends further messages |
| 4 | `kerak emas` | Stop signal --- no message sent, conversation closed | Any further agent action |
| 5 | (from non-canary account) `narxi qancha` | Sandbox: `would_execute` only, no real send | Real message to non-canary user |

## Metrics to Monitor

Track these in the Control Center during CANARY observation:

| Metric | What It Tells You | Expected Range | Hard Stop If |
|--------|-------------------|----------------|-------------|
| `canary_sends_total` | Real messages sent to canary users | Grows with test actions | 0 after 30 min (send path broken) |
| `canary_sends_delivered` | Successfully delivered | Should equal sends_total | Significantly less (delivery issues) |
| `canary_sends_failed` | Delivery failures to canary users | 0 | >2 (API or user issue) |
| `dry_run_would_execute` | Non-canary payloads validated | Grows with real traffic | N/A |
| `dry_run_blocked` | Non-canary payloads blocked | Normal range | N/A |
| `public_send_count` | Messages sent to NON-canary users | **0** | **>0 (critical --- canary filter bypassed)** |
| `followup_sent_canary` | Follow-ups delivered to canary (Phase B) | 0 (Phase A), grows (Phase B) | Grows during Phase A |
| `followup_sent_public` | Follow-ups to non-canary users | **0** | **>0 (critical --- canary filter bypassed)** |
| `sandbox_validation_errors` | Malformed payloads | 0 | >0 |
| `health_status` | Overall agent health | GREEN | RED |
| `live_sender_activity` | Live sender module activity | **0** (must stay off) | **>0 (wrong send path active)** |
| `stop_signals_honored` | Stop signals that blocked further action | Grows with stop tests | 0 after stop test (safety broken) |

## Observation Window

- **Phase A (follow-ups OFF):** 1-2 hours active monitoring
  - First 15 min: run manual test scenarios, check dashboard every 5 minutes
  - Next 45 min: monitor real traffic, verify non-canary isolation
  - If no issues: proceed to Phase B
- **Phase B (follow-ups ON):** 2-4 hours
  - First 15 min: trigger follow-up scenarios from canary account, verify delivery
  - Next 1-2h: monitor follow-up delivery, verify non-canary blocked
  - Verify stop signals cancel pending follow-ups
- **Post-test cool-down:** 30 minutes with no active testing
  - Verify no stale follow-ups fire
  - Verify metrics stable
  - Verify health GREEN

## PASS / FAIL Criteria

### PASS (all must be true)

- [ ] Health stayed GREEN throughout observation
- [ ] Canary users received expected messages (spot-check content correctness)
- [ ] **Zero messages sent to non-canary users** (public_send_count = 0)
- [ ] **Zero follow-ups sent to non-canary users** (followup_sent_public = 0)
- [ ] Stop signals correctly blocked all further agent actions
- [ ] Sandbox validation errors = 0
- [ ] No PII (phone numbers, tokens) in delivered message text
- [ ] No duplicate messages to canary users
- [ ] Non-canary users experienced zero behavior change
- [ ] No user complaints
- [ ] Bot remained stable (no crashes, no restarts needed)
- [ ] Follow-ups delivered correctly in Phase B (if tested)
- [ ] Follow-up delays respected (1 min +/- 30s tolerance)
- [ ] Daily action cap respected (max 3 per canary user per day)

### FAIL (any one triggers immediate rollback)

- Any message sent to a non-canary user
- Any follow-up sent to a non-canary user
- Stop signal ignored (agent continues after "kerak emas")
- Health turns RED
- Sandbox validation errors > 0
- PII found in delivered message text
- Duplicate messages sent
- Live sender flag found active
- Bot crash or unrecoverable error
- Canary user receives garbled or incorrect content
- Follow-up fires during Phase A (when follow-ups should be OFF)
- Daily cap exceeded for a canary user

## Rollback

If any FAIL condition triggers:

1. **Apply OFF preset** (Control Center UI or API)

   ```
   POST /api/v1/admin/agent/settings/presets/off/apply
   {"reason": "Stage 3 CANARY failure - <describe issue>"}
   ```

2. Verify dashboard stage: **OFF**
3. Verify health: **GREEN**
4. Verify all agent flags are at rollback defaults (see `19_AGENT_FLAGS_REFERENCE.md`)
5. Restart bot + scheduler:

   ```bash
   docker compose restart bot scheduler
   ```

6. Check for pending follow-ups --- they should be skipped automatically (stale check), but verify:

   ```
   followup_pending_count: 0
   ```

7. Report incident to admin group with:
   - What happened (which FAIL condition)
   - When it happened (timestamp)
   - Who was affected (canary only, or non-canary --- critical distinction)
   - Screenshots/traces if available
8. File observation report with failure details (see `41_STAGE_3_CANARY_OBSERVATION_TEMPLATE.md`)

### Emergency one-liner (.env)

If Control Center is unreachable:

```
AGENT_RESPONSE_ORCHESTRATOR_ENABLED=false
AGENT_EXECUTION_SANDBOX_ENABLED=false
AGENT_EXECUTION_MODE=log_only
AGENT_FOLLOWUPS_ENABLED=false
AGENT_EXECUTION_CANARY_USER_IDS=
```

Then restart: `docker compose restart bot scheduler`

See also `25_STAGE_1_ROLLBACK_CARD.md` and `29_EMERGENCY_ROLLBACK_OPERATOR_CARD.md` for the full rollback procedure.

## Next Step

After CANARY observation with PASS:
- File Stage 3 observation report (see `41_STAGE_3_CANARY_OBSERVATION_TEMPLATE.md`)
- Review delivered messages with team (content quality, timing, relevance)
- Evaluate readiness for Stage 4 (Approval Required)
- Consider expanding canary pool if additional confidence is needed before Stage 4
