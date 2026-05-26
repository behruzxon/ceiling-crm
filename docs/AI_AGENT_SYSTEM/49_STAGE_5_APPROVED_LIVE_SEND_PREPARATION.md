# Stage 5 --- APPROVED_LIVE_SEND Preparation

## What is APPROVED_LIVE_SEND?

APPROVED_LIVE_SEND is the first stage where admin-approved payloads are delivered to real users via the Telegram Bot API. The agent pipeline runs in full --- signal extraction, decision engine, offer selection, policy evaluation, orchestrator, sandbox validation, and approval queue --- exactly as in Stage 4. The critical difference is that **approved proposals are now executed automatically** through the live sender module, delivering real Telegram messages to real users.

However, this is **NOT autonomous mode**. Every user-facing message still requires explicit admin approval before it is sent. The mode remains `approval_required`, not `live`. The live sender is simply the execution backend that delivers already-approved payloads via the real Telegram API.

Key differences from APPROVAL_REQUIRED (Stage 4):

| Aspect | APPROVAL_REQUIRED (Stage 4) | APPROVED_LIVE_SEND (Stage 5) |
|--------|-----------------------------|-----------------------------|
| Signal extraction | Yes | Yes |
| Decision engine | Yes | Yes |
| Offer selection | Yes | Yes |
| Policy evaluation | Yes | Yes |
| Orchestrator | Full pipeline | Full pipeline |
| Execution payload | Built + validated | Built + validated |
| Sandbox validation | Active | Active |
| Target audience | All users | All users |
| Approval queue | On | **On** |
| Admin approve/reject | Required for every user DM | **Required for every user DM** |
| Live sender module | **OFF** | **ON --- delivers approved payloads** |
| Auto-execute (batch) | OFF | **ON --- processes approved queue** |
| Send path | Approval-controlled (non-live) | **Real Telegram API via live sender** |
| Re-validation before send | N/A | **ON --- sandbox re-checks before send** |
| Failed send handling | N/A | **Marked failed, no retry** |
| Duplicate prevention | Queue-level dedup | **Queue + sender exactly-once guard** |
| Mode | approval_required | **approval_required (NOT live)** |
| Follow-ups | Queued, require approval | Queued, require approval |
| Metrics tracked | proposed, approved, rejected, expired, blocked | + **sent, delivered, failed, send_errors** |

In APPROVED_LIVE_SEND, the admin-in-the-loop guarantee is preserved. The only change is that the delivery mechanism is now the production Telegram Bot API. This is the last gate before fully autonomous sending.

## Prerequisites

All of these must be true before entering APPROVED_LIVE_SEND:

- [ ] **Stage 4 completed** --- APPROVAL_REQUIRED observation with PASS result
- [ ] **Stage 4 observation report** filed (see `46_STAGE_4_APPROVAL_REQUIRED_OBSERVATION_TEMPLATE.md`)
- [ ] **Gate status**: READY (no RED or YELLOW blockers in readiness check)
- [ ] **Zero safety violations** during Stage 4 (no messages sent without approval, no live sender activity, no auto-execute activity)
- [ ] **Admin approve rate reviewed** --- at least 70% of proposals approved during Stage 4 (demonstrates agent judgment quality)
- [ ] **Proposal content quality reviewed** --- at least 20 approved/delivered messages spot-checked, >= 90% judged correct
- [ ] **Expired proposal rate reviewed** --- fewer than 30% of proposals expired (demonstrates admin engagement)
- [ ] **Stop signals verified** --- all stop signal scenarios passed in Stage 4
- [ ] **No duplicate proposals or messages** in Stage 4 observation
- [ ] **allow_live_flags = true** --- operator or superadmin has explicitly unlocked live sender flags
- [ ] **Health status**: GREEN
- [ ] **Live sender infrastructure ready** --- sender module exists, revalidation logic functional, failed-send marking logic verified
- [ ] **Exactly-once delivery logic verified** --- idempotency key or dedup guard present in sender module
- [ ] **Admin group configured** --- `AGENT_EXECUTION_APPROVAL_ADMIN_NOTIFY=true` target group verified and responsive
- [ ] **Admin(s) briefed** --- at least one admin understands that approved proposals will now send via Telegram automatically
- [ ] **All migrations applied**: `alembic upgrade head`
- [ ] **Bot smoke test passes**: `python -c "from apps.bot.main import build_dispatcher"`
- [ ] **Scheduler smoke test passes**: `python -c "import apps.scheduler.main"`
- [ ] **Unit tests pass**: `pytest tests/unit/ -q`
- [ ] **Simulation tests pass**: `pytest tests/simulation/ -q`
- [ ] **Control Center `/agent` loads** and shows correct stage
- [ ] **DB backup taken** before applying approved_live_send preset
- [ ] **Redis backup/snapshot taken** before applying preset

