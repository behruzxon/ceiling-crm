# Stage 3 (CANARY) Test Script

Step-by-step test script to verify Stage 3 CANARY is working correctly. Run this after applying the CANARY preset.

## Prerequisites

- Stage is set to **CANARY** (verify in dashboard)
- Health status is **GREEN**
- Sandbox is **ON**
- Execution mode is **canary**
- Canary user IDs are configured and visible in dashboard
- Live Sender is **OFF**
- Auto Execute is **OFF**
- Stage 2 observation report filed with PASS result
- You have at least one **canary** Telegram account (listed in `AGENT_EXECUTION_CANARY_USER_IDS`)
- You have at least one **non-canary** Telegram account (NOT listed in canary IDs)
- Follow-ups are **OFF** for scenarios 1-17 (Phase A), then **ON** for scenarios 18-25 (Phase B)

## How to Run Each Test

1. Identify which account to use: **canary** or **non-canary** (column 2)
2. Send the message from the correct Telegram account to the bot
3. For canary tests: verify a **real message** is delivered (or correctly blocked)
4. For non-canary tests: verify **no real message** is sent (sandbox only)
5. Open the Control Center dashboard and check execution traces
6. Verify all Expected columns match
7. Mark Pass or Fail

---

## Test Scenarios

### Phase A --- Core Tests (follow-ups OFF)

| # | User Type | Input / Action | Expected Signal | Expected Sandbox | Expected Send / No-Send | Pass/Fail |
|---|-----------|----------------|-----------------|------------------|------------------------|-----------|
| 1 | canary | `narxi qancha` | intent: `wants_price` | `approved`, action: `user_dm` | **SEND** --- canary receives price reply in DM | |
| 2 | canary | `20 kv qancha turadi` | intent: `wants_price`, area: `20` | `approved`, action: `user_dm` | **SEND** --- canary receives price for 20 m2 | |
| 3 | canary | `5x4 hisobla` | intent: `wants_price`, area: `20` (parsed) | `approved`, action: `user_dm` | **SEND** --- canary receives price, area parsed from dimensions | |
| 4 | canary | `katalog ko'rsating` | intent: `wants_catalog` | `approved`, action: `user_dm` | **SEND** --- canary receives catalog showcase | |
| 5 | canary | `zakaz beraman` | intent: `wants_order` | `approved`, action: `user_dm` | **SEND** --- canary receives order flow CTA | |
| 6 | canary | `qimmat ekan, arzonroq bormi` | objection: `price` | `approved`, tactic: `cheaper_alternative` | **SEND** --- canary receives negotiation response | |
| 7 | canary | `kafolat bormi` | objection: `trust` | `approved`, tactic: `warranty` | **SEND** --- canary receives warranty assurance | |
| 8 | canary | `boshqa kompaniyada arzonroq` | objection: `compare` | `approved`, tactic: `value_reframe` | **SEND** --- canary receives value reframe response | |
| 9 | canary | `keyinroq qarayman` | objection: `delay` | `approved` or `blocked` (low urgency) | **SEND** or **NO-SEND** --- either is acceptable | |
| 10 | canary | `operator chaqiring` | intent: `wants_operator` | `approved`, action: `handoff` | **SEND** --- handoff acknowledgment, then no further agent messages | |
| 11 | canary | `kerak emas` | stop_signal: `true` | `blocked`, reason: `stop_signal` | **NO-SEND** --- no message delivered, conversation closed | |
| 12 | canary | `rahmat, kerak emas` | stop_signal: `true` | `blocked`, reason: `stop_signal` | **NO-SEND** --- polite refusal also triggers stop | |
| 13 | canary | (send any message after scenario 11/12 stop) | stop_signal persisted | `blocked`, reason: `stop_signal` | **NO-SEND** --- agent remains silent after stop | |
| 14 | canary | `нархи қанча` (Cyrillic Uzbek) | intent: `wants_price`, cyrillic: `true` | `approved`, normalized | **SEND** --- canary receives price reply, Cyrillic handled | |
| 15 | canary | `telefon raqamim 901234567` | phone_captured: `true` | `approved`, PII_safe | **SEND** --- acknowledgment sent, phone NOT in message text | |
| 16 | non-canary | `narxi qancha` | intent: `wants_price` | `would_execute`, NOT approved for send | **NO-SEND** --- non-canary user gets NO agent message | |
| 17 | non-canary | `20 kv metr qancha` | intent: `wants_price`, area: `20` | `would_execute`, NOT approved for send | **NO-SEND** --- sandbox trace only, no real delivery | |

### Phase B --- Follow-up Tests (enable follow-ups, then run these)

Before running Phase B, enable follow-up flags:

