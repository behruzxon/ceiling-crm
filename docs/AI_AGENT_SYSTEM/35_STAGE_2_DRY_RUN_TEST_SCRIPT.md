# Stage 2 (DRY_RUN) Test Script

Step-by-step test script to verify Stage 2 DRY_RUN is working correctly. Run this after applying the DRY_RUN preset.

## Prerequisites

- Stage is set to **DRY_RUN** (verify in dashboard)
- Health status is **GREEN**
- Sandbox is **ON**
- Live Sender is **OFF**
- Auto Execute is **OFF**
- Follow-ups are **OFF**
- Stage 1 observation report filed with PASS result
- You have a test Telegram account to send messages from

## How to Run Each Test

1. Send the message from your test Telegram account to the bot
2. Observe the bot's normal response in Telegram (should be unchanged)
3. Open the Control Center dashboard and check sandbox traces
4. Verify the sandbox result matches the Expected columns
5. Verify nothing in "Must NOT Happen" occurred
6. Mark Pass or Fail

---

## Test Scenarios

| # | Input / Event | Expected Signal | Expected Offer | Expected Policy | Expected Sandbox | Pass/Fail |
|---|---------------|-----------------|----------------|-----------------|------------------|-----------|
| 1 | `narxi qancha` | intent: `wants_price` | price_calc (general) | `respond_price` | `would_execute`, action: `user_dm` | |
| 2 | `20 kv qancha` | intent: `wants_price`, area: `20` | price_calc with 20 m2 | `respond_price` | `would_execute`, action: `user_dm` | |
| 3 | `5x4 hisobla` | intent: `wants_price`, area: `20` (parsed) | price_calc with 20 m2 | `respond_price` | `would_execute`, area parsed from dimensions | |
| 4 | `katalog bormi` | intent: `wants_catalog` | catalog_showcase | `respond_catalog` | `would_execute`, action: `user_dm` | |
| 5 | `zakaz beraman` | intent: `wants_order` | order_continue CTA | `respond_order` | `would_execute`, action: `user_dm` | |
| 6 | `operator kerak` | intent: `wants_operator` | none (handoff) | `handoff_operator` | `would_execute`, action: `handoff` | |
| 7 | `chegirma bormi` | intent: `wants_discount` | discount_info | `respond_discount` | `would_execute`, action: `user_dm` | |
| 8 | `qimmat ekan` | objection: `price` | negotiation: `cheaper_alternative` | `negotiate` | `would_execute`, tactic logged | |
| 9 | `kafolat bormi` | objection: `trust` | warranty_assurance | `respond_trust` | `would_execute`, tactic: `warranty` | |
| 10 | `keyinroq qarayman` | objection: `delay` | soft_reminder or none | `allow_delay` | `would_execute` or `blocked`, reason: `low_urgency` | |
| 11 | `kerak emas` | stop_signal: `true` | no offer generated | `stop_conversation` | `blocked`, reason: `stop_signal` | |
| 12 | `нархи қанча` (Cyrillic Uzbek) | intent: `wants_price`, cyrillic: `true` | price_calc (general) | `respond_price` | `would_execute`, normalized text in trace | |
| 13 | `қиммат экан` (Cyrillic objection) | objection: `price`, cyrillic: `true` | negotiation tactic | `negotiate` | `would_execute`, cyrillic normalized | |
| 14 | `сколько стоит` (Russian) | intent: `wants_price` | price_calc (general) | `respond_price` | `would_execute`, language detected | |
| 15 | `bugun kerak o'rnatish` | intent: `wants_measurement`, urgency: `high` | fast_install CTA | `escalate_or_respond` | `would_execute`, urgency: `high` in payload | |
| 16 | `salom` (cold lead, no context) | intent: `unclear` | no offer (insufficient data) | `wait` or `nurture` | `blocked`, reason: `low_confidence` or stored only | |
| 17 | (Simulate) Hot lead: score >= 70, phone + area known | temperature: `hot` | closing CTA (measurement/call) | `attempt_close` | `would_execute`, action: `user_dm`, urgency: `high` | |
| 18 | (Simulate) Order abandoned: started order, went silent 30 min | intent: `order_abandoned` | order_reminder | `followup_check` | `would_execute` or `blocked`, action: `followup` | |
| 19 | `telefon raqamim 901234567` | phone_captured: `true` | lead_enrichment ack | `acknowledge_data` | `would_execute`, PII_safe: phone NOT in payload text | |
| 20 | `boshqa kompaniyada arzonroq ekan` | objection: `compare` | negotiation: `value_reframe` | `negotiate` | `would_execute`, tactic: `value_reframe` | |

---

## Scenario Notes

### Price Queries (1-3)

Scenarios 1-3 test the core pricing pipeline. Scenario 3 specifically tests the area parser (`shared/utils/area_parser.py`) — "5x4" should be parsed as 20 m2. All three should produce `would_execute` with a `user_dm` action type.