## Required Flags (APPROVED_LIVE_SEND Preset)

All of these must be `true` or set to the indicated value:

```
# Signal & Decision (carry forward from Stage 1+2+3+4)
AGENT_LEAD_SIGNAL_ENABLED=true
AGENT_LEAD_SCORING_ENABLED=true
AGENT_TEXT_NORMALIZATION_ENABLED=true
AGENT_FUZZY_INTENT_ENABLED=true
AGENT_DECISION_ENGINE_ENABLED=true

# Offer & Policy (carry forward from Stage 1+2+3+4)
AGENT_DYNAMIC_OFFER_ENABLED=true
AGENT_CONVERSATION_POLICY_ENABLED=true

# Orchestrator (carry forward from Stage 2+3+4)
AGENT_RESPONSE_ORCHESTRATOR_ENABLED=true
AGENT_RESPONSE_ORCHESTRATOR_LOG_ONLY=false
AGENT_RESPONSE_ORCHESTRATOR_TRACE_ENABLED=true

# Sandbox (carry forward, MUST stay on)
AGENT_EXECUTION_SANDBOX_ENABLED=true
AGENT_EXECUTION_MODE=approval_required
AGENT_EXECUTION_TRACE_ENABLED=true
AGENT_EXECUTION_MAX_DAILY_ACTIONS_PER_USER=3

# Approval queue (carry forward from Stage 4)
AGENT_EXECUTION_QUEUE_ENABLED=true
AGENT_EXECUTION_APPROVAL_ADMIN_NOTIFY=true
AGENT_EXECUTION_APPROVAL_TTL_MINUTES=30
AGENT_EXECUTION_REQUIRE_APPROVAL_FOR_USER_DM=true
AGENT_EXECUTION_REQUIRE_APPROVAL_FOR_ADMIN_ALERT=false
AGENT_EXECUTION_API_APPROVAL_ENABLED=true

# Live sender (NEW for Stage 5)
AGENT_EXECUTION_LIVE_SENDER_ENABLED=true
AGENT_EXECUTION_AUTO_EXECUTE_APPROVED=true
AGENT_EXECUTION_LIVE_SENDER_BATCH_LIMIT=10
AGENT_EXECUTION_LIVE_SENDER_REVALIDATE=true
AGENT_EXECUTION_LIVE_SENDER_MARK_FAILED_ON_ERROR=true
AGENT_SETTINGS_ALLOW_LIVE_FLAGS=true

# Follow-ups (carry forward from Stage 3+4, production delays)
AGENT_FOLLOWUPS_ENABLED=true
AGENT_CATALOG_FOLLOWUP_ENABLED=true
AGENT_PRICE_FOLLOWUP_ENABLED=true
AGENT_ORDER_FOLLOWUP_ENABLED=true
AGENT_CATALOG_FOLLOWUP_DELAY_MINUTES=10
AGENT_PRICE_FOLLOWUP_DELAY_MINUTES=10
AGENT_ORDER_FOLLOWUP_DELAY_MINUTES=10
```

### Important notes on live sender

