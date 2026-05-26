# Stage 4 --- APPROVAL_REQUIRED Preparation

## What is APPROVAL_REQUIRED?

APPROVAL_REQUIRED mode is the first stage where the agent interacts with **all users** (not just canary accounts). However, the agent **never sends messages directly**. Instead, every proposed action enters a **persistent approval queue**. An admin reviews each proposal in the admin group and explicitly approves or rejects it. Only approved proposals are executed. Rejected and expired proposals are discarded silently.

Key differences from CANARY:

| Aspect | CANARY (Stage 3) | APPROVAL_REQUIRED (Stage 4) |
|--------|--------------------|-----------------------------|
| Signal extraction | Yes | Yes |
| Decision engine | Yes | Yes |
| Offer selection | Yes | Yes |
| Policy evaluation | Yes | Yes |
| Orchestrator | Full pipeline | Full pipeline |
| Execution payload | Built + validated | Built + validated |
| Sandbox validation | Active | Active |
| Target audience | Canary users only | **All users** |
| Approval queue | Off | **On --- persistent queue** |
| Admin notification | Off | **On --- admin group cards** |
| Admin approve/reject | N/A | **Required for every user DM** |
| Auto-send | Canary-controlled | **No --- admin must approve** |
| Expired proposals | N/A | **Silently discarded after TTL** |
| Follow-ups | Canary only | **Queued, require approval** |
| Metrics tracked | sent, delivered, blocked | proposed, approved, rejected, expired, blocked |

In APPROVAL_REQUIRED, the agent demonstrates its judgment to the admin team. The admin sees exactly what the agent wants to say and to whom, and decides whether to allow it. This is the last human-in-the-loop gate before autonomous sending.

## Prerequisites

All of these must be true before entering APPROVAL_REQUIRED:

- [ ] **Stage 3 completed** --- CANARY observation with PASS result
- [ ] **Stage 3 observation report** filed (see `41_STAGE_3_CANARY_OBSERVATION_TEMPLATE.md`)
- [ ] **Gate status**: READY (no RED or YELLOW blockers in readiness check)
- [ ] **Zero safety violations** during Stage 3 (no messages to non-canary users, no live sender activity)
- [ ] **Canary message quality reviewed** --- at least 10 delivered messages spot-checked, >= 80% judged correct
- [ ] **Stop signals verified** --- all stop signal scenarios passed in Stage 3
- [ ] **Health status**: GREEN
- [ ] **Approval queue infrastructure ready** --- queue table exists, API endpoints functional
- [ ] **Admin group configured** --- `AGENT_EXECUTION_APPROVAL_ADMIN_NOTIFY=true` target group verified
- [ ] **Admin(s) briefed** --- at least one admin knows the approve/reject flow, has tested inline buttons
- [ ] **All migrations applied**: `alembic upgrade head`
- [ ] **Bot smoke test passes**: `python -c "from apps.bot.main import build_dispatcher"`
- [ ] **Scheduler smoke test passes**: `python -c "import apps.scheduler.main"`
- [ ] **Unit tests pass**: `pytest tests/unit/ -q`
- [ ] **Simulation tests pass**: `pytest tests/simulation/ -q`
- [ ] **Control Center `/agent` loads** and shows correct stage
- [ ] **DB backup taken** before applying approval_required preset

## Required Flags (APPROVAL_REQUIRED Preset)

All of these must be `true` or set to the indicated value:

