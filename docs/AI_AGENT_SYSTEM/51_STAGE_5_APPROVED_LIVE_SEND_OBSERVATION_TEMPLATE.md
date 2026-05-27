# Stage 5 APPROVED_LIVE_SEND Observation Report

```
Date: _______________
Time: ___ to ___
Environment: development / staging / production
Duration: _______________
Operator: _______________

============================================================
SECTION 1 --- STAGE 4 GATE
============================================================

Stage 4 observation result: PASS / FAIL
Stage 4 report date: _______________
Stage 4 gate score: ___ (GREEN / YELLOW / RED)
Stage 4 duration: _______________
Stage 4 proposals created (total): ___
Stage 4 proposals approved: ___
Stage 4 proposals rejected: ___
Stage 4 approve rate: ___% (must be >= 70% to proceed)
Stage 4 expired rate: ___% (must be < 30% to proceed)
Stage 4 unapproved sends: ___ (must have been 0)
Stage 4 safety violations: ___ (must be 0 to proceed)
Stage 4 message quality (spot-checked): ___% correct (must be >= 90%)
allow_live_flags explicitly unlocked: yes / no

============================================================
SECTION 2 --- APPROVED_LIVE_SEND CONFIGURATION
============================================================

Live sender infrastructure: ready / not ready
Exactly-once delivery logic: verified / not verified
Revalidation logic: verified / not verified
Failed-send marking logic: verified / not verified
Mock bot or test environment: available / not available
Admin group ID verified: yes / no
Admin(s) briefed on live delivery: yes / no (count: ___)
Approval TTL: ___ minutes
Batch limit: ___ per tick
Follow-ups enabled: yes / no
Follow-up delay: ___ minutes
DB backup taken: yes / no
Redis backup taken: yes / no

============================================================
SECTION 3 --- FLAGS SNAPSHOT
============================================================

Stage: APPROVED_LIVE_SEND
Execution mode: approval_required (NOT live)

Signal & Decision:
  AGENT_LEAD_SIGNAL_ENABLED:              true / false
  AGENT_LEAD_SCORING_ENABLED:             true / false
  AGENT_TEXT_NORMALIZATION_ENABLED:        true / false
  AGENT_FUZZY_INTENT_ENABLED:             true / false
  AGENT_FUZZY_MAX_DISTANCE:               ___
  AGENT_DECISION_ENGINE_ENABLED:          true / false
  AGENT_DECISION_MIN_CONFIDENCE:          ___

Offer & Policy:
  AGENT_DYNAMIC_OFFER_ENABLED:            true / false
  AGENT_DYNAMIC_OFFER_MIN_CONFIDENCE:     ___
  AGENT_CONVERSATION_POLICY_ENABLED:      true / false
  AGENT_CONVERSATION_POLICY_MIN_CONFIDENCE: ___

Orchestrator:
  AGENT_RESPONSE_ORCHESTRATOR_ENABLED:    true / false
  AGENT_RESPONSE_ORCHESTRATOR_LOG_ONLY:   true / false  (must be false)
  AGENT_RESPONSE_ORCHESTRATOR_MIN_CONFIDENCE: ___
  AGENT_RESPONSE_ORCHESTRATOR_TRACE_ENABLED: true / false

Sandbox:
  AGENT_EXECUTION_SANDBOX_ENABLED:        true / false  (must be true)
  AGENT_EXECUTION_MODE:                   ___           (must be approval_required)
  AGENT_EXECUTION_TRACE_ENABLED:          true / false
  AGENT_EXECUTION_MAX_DAILY_ACTIONS_PER_USER: ___

Approval Queue:
  AGENT_EXECUTION_QUEUE_ENABLED:          true / false  (must be true)
  AGENT_EXECUTION_APPROVAL_ADMIN_NOTIFY:  true / false  (must be true)
  AGENT_EXECUTION_APPROVAL_TTL_MINUTES:   ___           (default 30)
  AGENT_EXECUTION_API_APPROVAL_ENABLED:   true / false  (must be true)
  AGENT_EXECUTION_REQUIRE_APPROVAL_FOR_USER_DM:    true / false  (must be true)
  AGENT_EXECUTION_REQUIRE_APPROVAL_FOR_ADMIN_ALERT: true / false (must be false)

Live Sender (NEW for Stage 5):
  AGENT_EXECUTION_LIVE_SENDER_ENABLED:    true / false  (must be true)
  AGENT_EXECUTION_AUTO_EXECUTE_APPROVED:  true / false  (must be true)
  AGENT_EXECUTION_LIVE_SENDER_BATCH_LIMIT: ___          (default 10)
  AGENT_EXECUTION_LIVE_SENDER_REVALIDATE: true / false  (must be true)
  AGENT_EXECUTION_LIVE_SENDER_MARK_FAILED_ON_ERROR: true / false (must be true)
  AGENT_SETTINGS_ALLOW_LIVE_FLAGS:        true / false  (must be true)

Follow-ups:
  AGENT_FOLLOWUPS_ENABLED:                true / false
  AGENT_CATALOG_FOLLOWUP_ENABLED:         true / false
  AGENT_PRICE_FOLLOWUP_ENABLED:           true / false
  AGENT_ORDER_FOLLOWUP_ENABLED:           true / false
  AGENT_CATALOG_FOLLOWUP_DELAY_MINUTES:   ___
  AGENT_PRICE_FOLLOWUP_DELAY_MINUTES:     ___
  AGENT_ORDER_FOLLOWUP_DELAY_MINUTES:     ___

Forbidden flags (must all be false/off/empty):
  AGENT_EXECUTION_MODE:                   ___ (must NOT be "live")
  AGENT_EXECUTION_CANARY_USER_IDS:        set / empty   (must be empty)
  AGENT_AI_COMPOSER_ENABLED:              true / false  (must be false)

Flags verified correct: yes / no
If no, describe mismatch: ___

============================================================
SECTION 4 --- SCENARIO RESULTS
============================================================

Test script used: 50_STAGE_5_APPROVED_LIVE_SEND_TEST_SCRIPT.md

Section A (Approved Sends):
  Scenarios tested:          ___/8
  Scenarios passed:          ___
  Scenarios failed:          ___
  Failed scenario numbers:   ___

Section B (Rejected / Expired / Blocked):
  Scenarios tested:          ___/8
  Scenarios passed:          ___
  Scenarios failed:          ___
  Failed scenario numbers:   ___

Section C (Duplicate Prevention):
  Scenarios tested:          ___/4
  Scenarios passed:          ___
  Scenarios failed:          ___
  Failed scenario numbers:   ___

Section D (Token / Phone / Discount Blocked):
  Scenarios tested:          ___/5
  Scenarios passed:          ___
  Scenarios failed:          ___
  Failed scenario numbers:   ___

Section E (Failed Send Handling):
  Scenarios tested:          ___/3
  Scenarios passed:          ___
  Scenarios failed:          ___
  Failed scenario numbers:   ___

Section F (Mock Bot Verification):
  Scenarios tested:          ___/2
  Scenarios passed:          ___
  Scenarios failed:          ___
  Failed scenario numbers:   ___

Total scenarios:             ___/30
Total passed:                ___
Total failed:                ___

============================================================
SECTION 5 --- QUEUE METRICS
============================================================

proposals_created:           ___
proposals_approved:          ___
proposals_rejected:          ___
proposals_expired:           ___
proposals_blocked:           ___
proposals_pending:           ___ (at end of observation)

By action type:
  user_dm:                   ___
  handoff:                   ___
  follow_up:                 ___
  other:                     ___

By detected intent:
  wants_price:               ___
  wants_catalog:             ___
  wants_order:               ___
  wants_operator:            ___
  wants_discount:            ___
  negotiation (objection):   ___
  other:                     ___

Follow-up proposals:
  follow-up proposals created:   ___
  follow-up proposals approved:  ___
  follow-up proposals rejected:  ___
  follow-up proposals expired:   ___

============================================================
SECTION 6 --- SEND METRICS (CRITICAL)
============================================================

sends_attempted:             ___
sends_delivered:             ___
sends_failed:                ___
sends_delivered_rate:        ___% (sends_delivered / sends_attempted)

Send-to-approval match:
  proposals_approved:        ___
  sends_attempted:           ___
  match:                     yes / no (must match)
  if mismatch, delta:        ___
  if mismatch, explanation:  ___

By Telegram API result:
  200 OK (delivered):        ___
  403 Forbidden (blocked):   ___
  400 Bad Request:           ___
  429 Rate Limited:          ___
  Other errors:              ___

Failed sends detail:
  Total failed:              ___
  Retried automatically:     ___ (MUST be 0)
  Marked failed correctly:   ___
  failed_at timestamp set:   yes / no
  failed_reason recorded:    yes / no
  Admin notified of failures: yes / no

Batch processing:
  Max sends in single tick:  ___ (must be <= batch limit)
  Batch limit exceeded:      yes / no (must be no)
  Ticks with sends:          ___
  Average sends per tick:    ___

============================================================
SECTION 7 --- EXACTLY-ONCE VERIFICATION (CRITICAL)
============================================================

duplicate_send_attempts:     ___ (MUST be 0)

Dedup scenarios tested:
  Admin double-approve:      tested / not tested
    Result:                  pass / fail
    Duplicate sent:          yes / no (must be no)

  Sender double-process:     tested / not tested
    Result:                  pass / fail
    Duplicate sent:          yes / no (must be no)

  Duplicate user message:    tested / not tested
    Result:                  pass / fail
    Duplicate proposal:      yes / no (must be no)

  Bot restart mid-batch:     tested / not tested
    Result:                  pass / fail
    Duplicate sent:          yes / no (must be no)

Idempotency mechanism verified: yes / no
  Mechanism type: executed_at check / idempotency key / dedup token / other: ___

Total duplicate messages delivered: ___ (MUST be 0)

If any duplicate > 0, this is a CRITICAL FAILURE:
  Affected user ID(s) (masked): ___
  Duplicate message content (summarize): ___
  Timestamps of duplicates: ___
  Root cause (if determined): ___
  Immediate action taken: ___

============================================================
SECTION 8 --- REVALIDATION RESULTS
============================================================

Total revalidation checks:   ___
Revalidation passed:         ___
Revalidation blocked:        ___

By block reason:
  pii_detected (token):      ___
  pii_detected (phone):      ___
  unauthorized_discount:     ___
  unauthorized_urgency:      ___
  unauthorized_comparison:   ___
  stop_signal_after_approval: ___
  user_blocked_after_approval: ___
  payload_expired:           ___
  other:                     ___

Spot-check revalidation blocks (review at least 3):
  Blocks reviewed:           ___
  Blocks judged correct:     ___
  False positives (should not have blocked): ___
  Notes:
    ___

============================================================
SECTION 9 --- BLOCKED PROPOSALS (PRE-QUEUE)
============================================================

Total proposals blocked before queue:    ___

By block reason:
  stop_signal:               ___
  cooldown:                  ___
  rate_limit:                ___
  daily_cap:                 ___
  low_confidence:            ___
  policy_denied:             ___
  pii_detected:              ___
  unknown:                   ___ (must be 0)

Spot-check blocked proposals (review at least 3):
  Blocks reviewed:           ___
  Blocks judged correct:     ___
  False positives:           ___
  Notes:
    ___

============================================================
SECTION 10 --- SAFETY VIOLATIONS
============================================================

Messages sent without admin approval:    ___ (must be 0)
Mode changed to "live" during window:    yes / no (must be no)
Sandbox disabled during window:          yes / no (must be no)
Revalidation disabled during window:     yes / no (must be no)
Live sender module sent unapproved:      ___ (must be 0)
Auto-execute processed unapproved:       ___ (must be 0)
Follow-ups bypassing queue:              ___ (must be 0)
Expired proposals delivered:             ___ (must be 0)
Rejected proposals delivered:            ___ (must be 0)
Failed sends retried automatically:      ___ (must be 0)
Duplicate messages delivered:            ___ (must be 0)
Duplicate proposals for same event:      ___ (must be 0)
PII found in proposal text:              ___ (must be 0)
PII found in delivered message text:     ___ (must be 0)
Tokens/keys found in messages or traces: ___ (must be 0)
Stop signal ignored (proposal after stop): ___ (must be 0)
Daily cap exceeded for any user:         ___ (must be 0)
Batch limit exceeded in any tick:        ___ (must be 0)
sends_attempted > proposals_approved:    ___ (must be 0)
User complaints received:               ___ (must be 0)
Bot behavior change for non-interacting users: yes / no (must be no)

Total safety violations:                 ___

If any violation > 0, describe:
  ___

============================================================
SECTION 11 --- HEALTH & SYSTEM STATUS
============================================================

Health status at start of observation:   GREEN / YELLOW / RED
Health status at end of observation:     GREEN / YELLOW / RED
Health dipped to YELLOW during window:   yes / no
  If yes, timestamp:                     ___
  If yes, reason:                        ___
  If yes, duration:                      ___
  If yes, auto-resolved:                 yes / no

Health turned RED during window:         yes / no
  If yes, timestamp:                     ___
  If yes, reason:                        ___
  If yes, action taken:                  ___

Bot uptime during window:                ___%
Scheduler uptime during window:          ___%
Bot errors in logs:                      ___
Scheduler errors in logs:                ___
Redis connectivity issues:               ___
Database connectivity issues:            ___
Telegram API errors (non-send):          ___
Queue processing errors:                 ___
Live sender module errors:               ___
Batch sender loop errors:                ___

============================================================
SECTION 12 --- PASS / FAIL DETERMINATION
============================================================

Overall result: PASS / FAIL

PASS criteria checklist (ALL must be checked to PASS):
  [ ] Health stayed GREEN throughout (YELLOW acceptable if documented and resolved)
  [ ] Proposals created correctly for user-facing actions
  [ ] Approved proposals resulted in exactly one Telegram message delivery each
  [ ] Rejected proposals resulted in zero delivery
  [ ] Expired proposals resulted in zero delivery
  [ ] Zero messages sent without admin approval (unapproved_sends = 0)
  [ ] Zero duplicate messages delivered (duplicate_send_attempts = 0)
  [ ] Mode remained approval_required (never changed to live)
  [ ] Sandbox remained enabled throughout
  [ ] Revalidation remained enabled throughout
  [ ] Zero follow-ups bypassing the approval queue
  [ ] Zero failed sends retried automatically
  [ ] Failed sends marked with timestamp and reason
  [ ] Zero sandbox validation errors
  [ ] Zero unknown block reasons
  [ ] Zero PII or tokens in proposal text, delivered messages, or traces
  [ ] Zero stop signal violations (no proposal after stop)
  [ ] Daily cap enforced correctly
  [ ] Batch limit respected in every tick
  [ ] sends_attempted matches proposals_approved
  [ ] Revalidation blocked dangerous content after approval
  [ ] Admin approval cards displayed correct information
  [ ] No user complaints
  [ ] No bot or scheduler crashes
  [ ] Follow-up proposals entered queue and required approval before live send
  [ ] Re-approve did not cause duplicate delivery
  [ ] Post-reject approve was denied
  [ ] Bot restart did not cause duplicate delivery

FAIL triggers (ANY one means FAIL):
  [ ] Any message sent to a user without admin approval
  [ ] Mode found set to live (not approval_required)
  [ ] Sandbox disabled during observation
  [ ] Revalidation disabled during observation
  [ ] Duplicate message delivered to any user
  [ ] Follow-up bypassed approval queue
  [ ] Expired proposal delivered via live sender
  [ ] Rejected proposal delivered via live sender
  [ ] Failed send retried automatically
  [ ] Stop signal ignored (proposal created after stop)
  [ ] Health turned RED (unresolved)
  [ ] Sandbox validation errors > 0
  [ ] Unknown block reason appeared
  [ ] PII or token found in proposal, delivered message, or trace
  [ ] Duplicate proposals for same event
  [ ] Daily cap exceeded
  [ ] Batch limit exceeded
  [ ] sends_attempted diverges from proposals_approved
  [ ] Bot or scheduler crashed and did not auto-recover
  [ ] User complaint about changed bot behavior

============================================================
SECTION 13 --- ISSUES FOUND
============================================================

Total issues found: ___

Issue 1:
  Severity: low / medium / high / critical
  Category: safety / delivery / exactly-once / revalidation / send-failure / timing / queue / stability / other
  Description: ___
  Impact: ___
  Action taken: ___
  Resolved: yes / no

Issue 2:
  Severity: low / medium / high / critical
  Category: safety / delivery / exactly-once / revalidation / send-failure / timing / queue / stability / other
  Description: ___
  Impact: ___
  Action taken: ___
  Resolved: yes / no

Issue 3:
  Severity: low / medium / high / critical
  Category: safety / delivery / exactly-once / revalidation / send-failure / timing / queue / stability / other
  Description: ___
  Impact: ___
  Action taken: ___
  Resolved: yes / no

(Add more as needed)

============================================================
SECTION 14 --- NEXT ACTION RECOMMENDATION
============================================================

Recommended next step (select one):

  [ ] CONTINUE APPROVED_LIVE_SEND --- extend observation window
      Reason: ___
      Extended duration: ___
      Items to monitor: ___

  [ ] ADJUST CONFIGURATION --- tune batch limit, TTL, cap, or other parameters
      Reason: ___
      Parameter changes: ___

  [ ] ROLLBACK TO APPROVAL_REQUIRED (Stage 4) --- disable live sender, keep queue
      Reason: ___
      Issues to fix before re-attempting Stage 5: ___

  [ ] ROLLBACK TO OFF --- disable agent entirely
      Reason: ___
      Critical issue description: ___

  [ ] PROCEED TO STAGE 6 (LIMITED LIVE / AUTONOMOUS) --- remove approval requirement
      Proposed scope: all users / staged rollout
      Proposed mode: live
      Proposed daily cap: ___
      Proposed batch limit: ___
      Proposed duration: ___
      Admin approve rate during Stage 5: ___% (should be >= 90% to justify autonomy)
      Duplicate incidents during Stage 5: ___ (must be 0)
      Failed send rate during Stage 5: ___% (should be < 5%)
      Additional safety conditions for Stage 6: ___

============================================================
SIGNATURES
============================================================

Prepared by:  _______________
Reviewed by:  _______________
Approved by:  _______________
Date:         _______________
```