- `AGENT_EXECUTION_LIVE_SENDER_ENABLED=true` activates the real Telegram send path. Approved payloads are sent via the Bot API.
- `AGENT_EXECUTION_AUTO_EXECUTE_APPROVED=true` enables the batch sender loop that processes approved proposals from the queue. Without this, approved proposals sit idle after admin approval.
- `AGENT_EXECUTION_LIVE_SENDER_BATCH_LIMIT=10` caps the number of sends per scheduler tick, preventing burst overload on the Telegram API.
- `AGENT_EXECUTION_LIVE_SENDER_REVALIDATE=true` forces a second sandbox validation pass immediately before each send. This catches payloads that became invalid between approval and execution (e.g., user sent a stop signal after approval but before delivery).
- `AGENT_EXECUTION_LIVE_SENDER_MARK_FAILED_ON_ERROR=true` marks the proposal as `failed` if the Telegram API returns an error. No automatic retry --- failed sends require manual review.
- `AGENT_EXECUTION_API_APPROVAL_ENABLED=true` ensures the API approval endpoint is active so admin inline buttons can approve/reject proposals that flow into the live sender.
- `AGENT_SETTINGS_ALLOW_LIVE_FLAGS=true` is the top-level gate that unlocks the live sender and auto-execute flags. Without it, setting them to `true` has no effect.
- `AGENT_EXECUTION_MODE=approval_required` remains unchanged. The mode is **NOT** `live`. Every DM still requires admin approval. The live sender only executes proposals that have already been approved.
- Follow-up proposals continue to enter the approval queue and require admin approval before the live sender delivers them.

### Why mode MUST remain approval_required, NOT live

Setting `AGENT_EXECUTION_MODE=live` would bypass the approval queue entirely, allowing the agent to send messages autonomously without admin review. This is forbidden in Stage 5. The admin-in-the-loop guarantee must be preserved.

If `AGENT_EXECUTION_MODE` is found set to `live` during Stage 5, rollback immediately --- the approval gate is broken.

## Flags That MUST Remain False/Disabled

These flags are **forbidden** in Stage 5. If any is accidentally enabled or changed, rollback immediately.

```
# Mode --- must NOT be "live" (must remain "approval_required")
# AGENT_EXECUTION_MODE=live   <-- FORBIDDEN

# Canary IDs --- must be empty (queue applies to all users, not restricted to canary)
AGENT_EXECUTION_CANARY_USER_IDS=

# AI composer --- must stay off (templates only, no AI-generated text)
AGENT_AI_COMPOSER_ENABLED=false

# Sandbox --- must NOT be disabled (revalidation depends on sandbox)
# AGENT_EXECUTION_SANDBOX_ENABLED=false   <-- FORBIDDEN

# Revalidation --- must NOT be disabled (last safety check before real send)
# AGENT_EXECUTION_LIVE_SENDER_REVALIDATE=false   <-- FORBIDDEN

# Mark failed --- must NOT be disabled (failures must be recorded)
# AGENT_EXECUTION_LIVE_SENDER_MARK_FAILED_ON_ERROR=false   <-- FORBIDDEN
```

### Why these flags MUST stay off or unchanged

- **`AGENT_EXECUTION_MODE=live`** removes the approval requirement. Every DM would send without admin review. This destroys the human-in-the-loop guarantee.
- **`AGENT_AI_COMPOSER_ENABLED=false`** ensures only template-based messages are sent. AI-composed free-text messages add unpredictability that has not been validated in production sends.
- **`AGENT_EXECUTION_SANDBOX_ENABLED`** must be `true`. Disabling the sandbox removes payload validation. Malformed or dangerous payloads could reach real users via the live sender.
- **`AGENT_EXECUTION_LIVE_SENDER_REVALIDATE`** must be `true`. Disabling revalidation skips the final safety check before each send. A payload approved 20 minutes ago might target a user who has since sent "kerak emas" (stop signal). Revalidation catches this.
- **`AGENT_EXECUTION_LIVE_SENDER_MARK_FAILED_ON_ERROR`** must be `true`. Disabling this causes failed sends to be silently ignored, leaving proposals in an ambiguous state where they might be retried or lost without a trace.