```
# Signal & Decision (carry forward from Stage 1+2+3)
AGENT_LEAD_SIGNAL_ENABLED=true
AGENT_LEAD_SCORING_ENABLED=true
AGENT_TEXT_NORMALIZATION_ENABLED=true
AGENT_FUZZY_INTENT_ENABLED=true
AGENT_DECISION_ENGINE_ENABLED=true

# Offer & Policy (carry forward from Stage 1+2+3)
AGENT_DYNAMIC_OFFER_ENABLED=true
AGENT_CONVERSATION_POLICY_ENABLED=true

# Orchestrator (carry forward from Stage 2+3)
AGENT_RESPONSE_ORCHESTRATOR_ENABLED=true
AGENT_RESPONSE_ORCHESTRATOR_LOG_ONLY=false
AGENT_RESPONSE_ORCHESTRATOR_TRACE_ENABLED=true

# Sandbox (carry forward, mode changes)
AGENT_EXECUTION_SANDBOX_ENABLED=true
AGENT_EXECUTION_MODE=approval_required
AGENT_EXECUTION_TRACE_ENABLED=true
AGENT_EXECUTION_MAX_DAILY_ACTIONS_PER_USER=3

# Approval queue (NEW for Stage 4)
AGENT_EXECUTION_QUEUE_ENABLED=true
AGENT_EXECUTION_APPROVAL_ADMIN_NOTIFY=true
AGENT_EXECUTION_APPROVAL_TTL_MINUTES=30
AGENT_EXECUTION_REQUIRE_APPROVAL_FOR_USER_DM=true
AGENT_EXECUTION_REQUIRE_APPROVAL_FOR_ADMIN_ALERT=false

# Follow-ups (carry forward from Stage 3, now for all users)
AGENT_FOLLOWUPS_ENABLED=true
AGENT_CATALOG_FOLLOWUP_ENABLED=true
AGENT_PRICE_FOLLOWUP_ENABLED=true
AGENT_ORDER_FOLLOWUP_ENABLED=true
AGENT_CATALOG_FOLLOWUP_DELAY_MINUTES=10
AGENT_PRICE_FOLLOWUP_DELAY_MINUTES=10
AGENT_ORDER_FOLLOWUP_DELAY_MINUTES=10
```

### Important notes on approval queue

- `AGENT_EXECUTION_QUEUE_ENABLED=true` activates the persistent proposal queue (Redis-backed or DB-backed, per implementation)
- `AGENT_EXECUTION_APPROVAL_ADMIN_NOTIFY=true` sends an inline keyboard card to the admin group for each proposed action
- `AGENT_EXECUTION_APPROVAL_TTL_MINUTES=30` means proposals expire automatically after 30 minutes if no admin acts
- `AGENT_EXECUTION_REQUIRE_APPROVAL_FOR_USER_DM=true` ensures every user-facing DM requires explicit admin approval
- `AGENT_EXECUTION_REQUIRE_APPROVAL_FOR_ADMIN_ALERT=false` allows internal admin alerts (e.g., hot lead notifications) to bypass the queue
- Admin approval cards contain: recipient user info, proposed message text, intent/signal summary, approve/reject inline buttons
- Follow-up delays are now at production values (10 minutes) since proposals queue rather than send directly

## Flags That MUST Remain False/Disabled

These flags are **forbidden** in Stage 4. If any is accidentally enabled, rollback immediately.

```
# Live sender --- must stay off (approved proposals go through sandbox-controlled send, not live sender)
AGENT_EXECUTION_LIVE_SENDER_ENABLED=false

# Auto-execute --- must stay off (admin must explicitly approve each proposal)
AGENT_EXECUTION_AUTO_EXECUTE_APPROVED=false

# Canary IDs --- must be empty (no longer restricting to canary; queue applies to all users)
AGENT_EXECUTION_CANARY_USER_IDS=

# AI composer --- must stay off (templates only, no AI-generated text)
AGENT_AI_COMPOSER_ENABLED=false
```

### Why live_sender and auto_execute MUST be false

- `AGENT_EXECUTION_LIVE_SENDER_ENABLED=false` ensures no message can be sent via the live send path. All sends go through the approval-controlled execution path.
- `AGENT_EXECUTION_AUTO_EXECUTE_APPROVED=false` ensures that even approved proposals do not auto-send via the batch sender. The approval-controlled execution path handles delivery immediately after admin approval, but the autonomous batch processing loop is disabled.

If either flag is found `true` during Stage 4, the admin-in-the-loop guarantee is broken. Rollback immediately.

## Apply Method

### Option A: Control Center UI (recommended)

1. Open `/agent` dashboard
2. Find "Rollout Presets" section
3. Click **Preview** on APPROVAL_REQUIRED
4. Review diff --- verify mode=approval_required, queue=ON, approval notify=ON, live sender OFF, auto-execute OFF, canary IDs empty
5. Verify no RED blockers
6. Click **Apply APPROVAL_REQUIRED**
7. Confirm in dialog

### Option B: API

```
POST /api/v1/admin/agent/settings/presets/approval_required/preview
POST /api/v1/admin/agent/settings/presets/approval_required/apply
{"confirmation_token": "<from preview>", "reason": "Stage 4 APPROVAL_REQUIRED trial"}
```

