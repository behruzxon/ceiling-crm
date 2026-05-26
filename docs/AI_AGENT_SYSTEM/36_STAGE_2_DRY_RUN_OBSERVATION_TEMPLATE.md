# Stage 2 DRY_RUN Observation Report

```
Date: _______________
Time: ___ to ___
Environment: development / staging / production
Duration: _______________
Operator: _______________

============================================================
SECTION 1 — STAGE 1 GATE
============================================================

Stage 1 observation result: PASS / FAIL
Stage 1 report date: _______________
Stage 1 gate score: ___ (GREEN / YELLOW / RED)
Stage 1 duration: _______________
Stage 1 violations found: ___ (must be 0 to proceed)

============================================================
SECTION 2 — FLAGS SNAPSHOT
============================================================

Stage: DRY_RUN
Execution mode: dry_run

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
  AGENT_EXECUTION_MODE:                   ___           (must be dry_run)
  AGENT_EXECUTION_TRACE_ENABLED:          true / false

Forbidden flags (must all be false/off):
  AGENT_EXECUTION_LIVE_SENDER_ENABLED:    true / false  (must be false)
  AGENT_EXECUTION_AUTO_EXECUTE_APPROVED:  true / false  (must be false)
  AGENT_FOLLOWUPS_ENABLED:                true / false  (must be false)
  AGENT_CATALOG_FOLLOWUP_ENABLED:         true / false  (must be false)
  AGENT_PRICE_FOLLOWUP_ENABLED:           true / false  (must be false)
  AGENT_ORDER_FOLLOWUP_ENABLED:           true / false  (must be false)
  AGENT_ADMIN_ESCALATION_ENABLED:         true / false  (must be false)
  AGENT_EXECUTION_QUEUE_ENABLED:          true / false  (must be false)
  AGENT_AI_COMPOSER_ENABLED:              true / false  (must be false)

Flags verified correct: yes / no
If no, describe mismatch: ___

============================================================
SECTION 3 — DRY_RUN COUNTS (observation window)
============================================================

dry_run_payloads_total:       ___
dry_run_would_execute:        ___
dry_run_blocked:              ___
sandbox_validation_errors:    ___ (must be 0)

would_execute rate:           ___% (expected 60-90%)
blocked rate:                 ___% (expected 10-40%)

============================================================
SECTION 4 — WOULD_EXECUTE BREAKDOWN
============================================================

By action type:
  user_dm:                    ___
  admin_alert:                ___
  handoff:                    ___
  followup:                   ___ (should be 0 unless order-abandoned)
  other:                      ___

By detected intent:
  wants_price:                ___
  wants_catalog:              ___
  wants_measurement:          ___
  wants_order:                ___
  wants_operator:             ___
  wants_discount:             ___
  wants_info:                 ___
  negotiation (objection):    ___
  closing_attempt:            ___
  other/unclear:              ___

By lead temperature:
  hot:                        ___
  warm:                       ___
  cold:                       ___
  unknown:                    ___

Spot-check would_execute payloads (review at least 10):
  Payloads reviewed:          ___
  Payloads judged correct:    ___
  Payloads judged incorrect:  ___
  Notes on incorrect payloads:
    ___

============================================================
SECTION 5 — BLOCKED BREAKDOWN
============================================================

By block reason:
  stop_signal:                ___
  cooldown:                   ___
  rate_limit:                 ___
  daily_cap:                  ___
  low_confidence:             ___
  policy_denied:              ___
  pii_detected:               ___
  unknown:                    ___ (must be 0)

Spot-check blocked payloads (review at least 5):
  Blocks reviewed:            ___
  Blocks judged correct:      ___
  False positives (should not have blocked): ___
  Notes on false positives:
    ___

============================================================
SECTION 6 — SAFETY VIOLATIONS
============================================================

Messages actually sent by agent:       ___ (must be 0)
Follow-ups scheduled by agent:         ___ (must be 0)
Admin escalations triggered:           ___ (must be 0)
Approval queue items created:          ___ (must be 0)
PII found in payload text:             ___ (must be 0)
Tokens/keys found in traces:           ___ (must be 0)
User complaints received:              ___ (must be 0)
Bot behavior changes observed:         yes / no (must be no)

Total safety violations:               ___

If any violation > 0, describe:
  ___

============================================================
SECTION 7 — HEALTH & SYSTEM STATUS
============================================================

Health status at start of observation:  GREEN / YELLOW / RED
Health status at end of observation:    GREEN / YELLOW / RED
Health dipped to YELLOW during window:  yes / no
  If yes, timestamp:                    ___
  If yes, reason:                       ___
  If yes, duration:                     ___
  If yes, auto-resolved:               yes / no

Health turned RED during window:        yes / no
  If yes, timestamp:                    ___
  If yes, reason:                       ___
  If yes, action taken:                 ___

Bot uptime during window:               ___%
Scheduler uptime during window:         ___%
Bot errors in logs:                     ___
Scheduler errors in logs:               ___
Redis connectivity issues:              ___
Database connectivity issues:           ___

============================================================
SECTION 8 — PASS / FAIL DETERMINATION
============================================================

Overall result: PASS / FAIL

PASS criteria checklist (ALL must be checked to PASS):
  [ ] Health stayed GREEN throughout (YELLOW acceptable if documented and resolved)
  [ ] Zero messages actually sent by agent (live_sender_activity = 0)
  [ ] Zero follow-ups scheduled (followup_pending_count = 0)
  [ ] Zero admin escalations triggered
  [ ] Zero sandbox validation errors
  [ ] Zero unknown block reasons
  [ ] Zero PII or tokens in payload text
  [ ] Zero user complaints
  [ ] would_execute rate between 20% and 95%
  [ ] Spot-checked would_execute payloads are reasonable (>= 80% correct)
  [ ] Spot-checked blocked payloads are reasonable (>= 80% correct)
  [ ] Bot behavior unchanged for all users
  [ ] No bot or scheduler crashes

FAIL triggers (ANY one means FAIL):
  [ ] Agent sent a real message to a user
  [ ] Follow-up was scheduled
  [ ] Admin escalation fired
  [ ] Health turned RED (unresolved)
  [ ] Sandbox validation errors > 0
  [ ] Unknown block reason appeared
  [ ] PII or token found in payload text
  [ ] User complaint about changed bot behavior
  [ ] would_execute rate < 20% (agent blocks almost everything)
  [ ] would_execute rate > 95% (agent approves everything — no safety)
  [ ] Bot or scheduler crashed and did not auto-recover

============================================================
SECTION 9 — ISSUES FOUND
============================================================

Total issues found: ___

Issue 1:
  Severity: low / medium / high / critical
  Category: safety / accuracy / performance / stability / other
  Description: ___
  Impact: ___
  Action taken: ___
  Resolved: yes / no

Issue 2:
  Severity: low / medium / high / critical
  Category: safety / accuracy / performance / stability / other
  Description: ___
  Impact: ___
  Action taken: ___
  Resolved: yes / no

Issue 3:
  Severity: low / medium / high / critical
  Category: safety / accuracy / performance / stability / other
  Description: ___
  Impact: ___
  Action taken: ___
  Resolved: yes / no

(Add more as needed)

============================================================
SECTION 10 — NEXT ACTION RECOMMENDATION
============================================================

Recommended next step (select one):

  [ ] CONTINUE DRY_RUN — extend observation window
      Reason: ___
      Extended duration: ___

  [ ] ROLLBACK TO LOG_ONLY — revert to Stage 1 observation
      Reason: ___
      Issues to fix before re-attempting Stage 2: ___

  [ ] ROLLBACK TO OFF — disable agent entirely
      Reason: ___
      Critical issue description: ___

  [ ] PROCEED TO STAGE 3 (CANARY) — DRY_RUN passed, ready for limited live test
      Proposed canary user IDs: ___
      Proposed canary duration: ___
      Canary scope: user_dm only / user_dm + admin_alert / all actions
      Additional safety conditions for canary: ___

============================================================
SIGNATURES
============================================================

Prepared by:  _______________
Reviewed by:  _______________
Approved by:  _______________
Date:         _______________
```