## Apply Method

### Option A: Control Center UI (recommended)

1. Open `/agent` dashboard
2. Find "Rollout Presets" section
3. Click **Preview** on APPROVED_LIVE_SEND
4. Review diff --- verify:
   - mode = approval_required (NOT live)
   - queue = ON
   - approval notify = ON
   - api_approval = ON
   - live sender = ON
   - auto-execute approved = ON
   - revalidate = ON
   - mark failed on error = ON
   - sandbox = ON
   - allow_live_flags = true
   - canary IDs empty
   - AI composer OFF
5. Verify no RED blockers
6. Click **Apply APPROVED_LIVE_SEND**
7. Confirm in dialog

### Option B: API

```
POST /api/v1/admin/agent/settings/presets/approved_live_send/preview
POST /api/v1/admin/agent/settings/presets/approved_live_send/apply
{"confirmation_token": "<from preview>", "reason": "Stage 5 APPROVED_LIVE_SEND trial"}
```

### Option C: .env (fallback)

Copy the Required Flags section above into `.env`, ensure all Forbidden Flags are explicitly `false` or empty, then restart bot + scheduler:

```bash
docker compose restart bot scheduler
```

## Post-Apply Verification

Immediately after applying the APPROVED_LIVE_SEND preset:

- [ ] Dashboard stage shows: **APPROVED_LIVE_SEND**
- [ ] Health: GREEN
- [ ] Sandbox: **ON**
- [ ] Execution mode: **approval_required** (NOT live)
- [ ] Queue: **ON**
- [ ] Approval admin notify: **ON**
- [ ] API approval: **ON**
- [ ] Approval TTL: **30 min**
- [ ] Require approval for user DM: **true**
- [ ] Orchestrator log_only: **false**
- [ ] Live sender: **ON**
- [ ] Auto execute approved: **ON**
- [ ] Allow live flags: **true**
- [ ] Batch limit: **10**
- [ ] Revalidate before send: **ON**
- [ ] Mark failed on error: **ON**
- [ ] Canary IDs: **empty**
- [ ] AI composer: **OFF**
- [ ] Follow-ups enabled: **true**
- [ ] Follow-up delays: **10 min** (production values)

## Manual Test Scenarios (Quick Validation)

Run these immediately after applying. An admin must be available in the admin group to approve/reject.

| # | Action | Expected Result | Must NOT Happen |
|---|--------|-----------------|-----------------|
| 1 | User sends `narxi qancha` | Proposal appears in admin group; admin clicks Approve; **user receives price reply via Telegram** within seconds | Message sent before admin approves; message sent twice |
| 2 | User sends `katalog ko'rsating`, admin clicks **Reject** | User receives **nothing**; proposal marked `rejected`; live sender does NOT attempt delivery | Message delivered despite rejection |
| 3 | User sends `20 kv qancha`, wait 31+ minutes without admin action | Proposal expires; user receives **nothing**; live sender does NOT attempt delivery | Expired proposal delivered |
| 4 | User sends `kerak emas` | Stop signal: no proposal created; live sender has nothing to send | Proposal created or message sent to stopped user |
| 5 | Admin approves a proposal; then clicks Approve again | First approval delivers message; second click shows `already_approved`; **no duplicate message** | Duplicate message sent to user |
| 6 | Simulate Telegram API error (e.g., blocked bot) on approved proposal | Proposal marked `failed`; no retry; admin notified of failure | Infinite retry loop; silent failure without logging |
| 7 | User sends `telefon raqamim 901234567` | Proposal text contains acknowledgment WITHOUT raw phone number; if approved and sent, delivered message also has no phone | Phone number visible in proposal text or delivered message |
| 8 | User sends `zakaz beraman`, admin approves | Order CTA delivered via Telegram; exactly one message; `sent` counter increments by 1 | Multiple messages or counter mismatch |