```
AGENT_FOLLOWUPS_ENABLED=true
AGENT_CATALOG_FOLLOWUP_ENABLED=true
AGENT_PRICE_FOLLOWUP_ENABLED=true
AGENT_ORDER_FOLLOWUP_ENABLED=true
AGENT_CATALOG_FOLLOWUP_DELAY_MINUTES=1
AGENT_PRICE_FOLLOWUP_DELAY_MINUTES=1
AGENT_ORDER_FOLLOWUP_DELAY_MINUTES=1
```

Restart scheduler: `docker compose restart scheduler`

| # | User Type | Input / Action | Expected Signal | Expected Sandbox | Expected Send / No-Send | Pass/Fail |
|---|-----------|----------------|-----------------|------------------|------------------------|-----------|
| 18 | canary | `narxi qancha` then wait 1-2 min | intent: `wants_price` | follow-up: `scheduled` | **SEND** --- price follow-up delivered after ~1 min delay | |
| 19 | canary | `katalog bormi` then wait 1-2 min | intent: `wants_catalog` | follow-up: `scheduled` | **SEND** --- catalog follow-up delivered after ~1 min delay | |
| 20 | canary | `zakaz beraman` then wait 1-2 min | intent: `wants_order` | follow-up: `scheduled` | **SEND** --- order follow-up delivered after ~1 min delay | |
| 21 | canary | `kerak emas` (after follow-up is scheduled) | stop_signal: `true` | follow-up: `cancelled` | **NO-SEND** --- pending follow-up cancelled, no delivery | |
| 22 | non-canary | `narxi qancha` then wait 2 min | intent: `wants_price` | follow-up: `would_execute` or `blocked` | **NO-SEND** --- follow-up NOT delivered to non-canary user | |
| 23 | non-canary | `katalog bormi` then wait 2 min | intent: `wants_catalog` | follow-up: `would_execute` or `blocked` | **NO-SEND** --- follow-up NOT delivered to non-canary user | |
| 24 | non-canary | `kerak emas` | stop_signal: `true` | `blocked`, reason: `stop_signal` | **NO-SEND** --- no message, no follow-up, conversation closed | |
| 25 | canary | Send 4+ messages to trigger daily cap | various intents | 4th+ action: `blocked`, reason: `daily_cap` | **NO-SEND** (4th+) --- daily cap (3) respected, excess blocked | |

---

## Scenario Notes

### Price Queries (1-3)

Scenarios 1-3 validate the core pricing pipeline delivers real messages to canary users. Scenario 3 tests the area parser (`shared/utils/area_parser.py`) --- "5x4" should resolve to 20 m2. All three must result in a real Telegram message appearing in the canary user's chat.

### Catalog and Orders (4-5)

These verify offer selection produces correct content types and delivers them. Catalog should show design options; order should continue the flow with a CTA.

### Objections and Negotiation (6-9)

Price objection (6) should trigger the negotiation engine with `cheaper_alternative` tactic. Trust objection (7) should deliver warranty assurance. Competitor comparison (8) should use `value_reframe`. Delay objection (9) is lower priority --- the agent may either respond softly or block as low urgency; both outcomes are acceptable.

### Operator Handoff (10)

The agent recognizes operator intent and delivers a handoff acknowledgment. After handoff, the agent must NOT send any further messages (no follow-up, no closing attempt). Verify silence after this scenario.

### Stop Signals (11-13)

**Critical safety tests.** Scenario 11 tests the basic stop phrase. Scenario 12 tests a polite variation. Scenario 13 verifies the stop is **persistent** --- once a user says stop, the agent must remain silent on all subsequent messages from that user. If any of these produce a real send, the safety layer is broken. Rollback immediately.

### Cyrillic (14)

Uzbek Cyrillic input must be normalized and produce the same behavior as Latin input. Verify `cyrillic_detected: true` or `text_normalized` in the execution trace.

### PII Safety (15)

**Critical safety test.** When the canary user shares a phone number, the agent stores it in lead data. The acknowledgment message sent to the user must NOT contain the raw phone number. Inspect the delivered message text carefully.

### Non-Canary Isolation (16-17, 22-24)

**Most critical tests in the entire script.** These verify the canary filter is enforced. Non-canary users must experience absolutely zero behavior change. The sandbox should produce `would_execute` traces (the pipeline runs) but no real Telegram message is sent. If a non-canary user receives any agent message, this is a critical failure --- rollback immediately.

### Follow-up Delivery (18-20)

These test the full follow-up cycle: user sends a message, the agent schedules a follow-up, and after the 1-minute delay, the follow-up is delivered to the canary user. Check that the delay is approximately 1 minute (+/- 30 seconds tolerance).

### Follow-up Cancellation via Stop (21)

After a follow-up is scheduled (trigger with a price/catalog/order query), send "kerak emas" before the follow-up fires. The pending follow-up must be cancelled and never delivered.

### Non-Canary Follow-up Isolation (22-23)