### Option C: .env (fallback)

Copy the Required Flags section above into `.env`, ensure all Forbidden Flags are explicitly `false` or empty, then restart bot + scheduler:

```bash
docker compose restart bot scheduler
```

## Post-Apply Verification

Immediately after applying the APPROVAL_REQUIRED preset:

- [ ] Dashboard stage shows: **APPROVAL_REQUIRED**
- [ ] Health: GREEN
- [ ] Sandbox: **ON**
- [ ] Execution mode: **approval_required**
- [ ] Queue: **ON**
- [ ] Approval admin notify: **ON**
- [ ] Approval TTL: **30 min**
- [ ] Require approval for user DM: **true**
- [ ] Orchestrator log_only: **false**
- [ ] Live sender: **OFF**
- [ ] Auto execute: **OFF**
- [ ] Canary IDs: **empty**
- [ ] AI composer: **OFF**
- [ ] Follow-ups enabled: **true**
- [ ] Follow-up delays: **10 min** (production values)

## Manual Test Scenarios (Quick Validation)

Run these immediately after applying. Use **any user account** (not restricted to canary). An admin must be available in the admin group to approve/reject.

| # | Action | Expected Result | Must NOT Happen |
|---|--------|-----------------|-----------------|
| 1 | User sends `narxi qancha` | Proposal appears in admin group with approve/reject buttons; user receives **nothing** until admin acts | Message auto-sent to user without approval |
| 2 | Admin clicks **Approve** on proposal from scenario 1 | User receives the price reply; proposal marked `approved` | Message sent before admin clicks approve |
| 3 | User sends `katalog ko'rsating`, admin clicks **Reject** | User receives **nothing**; proposal marked `rejected` | Message delivered despite rejection |
| 4 | User sends `20 kv qancha`, wait 31+ minutes without admin action | Proposal expires; user receives **nothing**; proposal marked `expired` | Message delivered after expiry |
| 5 | User sends `kerak emas` | Stop signal: no proposal created, no message queued, conversation closed | Proposal created for a stopped user |

## Metrics to Monitor

Track these in the Control Center during APPROVAL_REQUIRED observation:

| Metric | What It Tells You | Expected Range | Hard Stop If |
|--------|-------------------|----------------|-------------|
| `proposals_created` | Total proposals queued | Grows with user traffic | 0 after 1h (pipeline broken) |
| `proposals_approved` | Admin-approved proposals | Grows with admin activity | 0 after several proposals (admin not responding) |
| `proposals_rejected` | Admin-rejected proposals | Small count, acceptable | N/A (admin judgment) |
| `proposals_expired` | Proposals that hit TTL | Some expected (admin not always available) | Majority expiring (admin not engaged) |
| `proposals_blocked` | Proposals blocked before queue (stop, policy) | Normal range | N/A |
| `auto_sends_total` | Messages sent without approval | **0** | **>0 (critical --- approval bypass)** |
| `live_sender_activity` | Live sender module activity | **0** (must stay off) | **>0 (wrong send path active)** |
| `followup_proposals_created` | Follow-up proposals in queue | Grows after follow-up delays | N/A |
| `health_status` | Overall agent health | GREEN | RED |
| `stop_signals_honored` | Stop signals that blocked proposals | Grows with stop events | 0 after stop test (safety broken) |
| `approval_avg_response_time` | Time from proposal to admin action | < 15 min ideally | N/A (informational) |
| `sandbox_validation_errors` | Malformed payloads | 0 | >0 |

## Observation Window

- **First 30 minutes:** Active monitoring
  - Run manual test scenarios, check dashboard every 5 minutes
  - Verify proposals appear in admin group with correct content
  - Verify approve/reject flow works end-to-end
  - Verify expired proposals are discarded correctly
- **Next 2-4 hours:** Monitor real traffic
  - Admin reviews and acts on incoming proposals
  - Verify no messages sent without approval
  - Monitor queue depth (proposals should not pile up indefinitely)
  - Verify follow-up proposals appear after 10-minute delay
- **Post-test cool-down:** 30 minutes with no active testing
  - Verify no stale proposals auto-execute
  - Verify metrics stable
  - Verify health GREEN

