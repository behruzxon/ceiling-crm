# Stage 3 CANARY Observation Report

```
Date: _______________
Time: ___ to ___
Environment: development / staging / production
Duration: _______________
Operator: _______________

============================================================
SECTION 1 --- STAGE 2 GATE
============================================================

Stage 2 observation result: PASS / FAIL
Stage 2 report date: _______________
Stage 2 gate score: ___ (GREEN / YELLOW / RED)
Stage 2 duration: _______________
Stage 2 would_execute rate: ___%
Stage 2 safety violations: ___ (must be 0 to proceed)

============================================================
SECTION 2 --- CANARY CONFIGURATION
============================================================

Canary user count: ___
Canary user IDs (masked): C-***01, C-***02, ... (never write full IDs in report)
Canary users briefed: yes / no
Canary scope: user_dm only / user_dm + follow-ups / all actions

Phase A (follow-ups OFF) duration: ___
Phase B (follow-ups ON) duration: ___
Phase B enabled: yes / no

============================================================
SECTION 3 --- FLAGS SNAPSHOT
============================================================

Stage: CANARY
Execution mode: canary

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
  AGENT_EXECUTION_MODE:                   ___           (must be canary)
  AGENT_EXECUTION_TRACE_ENABLED:          true / false
  AGENT_EXECUTION_CANARY_USER_IDS:        set / empty   (must be set)
  AGENT_EXECUTION_MAX_DAILY_ACTIONS_PER_USER: ___

Follow-ups (Phase A / Phase B):
  AGENT_FOLLOWUPS_ENABLED:                true / false
  AGENT_CATALOG_FOLLOWUP_ENABLED:         true / false
  AGENT_PRICE_FOLLOWUP_ENABLED:           true / false
  AGENT_ORDER_FOLLOWUP_ENABLED:           true / false
  AGENT_CATALOG_FOLLOWUP_DELAY_MINUTES:   ___
  AGENT_PRICE_FOLLOWUP_DELAY_MINUTES:     ___
  AGENT_ORDER_FOLLOWUP_DELAY_MINUTES:     ___

Forbidden flags (must all be false/off):
  AGENT_EXECUTION_LIVE_SENDER_ENABLED:    true / false  (must be false)
  AGENT_EXECUTION_AUTO_EXECUTE_APPROVED:  true / false  (must be false)
  AGENT_ADMIN_ESCALATION_ENABLED:         true / false  (must be false)
  AGENT_EXECUTION_QUEUE_ENABLED:          true / false  (must be false)
  AGENT_EXECUTION_APPROVAL_ADMIN_NOTIFY:  true / false  (must be false)
  AGENT_AI_COMPOSER_ENABLED:              true / false  (must be false)

Flags verified correct: yes / no
If no, describe mismatch: ___

============================================================
SECTION 4 --- SCENARIO RESULTS
============================================================

Test script used: 40_STAGE_3_CANARY_TEST_SCRIPT.md

Phase A (follow-ups OFF):
  Scenarios tested:          ___/17
  Scenarios passed:          ___
  Scenarios failed:          ___
  Failed scenario numbers:   ___

Phase B (follow-ups ON):
  Scenarios tested:          ___/8
  Scenarios passed:          ___
  Scenarios failed:          ___
  Failed scenario numbers:   ___

Total scenarios:             ___/25
Total passed:                ___
Total failed:                ___

============================================================
SECTION 5 --- CANARY SEND COUNTS
============================================================

canary_sends_total:          ___
canary_sends_delivered:      ___
canary_sends_failed:         ___ (must be 0)

By action type:
  user_dm:                   ___
  handoff:                   ___
  follow_up:                 ___ (0 in Phase A)
  other:                     ___

By detected intent:
  wants_price:               ___
  wants_catalog:             ___
  wants_order:               ___
  wants_operator:            ___
  wants_discount:            ___
  negotiation (objection):   ___
  other:                     ___

Follow-up delivery (Phase B only):
  follow-ups scheduled:      ___
  follow-ups delivered:      ___
  follow-ups cancelled:      ___ (via stop signal)
  follow-up avg delay:       ___ seconds (expected ~60s)

Spot-check delivered messages (review at least 5):
  Messages reviewed:         ___
  Content judged correct:    ___
  Content judged incorrect:  ___
  Notes on incorrect messages:
    ___

============================================================
SECTION 6 --- PUBLIC SEND COUNT (CRITICAL)
============================================================

Messages sent to non-canary users:            ___ (MUST be 0)
Follow-ups sent to non-canary users:          ___ (MUST be 0)
Admin alerts sent to non-canary contexts:     ___ (MUST be 0)

Total public sends:                           ___ (MUST be 0)

If any value > 0, this is a CRITICAL FAILURE:
  Affected user ID(s) (masked): ___
  Message content (summarize): ___
  Timestamp: ___
  Root cause (if determined): ___
  Immediate action taken: ___

============================================================
SECTION 7 --- NON-CANARY BLOCKS
============================================================

Total non-canary pipeline runs:              ___
Non-canary blocked (reason: non_canary):     ___
Non-canary would_execute (sandbox only):     ___

Block rate for non-canary users:             ___% (must be 100% for sends)

By block reason:
  non_canary_user:           ___
  stop_signal:               ___
  cooldown:                  ___
  rate_limit:                ___
  daily_cap:                 ___
  low_confidence:            ___
  policy_denied:             ___
  unknown:                   ___ (must be 0)

============================================================
SECTION 8 --- CANARY BLOCKS
============================================================

Total canary actions blocked:                ___

By block reason:
  stop_signal:               ___
  daily_cap:                 ___
  cooldown:                  ___
  low_confidence:            ___
  policy_denied:             ___
  unknown:                   ___ (must be 0)

Spot-check canary blocks (review at least 3):
  Blocks reviewed:           ___
  Blocks judged correct:     ___
  False positives (should not have blocked): ___
  Notes:
    ___

============================================================
SECTION 9 --- SAFETY VIOLATIONS
============================================================

Messages sent to non-canary users:           ___ (must be 0)
Follow-ups sent to non-canary users:         ___ (must be 0)
Live sender module activity:                 ___ (must be 0)
Admin escalations triggered:                 ___ (must be 0)
Approval queue items created:                ___ (must be 0)
PII found in delivered message text:         ___ (must be 0)
Tokens/keys found in messages or traces:     ___ (must be 0)
Duplicate messages to canary users:          ___ (must be 0)
Follow-ups fired during Phase A:             ___ (must be 0)
Daily cap exceeded for any user:             ___ (must be 0)
User complaints received:                    ___ (must be 0)
Bot behavior change for non-canary users:    yes / no (must be no)
Stop signal ignored (send after stop):       ___ (must be 0)

Total safety violations:                     ___

If any violation > 0, describe:
  ___

============================================================
SECTION 10 --- HEALTH & SYSTEM STATUS
============================================================

Health status at start of observation:       GREEN / YELLOW / RED
Health status at end of observation:         GREEN / YELLOW / RED
Health dipped to YELLOW during window:       yes / no
  If yes, timestamp:                         ___
  If yes, reason:                            ___
  If yes, duration:                          ___
  If yes, auto-resolved:                     yes / no

Health turned RED during window:             yes / no
  If yes, timestamp:                         ___
  If yes, reason:                            ___
  If yes, action taken:                      ___

Bot uptime during window:                    ___%
Scheduler uptime during window:              ___%
Bot errors in logs:                          ___
Scheduler errors in logs:                    ___
Redis connectivity issues:                   ___
Database connectivity issues:                ___
Telegram API errors:                         ___

============================================================
SECTION 11 --- PASS / FAIL DETERMINATION
============================================================

Overall result: PASS / FAIL

PASS criteria checklist (ALL must be checked to PASS):
  [ ] Health stayed GREEN throughout (YELLOW acceptable if documented and resolved)
  [ ] Canary users received expected messages (content correct for >= 80% of sends)
  [ ] Zero messages sent to non-canary users (public_send_count = 0)
  [ ] Zero follow-ups sent to non-canary users (followup_sent_public = 0)
  [ ] Zero live sender module activity
  [ ] Zero admin escalations triggered
  [ ] Zero approval queue items created
  [ ] Zero sandbox validation errors
  [ ] Zero unknown block reasons
  [ ] Zero PII or tokens in delivered messages
  [ ] Zero duplicate messages
  [ ] Zero stop signal violations (no send after stop)
  [ ] Zero follow-ups during Phase A (if Phase A tested)
  [ ] Daily cap enforced correctly
  [ ] Stop signals correctly cancelled pending follow-ups (Phase B)
  [ ] Non-canary user experience completely unchanged
  [ ] No user complaints
  [ ] No bot or scheduler crashes
  [ ] Follow-up delays within tolerance (60s +/- 30s, Phase B)

FAIL triggers (ANY one means FAIL):
  [ ] Any message sent to a non-canary user
  [ ] Any follow-up sent to a non-canary user
  [ ] Stop signal ignored (agent sends after "kerak emas")
  [ ] Health turned RED (unresolved)
  [ ] Sandbox validation errors > 0
  [ ] Unknown block reason appeared
  [ ] PII or token found in delivered message text
  [ ] Duplicate messages to any user
  [ ] Live sender flag found active
  [ ] Follow-up fired during Phase A
  [ ] Daily cap exceeded
  [ ] Bot or scheduler crashed and did not auto-recover
  [ ] User complaint about changed bot behavior

============================================================
SECTION 12 --- ISSUES FOUND
============================================================

Total issues found: ___

Issue 1:
  Severity: low / medium / high / critical
  Category: safety / accuracy / delivery / timing / stability / other
  Description: ___
  Impact: ___
  Action taken: ___
  Resolved: yes / no

Issue 2:
  Severity: low / medium / high / critical
  Category: safety / accuracy / delivery / timing / stability / other
  Description: ___
  Impact: ___
  Action taken: ___
  Resolved: yes / no

Issue 3:
  Severity: low / medium / high / critical
  Category: safety / accuracy / delivery / timing / stability / other
  Description: ___
  Impact: ___
  Action taken: ___
  Resolved: yes / no

(Add more as needed)

============================================================
SECTION 13 --- NEXT ACTION RECOMMENDATION
============================================================

Recommended next step (select one):

  [ ] CONTINUE CANARY --- extend observation window or expand canary pool
      Reason: ___
      Extended duration: ___
      Additional canary users: ___

  [ ] ROLLBACK TO DRY_RUN --- revert to Stage 2 sandbox-only mode
      Reason: ___
      Issues to fix before re-attempting Stage 3: ___

  [ ] ROLLBACK TO OFF --- disable agent entirely
      Reason: ___
      Critical issue description: ___

  [ ] PROCEED TO STAGE 4 (APPROVAL_REQUIRED) --- canary passed, ready for admin approval queue
      Proposed scope: all users / staged rollout
      Proposed duration: ___
      Additional safety conditions for Stage 4: ___

============================================================
SIGNATURES
============================================================

Prepared by:  _______________
Reviewed by:  _______________
Approved by:  _______________
Date:         _______________
```