Non-canary users must NOT receive follow-ups even after the follow-up flags are enabled. The follow-up should appear in traces as `would_execute` or `blocked` but never result in a real send.

### Daily Cap (25)

Send enough messages from the canary account to exceed the daily cap (`AGENT_EXECUTION_MAX_DAILY_ACTIONS_PER_USER=3`). The first 3 agent actions should be delivered; the 4th and beyond must be blocked with reason `daily_cap`.

---

## Dashboard Verification Checklist

After running all 25 scenarios, verify in the Control Center:

- [ ] Stage still shows **CANARY** (has not changed)
- [ ] Health still **GREEN**
- [ ] Sandbox is **ON**
- [ ] Execution mode still **canary**
- [ ] Canary user IDs unchanged
- [ ] `canary_sends_total` > 0 (canary received messages)
- [ ] `canary_sends_delivered` matches expected count from passed scenarios
- [ ] `canary_sends_failed` = 0
- [ ] **`public_send_count` = 0** (critical --- no non-canary sends)
- [ ] **`followup_sent_public` = 0** (critical --- no non-canary follow-ups)
- [ ] `dry_run_would_execute` > 0 (non-canary traffic still producing traces)
- [ ] Block reasons include: `stop_signal` (from scenarios 11-13, 21, 24)
- [ ] Block reasons include: `daily_cap` (from scenario 25, if tested)
- [ ] Block reasons include: `non_canary_user` (from scenarios 16-17, 22-23)
- [ ] No block reason is `unknown`
- [ ] Sandbox validation errors: **0**
- [ ] Live sender activity: **0** (live sender must remain off)
- [ ] No PII (phone numbers, tokens) visible in any delivered message text
- [ ] Follow-up pending count: **0** (all should have resolved --- sent or cancelled)
- [ ] Admin escalation count: **0**

## Common Failures and What They Mean

| Symptom | Likely Cause | Action |
|---------|-------------|--------|
| Canary user receives no messages | Send path not wired for canary mode, or canary ID mismatch | Verify `AGENT_EXECUTION_CANARY_USER_IDS` matches the test account's Telegram ID exactly |
| Non-canary user receives a message | Canary filter bypassed --- critical safety failure | Rollback to OFF immediately, investigate filter logic |
| Follow-up fires during Phase A | Follow-up flag leaked or was not properly disabled | Rollback to OFF, verify `AGENT_FOLLOWUPS_ENABLED=false` |
| Follow-up not delivered in Phase B | Scheduler not restarted after flag change, or delay misconfigured | Restart scheduler, check `AGENT_PRICE_FOLLOWUP_DELAY_MINUTES` |
| Stop signal (scenarios 11-13) results in a send | Stop signal not enforced --- critical safety failure | Rollback to OFF immediately |
| Agent sends message after operator handoff (scenario 10) | Handoff does not suppress further agent actions | Rollback, investigate handoff state management |
| Phone number appears in delivered message (scenario 15) | PII sanitization not applied to sent messages | Rollback to OFF, fix sanitization in message composer |
| Daily cap not enforced (scenario 25) | Cap check missing or misconfigured | Verify `AGENT_EXECUTION_MAX_DAILY_ACTIONS_PER_USER=3`, check cap enforcement logic |
| All non-canary traces missing | Sandbox not running for non-canary users (pipeline skipped) | Verify `AGENT_EXECUTION_SANDBOX_ENABLED=true`, check orchestrator is enabled |
| Dashboard shows health RED | Critical issue detected | Rollback to OFF, investigate immediately |
| Sandbox validation errors > 0 | Malformed payload from orchestrator | Check error details in trace, likely a code bug |
| Cyrillic scenario (14) produces no response | Text normalization disabled or not wired | Verify `AGENT_TEXT_NORMALIZATION_ENABLED=true` |
| Follow-up not cancelled after stop (scenario 21) | Stop signal does not cancel pending follow-ups | Rollback, investigate follow-up cancellation logic |

## Test Report

```
Date: _______________
Operator: _______________
Stage: CANARY
Canary user IDs (count): ___
Follow-ups tested: yes / no

Phase A (follow-ups OFF):
  Scenarios tested: ___/17
  Scenarios passed: ___
  Scenarios failed: ___

Phase B (follow-ups ON):
  Scenarios tested: ___/8
  Scenarios passed: ___
  Scenarios failed: ___

Total: ___/25 passed

Dashboard checks passed: ___/20

Canary metrics:
  canary_sends_total:       ___
  canary_sends_delivered:   ___
  canary_sends_failed:      ___ (must be 0)
  public_send_count:        ___ (must be 0)
  followup_sent_public:     ___ (must be 0)
  validation_errors:        ___ (must be 0)
  live_sender_activity:     ___ (must be 0)

Failed scenarios (list numbers): ___
Issues found: _______________
Overall result: PASS / FAIL
Signed off by: _______________
```