## Metrics to Monitor

Track these in the Control Center during APPROVED_LIVE_SEND observation:

| Metric | What It Tells You | Expected Range | Hard Stop If |
|--------|-------------------|----------------|-------------|
| `proposals_created` | Total proposals queued | Grows with user traffic | 0 after 1h (pipeline broken) |
| `proposals_approved` | Admin-approved proposals | Grows with admin activity | 0 after several proposals |
| `proposals_rejected` | Admin-rejected proposals | Small count | N/A (admin judgment) |
| `proposals_expired` | Proposals that hit TTL | Some expected | Majority expiring |
| `proposals_blocked` | Proposals blocked before queue | Normal range | N/A |
| `sends_attempted` | Live sender attempted delivery | Matches `proposals_approved` | Mismatch with approved count |
| `sends_delivered` | Successfully delivered via Telegram | Close to `sends_attempted` | 0 after approved proposals exist |
| `sends_failed` | Telegram API errors on delivery | Low count acceptable | Rising trend |
| `send_errors` | Error detail categories from Telegram API | 0 ideally | Forbidden errors rising (bot blocked) |
| `duplicate_send_attempts` | Sender tried to deliver same proposal twice | **0** | **>0 (exactly-once broken)** |
| `unapproved_sends` | Messages sent without prior approval | **0** | **>0 (critical --- approval bypass)** |
| `revalidation_blocks` | Sends blocked by revalidation | Low count expected | N/A (safety working correctly) |
| `health_status` | Overall agent health | GREEN | RED |
| `stop_signals_honored` | Stop signals that blocked proposals | Grows with stop events | 0 after stop test |
| `sandbox_validation_errors` | Malformed payloads caught by sandbox | 0 | >0 |

## Observation Window

- **First 30 minutes:** Active monitoring
  - Run manual test scenarios, check dashboard every 5 minutes
  - Verify proposals appear in admin group with correct content
  - Verify approve flow results in real Telegram delivery
  - Verify reject/expire flow results in zero delivery
  - Verify exactly-once: no duplicate messages
  - Verify failed sends are marked and logged, not retried
- **Next 2-4 hours:** Monitor real traffic
  - Admin reviews and acts on incoming proposals
  - Verify every approved proposal results in exactly one delivered message
  - Monitor sends_failed for rising trends
  - Verify follow-up proposals appear after 10-minute delay and require approval
  - Verify revalidation catches stale approvals (e.g., user stopped after proposal was approved)
- **Post-test cool-down:** 30 minutes with no active testing
  - Verify no stale proposals auto-execute without approval
  - Verify no duplicate sends on already-delivered proposals
  - Verify metrics stable
  - Verify health GREEN

## PASS / FAIL Criteria

### PASS (all must be true)

- [ ] Health stayed GREEN throughout observation
- [ ] Proposals created for user-facing actions (queue is working)
- [ ] Approved proposals resulted in **exactly one** Telegram message delivery each
- [ ] Rejected proposals resulted in zero delivery
- [ ] Expired proposals resulted in zero delivery
- [ ] **Zero messages sent without admin approval** (unapproved_sends = 0)
- [ ] **Zero duplicate messages** (duplicate_send_attempts = 0)
- [ ] **Mode remained approval_required** (never changed to live)
- [ ] Stop signals correctly prevented proposal creation
- [ ] Revalidation blocked sends for users who stopped after approval
- [ ] Failed sends marked correctly, no infinite retry
- [ ] Sandbox validation errors = 0
- [ ] No PII (phone numbers, tokens) in proposed or delivered message text
- [ ] No duplicate proposals for the same event
- [ ] Follow-up proposals created after correct delay
- [ ] Follow-up proposals required approval and were delivered via live sender only after approval
- [ ] Daily action cap respected (max 3 approved + delivered actions per user per day)
- [ ] Admin approval cards displayed correct information
- [ ] Batch limit respected (max 10 sends per scheduler tick)
- [ ] Bot remained stable (no crashes, no restarts needed)
- [ ] No user complaints