## PASS / FAIL Criteria

### PASS (all must be true)

- [ ] Health stayed GREEN throughout observation
- [ ] Proposals created for user-facing actions (queue is working)
- [ ] Approved proposals resulted in correct message delivery
- [ ] Rejected proposals resulted in zero delivery
- [ ] Expired proposals resulted in zero delivery
- [ ] **Zero messages sent without admin approval** (auto_sends_total = 0)
- [ ] **Zero live sender module activity** (live_sender_activity = 0)
- [ ] Stop signals correctly prevented proposal creation
- [ ] Sandbox validation errors = 0
- [ ] No PII (phone numbers, tokens) in proposed or delivered message text
- [ ] No duplicate proposals for the same event
- [ ] Follow-up proposals created after correct delay
- [ ] Follow-up proposals also required approval (not auto-sent)
- [ ] Daily action cap respected (max 3 approved actions per user per day)
- [ ] Admin approval cards displayed correct information (user, intent, message preview)
- [ ] Bot remained stable (no crashes, no restarts needed)
- [ ] No user complaints

### FAIL (any one triggers immediate rollback)

- Any message sent to a user without admin approval
- Live sender flag found active
- Auto-execute flag found active
- Stop signal ignored (proposal created after "kerak emas")
- Health turns RED
- Sandbox validation errors > 0
- PII found in proposed or delivered message text
- Duplicate proposals for the same event
- Expired proposal delivered to user
- Rejected proposal delivered to user
- Bot crash or unrecoverable error
- Proposal content garbled or incorrect
- Follow-up auto-sent without entering the approval queue
- Daily cap exceeded

## Rollback

If any FAIL condition triggers:

1. **Apply OFF preset** (Control Center UI or API)

   ```
   POST /api/v1/admin/agent/settings/presets/off/apply
   {"reason": "Stage 4 APPROVAL_REQUIRED failure - <describe issue>"}
   ```

2. Verify dashboard stage: **OFF**
3. Verify health: **GREEN**
4. Verify all agent flags are at rollback defaults (see `19_AGENT_FLAGS_REFERENCE.md`)
5. Restart bot + scheduler:

   ```bash
   docker compose restart bot scheduler
   ```

6. Check for pending proposals in queue --- they should be marked as `expired` or `discarded` on rollback, but verify:

   ```
   proposals_pending_count: 0
   ```

7. Check for pending follow-ups --- they should be skipped automatically (stale check), but verify:

   ```
   followup_pending_count: 0
   ```

8. Report incident to admin group with:
   - What happened (which FAIL condition)
   - When it happened (timestamp)
   - Who was affected (which users had proposals in flight)
   - Whether any unapproved message was delivered (critical distinction)
   - Screenshots/traces if available
9. File observation report with failure details (see `46_STAGE_4_APPROVAL_REQUIRED_OBSERVATION_TEMPLATE.md`)

### Emergency one-liner (.env)

If Control Center is unreachable:

```
AGENT_RESPONSE_ORCHESTRATOR_ENABLED=false
AGENT_EXECUTION_SANDBOX_ENABLED=false
AGENT_EXECUTION_MODE=log_only
AGENT_EXECUTION_QUEUE_ENABLED=false
AGENT_EXECUTION_APPROVAL_ADMIN_NOTIFY=false
AGENT_FOLLOWUPS_ENABLED=false
AGENT_EXECUTION_CANARY_USER_IDS=
```

Then restart: `docker compose restart bot scheduler`

See also `25_STAGE_1_ROLLBACK_CARD.md` and `29_EMERGENCY_ROLLBACK_OPERATOR_CARD.md` for the full rollback procedure.

## Next Step

After APPROVAL_REQUIRED observation with PASS:
- File Stage 4 observation report (see `46_STAGE_4_APPROVAL_REQUIRED_OBSERVATION_TEMPLATE.md`)
- Review approved/rejected ratio with team (is the agent proposing quality actions?)
- Evaluate admin workload (is the approval volume sustainable?)
- Review expired proposals (are admins responding fast enough, or is TTL too short?)
- Consider enabling AI composer (`AGENT_AI_COMPOSER_ENABLED=true`) for personalized messages (sub-stage)
- Evaluate readiness for Stage 5 (Live / Auto-Execute)