### Catalog and Orders (4-5, 7)

These verify the offer engine selects the correct content type. Catalog should show design options, order should continue the flow, discount should provide discount info.

### Operator Handoff (6)

The agent recognizes operator intent and produces a handoff action. The sandbox should mark this as `would_execute` but no actual handoff occurs beyond the bot's existing behavior.

### Objections (8-10, 20)

Price objection (8) should trigger negotiation tactics. Trust objection (9) should offer warranty assurance. Delay objection (10) is lower priority — the agent may block it as low urgency. Competitor comparison (20) should trigger `value_reframe`.

### Stop Signals (11)

This is a critical safety test. "kerak emas" must always produce `blocked` with reason `stop_signal`. If it produces `would_execute`, the safety layer is broken — rollback immediately.

### Cyrillic and Multi-Language (12-14)

Scenarios 12-13 test Uzbek Cyrillic normalization. Scenario 14 tests Russian input. All should be normalized and produce the same signals as their Latin equivalents. Check that `cyrillic_detected: true` or `text_normalized` appears in traces.

### Urgency and Temperature (15-17)

Scenario 15 tests high-urgency detection. Scenarios 16-17 test lead temperature extremes. For simulated scenarios (17), check existing hot leads in the dashboard if you cannot trigger naturally.

### Order Abandoned (18)

If you cannot naturally simulate abandonment, check dashboard traces for any user who started an order flow and went inactive. The agent should recognize the pattern and produce a reminder payload.

### PII Safety (19)

Critical safety test. When a user shares a phone number, the agent must store it in lead data but must NOT include the raw phone number in any sandbox payload text field. Check the `would_execute` payload carefully.

---

## Dashboard Verification Checklist

After running all 20 scenarios, verify in the Control Center:

- [ ] Stage still shows **DRY_RUN** (has not changed)
- [ ] Health still **GREEN**
- [ ] Sandbox is **ON**
- [ ] `dry_run_payloads_total` increased (approximately 20, may vary)
- [ ] `dry_run_would_execute` count > 0 (most scenarios should produce payloads)
- [ ] `dry_run_blocked` count > 0 (stop signal and low-confidence should block)
- [ ] Block reasons include: `stop_signal` (from scenario 11)
- [ ] No block reason is `unknown`
- [ ] Sandbox validation errors: **0**
- [ ] Live sender activity: **0** (critical)
- [ ] Follow-up pending count: **0** (critical)
- [ ] Executed actions count: **0** (critical)
- [ ] Admin escalation count: **0**
- [ ] Action type breakdown visible (user_dm, handoff, etc.)
- [ ] No PII (phone numbers, tokens) visible in any payload text field

## Common Failures and What They Mean

| Symptom | Likely Cause | Action |
|---------|-------------|--------|
| No sandbox traces after sending messages | Sandbox not enabled or mode still `log_only` | Verify `AGENT_EXECUTION_SANDBOX_ENABLED=true` and `AGENT_EXECUTION_MODE=dry_run` |
| All payloads show `blocked` | Policy too strict or min confidence too high | Check `AGENT_RESPONSE_ORCHESTRATOR_MIN_CONFIDENCE`, review policy rules |
| All payloads show `would_execute` (none blocked) | Stop signals not wired, safety checks missing | Rollback to OFF, investigate policy engine |
| Stop signal (scenario 11) shows `would_execute` | Critical safety failure — stop signal not enforced | Rollback to OFF immediately |
| Sandbox validation errors > 0 | Malformed payload from orchestrator | Check error details, likely a code bug |
| PII found in payload text (scenario 19) | Phone/name leaking into composed message | Rollback to OFF, fix sanitization layer |
| Live sender activity > 0 | Sandbox not enforcing — messages actually sent | Rollback to OFF immediately |
| Cyrillic scenarios (12-13) show no signal | Text normalization disabled | Check `AGENT_TEXT_NORMALIZATION_ENABLED=true` |
| Area not parsed from "5x4" (scenario 3) | Area parser not integrated into signal extraction | Check area_parser wiring in signal extractor |
| Bot stops responding | Bot process crashed | `docker compose restart bot`, check logs |
| Dashboard shows health RED | Critical issue detected | Rollback to OFF, investigate immediately |

## Test Report

```
Date: _______________
Operator: _______________
Stage: DRY_RUN
Scenarios tested: ___/20
Scenarios passed: ___
Scenarios failed: ___
Dashboard checks passed: ___/15

Sandbox metrics:
  dry_run_payloads_total: ___
  dry_run_would_execute:  ___
  dry_run_blocked:        ___
  validation_errors:      ___ (must be 0)
  live_sender_activity:   ___ (must be 0)

Failed scenarios (list numbers): ___
Issues found: _______________
Overall result: PASS / FAIL
Signed off by: _______________
```