### FAIL (any one triggers immediate rollback)

- Any message sent to a user without admin approval
- Mode found set to `live` (not `approval_required`)
- Sandbox disabled during observation
- Revalidation disabled during observation
- Duplicate message delivered to any user
- Stop signal ignored (proposal created after "kerak emas")
- Expired proposal delivered via live sender
- Rejected proposal delivered via live sender
- Failed send retried automatically (should be marked failed, not retried)
- Health turns RED
- Sandbox validation errors > 0
- PII found in proposed or delivered message text
- Duplicate proposals for the same event
- Bot crash or unrecoverable error
- Proposal content garbled or incorrect
- Follow-up auto-sent without entering the approval queue
- Daily cap exceeded
- Batch limit exceeded (more than 10 sends in a single scheduler tick)
- `sends_attempted` significantly diverges from `proposals_approved` (send path leak)

## Rollback

If any FAIL condition triggers:

1. **Apply OFF preset** (Control Center UI or API)

   ```
   POST /api/v1/admin/agent/settings/presets/off/apply
   {"reason": "Stage 5 APPROVED_LIVE_SEND failure - <describe issue>"}
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

7. Check for pending approved-but-unsent proposals --- these are the most critical. On rollback, the live sender is disabled, so approved proposals must NOT be delivered. Verify:

   ```
   approved_unsent_count: 0
   ```

   If any approved proposals are found pending delivery, they must be manually expired or discarded. The live sender being OFF prevents delivery, but the records should be cleaned up.

8. Check for pending follow-ups --- they should be skipped automatically (stale check), but verify:

   ```
   followup_pending_count: 0
   ```

9. Report incident to admin group with:
   - What happened (which FAIL condition)
   - When it happened (timestamp)
   - Who was affected (which users received or did not receive messages)
   - Whether any duplicate or unapproved message was delivered (critical distinction)
   - Whether any approved-but-unsent proposals exist
   - Screenshots/traces if available
10. File observation report with failure details (see `51_STAGE_5_APPROVED_LIVE_SEND_OBSERVATION_TEMPLATE.md`)

### Emergency one-liner (.env)

If Control Center is unreachable:

```
AGENT_RESPONSE_ORCHESTRATOR_ENABLED=false
AGENT_EXECUTION_SANDBOX_ENABLED=false
AGENT_EXECUTION_MODE=log_only
AGENT_EXECUTION_QUEUE_ENABLED=false
AGENT_EXECUTION_APPROVAL_ADMIN_NOTIFY=false
AGENT_EXECUTION_API_APPROVAL_ENABLED=false
AGENT_EXECUTION_LIVE_SENDER_ENABLED=false
AGENT_EXECUTION_AUTO_EXECUTE_APPROVED=false
AGENT_SETTINGS_ALLOW_LIVE_FLAGS=false
AGENT_FOLLOWUPS_ENABLED=false
AGENT_EXECUTION_CANARY_USER_IDS=
```

Then restart: `docker compose restart bot scheduler`

See also `25_STAGE_1_ROLLBACK_CARD.md` and `29_EMERGENCY_ROLLBACK_OPERATOR_CARD.md` for the full rollback procedure.

## Next Step

After APPROVED_LIVE_SEND observation with PASS:
- File Stage 5 observation report (see `51_STAGE_5_APPROVED_LIVE_SEND_OBSERVATION_TEMPLATE.md`)
- Review sends_delivered vs sends_failed ratio (is the Telegram delivery reliable?)
- Review admin approve rate and response time (is the admin bottleneck acceptable?)
- Review revalidation block rate (how many stale approvals were caught?)
- Review exactly-once metrics (any close calls or race conditions?)
- Consider enabling AI composer (`AGENT_AI_COMPOSER_ENABLED=true`) for personalized messages (sub-stage)
- Evaluate readiness for Stage 6 (Fully Autonomous / mode=live) based on sustained high approve rate (>= 90%)
