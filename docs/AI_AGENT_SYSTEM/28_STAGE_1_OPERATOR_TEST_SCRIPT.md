# Stage 1 (LOG_ONLY) Operator Test Script

Step-by-step test script to verify Stage 1 is working correctly. Run this after applying the LOG_ONLY preset.

## Prerequisites

- Stage is set to **LOG_ONLY** (verify in dashboard)
- Health status is **GREEN**
- Live Sender is **OFF**
- Auto Execute is **OFF**
- You have a test Telegram account to send messages from

## How to Run Each Test

1. Send the message from your test Telegram account to the bot
2. Observe the bot's response in Telegram
3. Open the Control Center dashboard and check traces
4. Verify what **must NOT happen**
5. Mark Pass or Fail

---

## Test Scenarios

| # | You Send | Bot Expected Response | Dashboard Expected Trace | What Must NOT Happen | Pass/Fail |
|---|----------|-----------------------|--------------------------|----------------------|-----------|
| 1 | `/start` | Normal welcome message with menu keyboard | No agent trace (start command is handled by bot, not agent) | No extra DM, no follow-up scheduled | |
| 2 | `20 kv qancha` | Normal pricing response for 20 m2 | `intent: wants_price`, `area: 20` in signal trace. Decision and offer traces written. | No follow-up scheduled, no admin alert, no closing CTA from agent | |
| 3 | `qimmat ekan` | Normal objection handling response | `objection: price` in signal trace. Negotiation tactic logged in decision trace. | No separate agent DM, no "arzon variant" pushed by agent, no follow-up | |
| 4 | `narxi qancha` (Cyrillic: `нархи қанча`) | Normal pricing flow response | `intent: wants_price` in signal trace. `cyrillic_detected: true` or `text_normalized` in trace. | No different behavior from Latin input, no error, no agent message | |
| 5 | `operator kerak` | Operator handoff flow (existing bot behavior) | `intent: wants_operator` in signal trace. Policy: `handoff_operator`. | No agent follow-up after handoff, no "operator hozir band" from agent | |
| 6 | `kerak emas` | Normal bot acknowledgment | `stop_signal: true` in trace. Stop signal count +1 in safety panel. | No further messages of any kind from bot/agent, no follow-up ever | |

---

## Dashboard Verification Checklist

After running all 6 scenarios, verify in the dashboard:

- [ ] Stage still shows **LOG_ONLY** (has not changed)
- [ ] Health still **GREEN**
- [ ] Signal extraction metrics show activity (event count increased)
- [ ] Decision engine traces are written for scenarios 2-6
- [ ] Offer traces are written for scenarios 2-5
- [ ] Policy traces are written for scenarios 2-6
- [ ] Follow-up pending count is **0** (no follow-ups scheduled)
- [ ] Approval queue is **empty** (no proposals created)
- [ ] Executed actions count is **0**
- [ ] Live Sender still **OFF**
- [ ] Safety panel shows stop signal count incremented (from scenario 6)
- [ ] No blocked actions (nothing to block in LOG_ONLY)

## Common Failures and What They Mean

| Symptom | Likely Cause | Action |
|---------|-------------|--------|
| No traces written after sending messages | Orchestrator not enabled or LOG_ONLY flag misconfigured | Check flags match doc 23 (Stage 1 Readiness) |
| Bot does not respond at all | Bot process crashed or not running | Check `docker compose ps bot`, restart if needed |
| Dashboard shows health YELLOW | A metric is near threshold | Check which metric triggered it, likely safe to continue |
| Dashboard shows health RED | Critical issue | Rollback to OFF immediately |
| Follow-up count > 0 | Follow-up flags accidentally enabled | Rollback to OFF, verify flags match LOG_ONLY preset |
| User received unexpected DM | Stage is not actually LOG_ONLY | Rollback to OFF immediately, check audit log for stage changes |

## Test Report

```
Date: _______________
Operator: _______________
Stage: LOG_ONLY
Scenarios tested: ___/6
Scenarios passed: ___
Scenarios failed: ___
Dashboard checks passed: ___/12
Issues found: _______________
Overall result: PASS / FAIL
Signed off by: _______________
```
