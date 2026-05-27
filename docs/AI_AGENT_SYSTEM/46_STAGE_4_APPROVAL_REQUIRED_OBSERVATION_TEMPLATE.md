# Stage 4 APPROVAL_REQUIRED Observation Report

```
Date: _______________
Time: ___ to ___
Environment: development / staging / production
Duration: _______________
Operator: _______________

============================================================
SECTION 1 --- STAGE 3 GATE
============================================================

Stage 3 observation result: PASS / FAIL
Stage 3 report date: _______________
Stage 3 gate score: ___ (GREEN / YELLOW / RED)
Stage 3 duration: _______________
Stage 3 canary sends (total): ___
Stage 3 public sends: ___ (must have been 0)
Stage 3 safety violations: ___ (must be 0 to proceed)
Stage 3 message quality (spot-checked): ___% correct

============================================================
SECTION 2 --- APPROVAL_REQUIRED CONFIGURATION
============================================================

Queue infrastructure: ready / not ready
Admin group ID verified: yes / no
Admin(s) briefed and available: yes / no (count: ___)
Approval TTL: ___ minutes
Follow-ups enabled: yes / no
Follow-up delay: ___ minutes

============================================================
SECTION 3 --- FLAGS SNAPSHOT
============================================================

Stage: APPROVAL_REQUIRED
Execution mode: approval_required

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
  AGENT_EXECUTION_REQUIRE_APPROVAL_FOR_USER_DM:    true / false  (must be true)
  AGENT_EXECUTION_REQUIRE_APPROVAL_FOR_ADMIN_ALERT: true / false (must be false)

Follow-ups:
  AGENT_FOLLOWUPS_ENABLED:                true / false
  AGENT_CATALOG_FOLLOWUP_ENABLED:         true / false
  AGENT_PRICE_FOLLOWUP_ENABLED:           true / false
  AGENT_ORDER_FOLLOWUP_ENABLED:           true / false
  AGENT_CATALOG_FOLLOWUP_DELAY_MINUTES:   ___
  AGENT_PRICE_FOLLOWUP_DELAY_MINUTES:     ___
  AGENT_ORDER_FOLLOWUP_DELAY_MINUTES:     ___

Forbidden flags (must all be false/off/empty):
  AGENT_EXECUTION_LIVE_SENDER_ENABLED:    true / false  (must be false)
  AGENT_EXECUTION_AUTO_EXECUTE_APPROVED:  true / false  (must be false)
  AGENT_EXECUTION_CANARY_USER_IDS:        set / empty   (must be empty)
  AGENT_AI_COMPOSER_ENABLED:              true / false  (must be false)

Flags verified correct: yes / no
If no, describe mismatch: ___

============================================================
SECTION 4 --- SCENARIO RESULTS
============================================================

Test script used: 45_STAGE_4_APPROVAL_REQUIRED_TEST_SCRIPT.md

Section A (Proposal Creation):
  Scenarios tested:          ___/10
  Scenarios passed:          ___
  Scenarios failed:          ___
  Failed scenario numbers:   ___

Section B (Admin Approve/Reject):
  Scenarios tested:          ___/8
  Scenarios passed:          ___
  Scenarios failed:          ___
  Failed scenario numbers:   ___

Section C (Expiry Handling):
  Scenarios tested:          ___/3
  Scenarios passed:          ___
  Scenarios failed:          ___
  Failed scenario numbers:   ___

Section D (Non-Admin Rejection):
  Scenarios tested:          ___/1
  Scenarios passed:          ___
  Scenarios failed:          ___
  Failed scenario numbers:   ___

Section E (Blocked Payloads):
  Scenarios tested:          ___/4
  Scenarios passed:          ___
  Scenarios failed:          ___
  Failed scenario numbers:   ___

Section F (PII Safety):
  Scenarios tested:          ___/2
  Scenarios passed:          ___
  Scenarios failed:          ___
  Failed scenario numbers:   ___

Section G (No Auto-Send):
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

Spot-check proposal content (review at least 5 approved):
  Proposals reviewed:        ___
  Content judged correct:    ___
  Content judged incorrect:  ___
  Notes on incorrect proposals:
    ___

============================================================
SECTION 6 --- APPROVE/REJECT RESULTS
============================================================

Total admin approve actions:             ___
Total admin reject actions:              ___
Approve/reject ratio:                    ___:___

Approved --- message delivered:          ___
Approved --- delivery failed:            ___ (should be 0)
Rejected --- verified no delivery:       ___
Rejected --- message leaked anyway:      ___ (MUST be 0)

Re-approve attempts (already approved):  ___
Re-approve resulted in duplicate:        ___ (MUST be 0)

Post-reject approve attempts:            ___
Post-reject approve succeeded:           ___ (MUST be 0)

Non-admin approve attempts:              ___
Non-admin approve succeeded:             ___ (MUST be 0)

Admin avg response time:                 ___ min
Admin median response time:              ___ min
Fastest response:                        ___ min
Slowest response:                        ___ min

============================================================
SECTION 7 --- NO-SEND VERIFICATION (CRITICAL)
============================================================

Messages sent without admin approval:    ___ (MUST be 0)
Messages auto-executed by system:        ___ (MUST be 0)
Live sender module activity:             ___ (MUST be 0)
Follow-ups sent directly (bypassing queue): ___ (MUST be 0)
Expired proposals delivered:             ___ (MUST be 0)
Rejected proposals delivered:            ___ (MUST be 0)

Total unapproved sends:                 ___ (MUST be 0)

If any value > 0, this is a CRITICAL FAILURE:
  Affected user ID(s) (masked): ___
  Message content (summarize): ___
  Timestamp: ___
  Root cause (if determined): ___
  Immediate action taken: ___

============================================================
SECTION 8 --- BLOCKED PROPOSALS
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
  False positives (should not have blocked): ___
  Notes:
    ___

============================================================
SECTION 9 --- SAFETY VIOLATIONS
============================================================

Messages sent without admin approval:    ___ (must be 0)
Live sender module activity:             ___ (must be 0)
Auto-execute module activity:            ___ (must be 0)
Follow-ups bypassing queue:              ___ (must be 0)
Expired proposals delivered:             ___ (must be 0)
Rejected proposals delivered:            ___ (must be 0)
Non-admin successful approvals:          ___ (must be 0)
PII found in proposal text:             ___ (must be 0)
PII found in delivered message text:     ___ (must be 0)
Tokens/keys found in messages or traces: ___ (must be 0)
Duplicate messages to any user:          ___ (must be 0)
Duplicate proposals for same event:      ___ (must be 0)
Stop signal ignored (proposal after stop): ___ (must be 0)
Daily cap exceeded for any user:         ___ (must be 0)
User complaints received:               ___ (must be 0)
Bot behavior change for non-interacting users: yes / no (must be no)

Total safety violations:                 ___

If any violation > 0, describe:
  ___

============================================================
SECTION 10 --- HEALTH & SYSTEM STATUS
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
Telegram API errors:                     ___
Queue processing errors:                 ___

============================================================
SECTION 11 --- PASS / FAIL DETERMINATION
============================================================

Overall result: PASS / FAIL

PASS criteria checklist (ALL must be checked to PASS):
  [ ] Health stayed GREEN throughout (YELLOW acceptable if documented and resolved)
  [ ] Proposals created correctly for user-facing actions
  [ ] Approved proposals resulted in correct message delivery
  [ ] Rejected proposals resulted in zero delivery
  [ ] Expired proposals resulted in zero delivery
  [ ] Zero messages sent without admin approval (auto_sends_total = 0)
  [ ] Zero live sender module activity
  [ ] Zero auto-execute module activity
  [ ] Zero follow-ups bypassing the approval queue
  [ ] Zero non-admin successful approvals
  [ ] Zero sandbox validation errors
  [ ] Zero unknown block reasons
  [ ] Zero PII or tokens in proposal text or delivered messages
  [ ] Zero duplicate messages or proposals
  [ ] Zero stop signal violations (no proposal after stop)
  [ ] Daily cap enforced correctly
  [ ] Admin approval cards displayed correct information
  [ ] No user complaints
  [ ] No bot or scheduler crashes
  [ ] Follow-up proposals entered queue (not sent directly)
  [ ] Re-approve did not duplicate delivery
  [ ] Post-reject approve was denied

FAIL triggers (ANY one means FAIL):
  [ ] Any message sent to a user without admin approval
  [ ] Live sender flag found active
  [ ] Auto-execute flag found active
  [ ] Follow-up bypassed approval queue
  [ ] Expired proposal delivered
  [ ] Rejected proposal delivered
  [ ] Non-admin successfully approved a proposal
  [ ] Stop signal ignored (proposal created after stop)
  [ ] Health turned RED (unresolved)
  [ ] Sandbox validation errors > 0
  [ ] Unknown block reason appeared
  [ ] PII or token found in proposal or delivered message text
  [ ] Duplicate messages or duplicate proposals
  [ ] Daily cap exceeded
  [ ] Bot or scheduler crashed and did not auto-recover
  [ ] User complaint about changed bot behavior

============================================================
SECTION 12 --- ISSUES FOUND
============================================================

Total issues found: ___

Issue 1:
  Severity: low / medium / high / critical
  Category: safety / accuracy / delivery / timing / queue / authorization / stability / other
  Description: ___
  Impact: ___
  Action taken: ___
  Resolved: yes / no

Issue 2:
  Severity: low / medium / high / critical
  Category: safety / accuracy / delivery / timing / queue / authorization / stability / other
  Description: ___
  Impact: ___
  Action taken: ___
  Resolved: yes / no

Issue 3:
  Severity: low / medium / high / critical
  Category: safety / accuracy / delivery / timing / queue / authorization / stability / other
  Description: ___
  Impact: ___
  Action taken: ___
  Resolved: yes / no

(Add more as needed)

============================================================
SECTION 13 --- NEXT ACTION RECOMMENDATION
============================================================

Recommended next step (select one):

  [ ] CONTINUE APPROVAL_REQUIRED --- extend observation window
      Reason: ___
      Extended duration: ___
      Items to monitor: ___

  [ ] ADJUST CONFIGURATION --- tune TTL, cap, or other parameters
      Reason: ___
      Parameter changes: ___

  [ ] ROLLBACK TO CANARY --- revert to Stage 3 canary-only mode
      Reason: ___
      Issues to fix before re-attempting Stage 4: ___

  [ ] ROLLBACK TO OFF --- disable agent entirely
      Reason: ___
      Critical issue description: ___

  [ ] PROCEED TO STAGE 5 (LIVE / AUTO-EXECUTE) --- approval queue passed, ready for autonomous sending
      Proposed scope: all users / staged rollout
      Proposed daily cap: ___
      Proposed duration: ___
      Additional safety conditions for Stage 5: ___
      Admin approve rate during Stage 4: ___% (should be high to justify autonomy)

============================================================
SIGNATURES
============================================================

Prepared by:  _______________
Reviewed by:  _______________
Approved by:  _______________
Date:         _______________
```
