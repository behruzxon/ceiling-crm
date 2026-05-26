# Stage 5 (APPROVED_LIVE_SEND) Test Script

Step-by-step test script to verify Stage 5 APPROVED_LIVE_SEND is working correctly. Run this after applying the APPROVED_LIVE_SEND preset.

## Prerequisites

- Stage is set to **APPROVED_LIVE_SEND** (verify in dashboard)
- Health status is **GREEN**
- Sandbox is **ON**
- Execution mode is **approval_required** (NOT live)
- Queue is **ON**
- Approval admin notify is **ON**
- API approval is **ON**
- Approval TTL is **30 min**
- Live Sender is **ON**
- Auto Execute Approved is **ON**
- Revalidate Before Send is **ON**
- Mark Failed on Error is **ON**
- Batch Limit is **10**
- Allow Live Flags is **true**
- Canary IDs are **empty**
- AI Composer is **OFF**
- Stage 4 observation report filed with PASS result
- You have at least one **regular user** Telegram account (any non-admin)
- You have at least one **admin** Telegram account with access to the admin group
- Follow-ups are enabled with production delays (10 min)
- Mock bot or test environment available for simulating send failures

## How to Run Each Test

1. Identify the actor: **user** (sends trigger message), **admin** (reviews proposal in admin group), or **system** (automated behavior)
2. User sends the input message from their Telegram account to the bot
3. Verify a **proposal card** appears in the admin group (or is blocked as expected)
4. Admin performs the approve/reject action in the admin group
5. Verify the outcome: message delivered via Telegram (or not delivered, depending on scenario)
6. Open the Control Center dashboard and check execution traces, send logs, and dedup records
7. Mark Pass or Fail

---

## Test Scenarios

### Section A --- Approved Sends (scenarios 1-8)

These verify that admin-approved proposals are delivered exactly once via the live sender.

| # | User Input / Setup | Admin Action | Expected Send | Expected DB Status | Verify | Pass/Fail |
|---|-------------------|-------------|--------------|-------------------|--------|-----------|
| 1 | User sends `narxi qancha` | Approve | **YES** --- price reply delivered via Telegram | `executed` | User received exactly 1 message; `executed_at` timestamp set | |
| 2 | User sends `katalog ko'rsating` | Approve | **YES** --- catalog showcase delivered | `executed` | User received exactly 1 message; catalog keyboard present | |
| 3 | User sends `zakaz beraman` | Approve | **YES** --- order CTA delivered | `executed` | User received exactly 1 message; order flow initiated | |
| 4 | User sends `qimmat ekan` (price objection) | Approve | **YES** --- negotiation reply delivered | `executed` | User received exactly 1 message; tactic matches proposal card | |
| 5 | User sends `operator chaqiring` | Approve | **YES** --- handoff acknowledgment delivered | `executed` | User received exactly 1 message; conversation handed off | |
| 6 | User sends `20 kv qancha turadi` | Approve | **YES** --- price with area calculation delivered | `executed` | User received exactly 1 message; price includes 20 m2 | |
| 7 | User sends `kafolat bormi` (trust objection) | Approve | **YES** --- warranty/trust reply delivered | `executed` | User received exactly 1 message; trust tactic applied | |
| 8 | User sends `paketlar ko'rsating` | Approve | **YES** --- packages showcase delivered | `executed` | User received exactly 1 message; package options shown | |

### Section B --- Rejected / Expired / Blocked: No Send (scenarios 9-16)

These verify that non-approved proposals are NEVER delivered by the live sender.

| # | User Input / Setup | Condition | Expected Send | Expected DB Status | Verify | Pass/Fail |
|---|-------------------|-----------|--------------|-------------------|--------|-----------|
| 9 | User sends `narxi qancha` | Admin clicks **Reject** | **NO** | `rejected` | User received 0 messages; live sender log has no attempt for this proposal | |
| 10 | User sends `katalog ko'rsating` | Wait 31+ minutes, admin does NOT act | **NO** | `expired` | User received 0 messages; proposal auto-expired; live sender has no attempt | |
| 11 | User sends `kerak emas` | Stop signal detected | **NO** (no proposal created) | `blocked` | No proposal card in admin group; no queue entry; user received 0 messages | |
| 12 | User sends `rahmat, kerak emas` | Polite stop signal | **NO** (no proposal created) | `blocked` | No proposal card; stop persists for this user | |
| 13 | User sends any message after stop (scenario 11) | Post-stop message | **NO** (no proposal created) | `blocked` | Stop is persistent; no new proposals for stopped user | |
| 14 | Proposal already expired (scenario 10) | Admin clicks **Approve** after expiry | **NO** | `expired` (unchanged) | Expired proposals cannot be approved; error shown to admin | |
| 15 | Proposal already rejected (scenario 9) | Admin clicks **Approve** after rejection | **NO** | `rejected` (unchanged) | Rejected proposals cannot be re-approved; error shown to admin | |
| 16 | User has 3 approved+delivered actions today | User sends `yana narx ayting` | **NO** (daily cap) | `blocked` (cap exceeded) | Proposal blocked before queue; admin sees no card; cap counter shows 3/3 | |

### Section C --- Duplicate Prevention (scenarios 17-20)

These verify the exactly-once delivery guarantee.

| # | Setup | Action | Expected Send | Expected DB Status | Verify | Pass/Fail |
|---|-------|--------|--------------|-------------------|--------|-----------|
| 17 | Proposal approved and already executed (scenario 1) | Admin clicks **Approve** again | **NO** (already sent) | `executed` (unchanged) | Admin sees `already_approved` response; user did NOT receive a duplicate; `duplicate_send_attempts` metric stays 0 | |
| 18 | Proposal approved; live sender picks it up | Sender processes same proposal in next tick | **NO** (idempotency guard) | `executed` (unchanged) | `executed_at` unchanged from first send; no second Telegram message; dedup guard logged | |
| 19 | Same user sends `narxi qancha` twice in 5 seconds | Both enter pipeline | **At most 1 proposal created** | First: `proposed`; second: `blocked` (dedup) | Queue deduplication prevents two identical proposals for same user+intent within cooldown window | |
| 20 | Proposal approved; bot restarts mid-batch | Sender resumes after restart | **Exactly 1 send total** | `executed` | If message was sent before restart, sender detects via `executed_at` and skips; if not yet sent, sender delivers once | |

### Section D --- Token / Phone / Discount Blocked (scenarios 21-25)

These verify that the sandbox and revalidation block dangerous content from reaching users.

| # | Payload Condition | Expected Send | Expected DB Status | Block Reason | Verify | Pass/Fail |
|---|-------------------|--------------|-------------------|-------------|--------|-----------|
| 21 | Approved proposal contains bot token in message text (simulated) | **NO** | `blocked` (revalidation) | `pii_detected` (token) | Revalidation caught token before send; admin notified of block; user received 0 messages | |
| 22 | Approved proposal contains raw phone number `+998901234567` in text (simulated) | **NO** | `blocked` (revalidation) | `pii_detected` (phone) | Revalidation caught phone before send; user received 0 messages | |
| 23 | Approved proposal contains unauthorized discount `20% chegirma` (simulated) | **NO** | `blocked` (revalidation) | `unauthorized_discount` | Revalidation caught discount promise; user received 0 messages; discount not in approved templates | |
| 24 | Approved proposal contains false urgency `bugun oxirgi kun` (simulated) | **NO** | `blocked` (revalidation) | `unauthorized_urgency` | Revalidation caught urgency claim; user received 0 messages | |
| 25 | Approved proposal contains competitor comparison `eng arzon biz` (simulated) | **NO** | `blocked` (revalidation) | `unauthorized_comparison` | Revalidation caught comparison claim; user received 0 messages | |

### Section E --- Failed Send Handling (scenarios 26-28)

These verify that Telegram API errors are handled correctly without retry loops.

| # | Setup | Telegram API Response | Expected DB Status | Verify | Pass/Fail |
|---|-------|----------------------|-------------------|--------|-----------|
| 26 | Approved proposal, target user has blocked the bot | `TelegramForbiddenError` (403) | `failed` | `failed_at` timestamp set; `failed_reason` contains "forbidden"; no retry attempted; admin notified; blocked_chats table updated | |
| 27 | Approved proposal, target chat_id invalid or deleted | `TelegramBadRequest` (400) | `failed` | `failed_at` timestamp set; `failed_reason` contains error detail; no retry attempted | |
| 28 | Approved proposal, Telegram API rate limited | `TelegramRetryAfter` (429) | `failed` | `failed_at` set; `failed_reason` notes rate limit; proposal NOT auto-retried (manual review required); batch processing pauses for remaining tick | |

### Section F --- Mock Bot Verification (scenarios 29-30)

These verify end-to-end delivery via the mock bot or test environment.

| # | Setup | Action | Expected Result | Verify | Pass/Fail |
|---|-------|--------|----------------|--------|-----------|
| 29 | Mock bot captures outgoing messages | User sends `narxi qancha`; admin approves | Mock bot log shows exactly 1 outgoing `sendMessage` call to user's chat_id with correct text matching the proposal card preview | Message text matches proposal; chat_id correct; no extra API calls; `message_id` stored in proposal record | |
| 30 | Mock bot captures outgoing messages; follow-up triggers after 10 min | Wait 10+ minutes after scenario 29 | Follow-up proposal appears in admin group; admin approves; mock bot log shows exactly 1 additional `sendMessage` for the follow-up | Follow-up text matches follow-up proposal card; timing is >= 10 min after original; no auto-send without approval | |

---

## Scenario Notes

### Approved Sends (1-8)

Every approved proposal must result in exactly one Telegram message delivered to the target user. The message content must match the preview shown in the admin approval card. The `executed_at` timestamp must be set, and the `sends_delivered` metric must increment by exactly 1 per successful delivery. Verify by checking the user's Telegram chat and cross-referencing with the execution trace in the Control Center.

### Rejected / Expired / Blocked (9-16)

The live sender must never attempt delivery for proposals in any status other than `approved`. Rejected proposals are final and cannot be re-approved. Expired proposals are final and cannot be approved after TTL. Stopped users must never have proposals created. Daily cap must block proposals before they enter the queue. In every case, the user must receive zero messages.

### Duplicate Prevention (17-20)

This is the core exactly-once guarantee. The system must handle: (a) admin clicking Approve twice on the same proposal, (b) the batch sender processing the same proposal in consecutive ticks, (c) duplicate user messages generating duplicate proposals, and (d) bot restart during batch processing. In all cases, the user must receive at most one message per approved proposal. The `duplicate_send_attempts` metric must remain at 0.

### Token / Phone / Discount Blocked (21-25)

Even after admin approval, the revalidation step (`AGENT_EXECUTION_LIVE_SENDER_REVALIDATE=true`) performs a final sandbox check before each send. This catches content that should never reach users: bot tokens, raw phone numbers, unauthorized discount promises, false urgency claims, and competitor comparisons. These scenarios require simulated payloads (inject test data into the queue with dangerous content). If revalidation is working correctly, the send is blocked and the proposal moves to `blocked` status with the appropriate reason.

### Failed Send Handling (26-28)

When the Telegram API returns an error, the proposal must be marked `failed` with a timestamp and reason. No automatic retry is attempted --- failed sends require manual operator review. For `TelegramForbiddenError` (user blocked bot), the `blocked_chats` table should also be updated. For rate limiting (429), the batch sender should pause its current tick but NOT automatically retry the failed proposal.

### Mock Bot Verification (29-30)

These are end-to-end integration tests using a mock bot or test environment that captures outgoing API calls. They verify the full chain: user message -> pipeline -> proposal -> admin approval -> live sender -> Telegram API call -> message delivered. The mock bot log is the ground truth for verifying that exactly one `sendMessage` call was made with the correct parameters. Scenario 30 also validates that follow-ups go through the same approval pipeline and are not auto-sent.

---

## Dashboard Verification Checklist

After running all 30 scenarios, verify in the Control Center:

- [ ] Stage still shows **APPROVED_LIVE_SEND** (has not changed)
- [ ] Health still **GREEN**
- [ ] Sandbox is **ON**
- [ ] Execution mode still **approval_required** (NOT live)
- [ ] Queue is **ON**
- [ ] Live sender is **ON**
- [ ] Auto execute approved is **ON**
- [ ] Revalidate is **ON**
- [ ] `proposals_created` > 0 (proposals are being queued)
- [ ] `proposals_approved` matches count of approve actions from Section A + Section F
- [ ] `proposals_rejected` matches count of reject actions from Section B
- [ ] `proposals_expired` matches count from Section B (scenario 10)
- [ ] `proposals_blocked` includes stop signals (Section B) + PII blocks (Section D) + cap blocks (Section B)
- [ ] `sends_attempted` matches `proposals_approved` (no mismatch)
- [ ] `sends_delivered` matches successful deliveries from Section A + Section F
- [ ] `sends_failed` matches Section E failure count
- [ ] **`duplicate_send_attempts` = 0** (critical --- exactly-once guarantee)
- [ ] **`unapproved_sends` = 0** (critical --- no messages without approval)
- [ ] `revalidation_blocks` matches Section D block count
- [ ] No PII visible in any proposal card, execution trace, or delivered message
- [ ] `sandbox_validation_errors` = 0 (or only for simulated scenarios)
- [ ] Follow-up proposals appear in queue (scenario 30)
- [ ] Daily cap tracked correctly per user (scenario 16)
- [ ] Batch limit not exceeded in any single tick

## Common Failures and What They Mean

| Symptom | Likely Cause | Action |
|---------|-------------|--------|
| Approved proposal not delivered | Live sender disabled, auto-execute off, or send path broken | Verify `AGENT_EXECUTION_LIVE_SENDER_ENABLED=true` and `AGENT_EXECUTION_AUTO_EXECUTE_APPROVED=true`; check execution trace |
| User receives message without admin approval | Mode set to `live`, or approval bypass in send path | Rollback to OFF immediately; verify `AGENT_EXECUTION_MODE=approval_required` |
| Duplicate message to user | Exactly-once guard missing or idempotency key not checked | Rollback to OFF immediately; investigate dedup logic in sender |
| Rejected proposal delivered | Live sender does not check proposal status before send | Rollback to OFF immediately; investigate sender status check |
| Expired proposal delivered | Live sender does not check expiry before send | Rollback to OFF immediately; investigate sender expiry check |
| Revalidation did not block PII | Revalidation disabled or regex patterns incomplete | Verify `AGENT_EXECUTION_LIVE_SENDER_REVALIDATE=true`; check sandbox PII patterns |
| Failed send retried automatically | Retry logic present in sender (should not be) | Rollback to OFF; remove retry logic; failed sends must be terminal |
| Sends_attempted > proposals_approved | Send path leak --- sender executing non-approved proposals | Rollback to OFF immediately; critical authorization bug |
| Sends_attempted < proposals_approved | Sender not picking up approved proposals | Check batch sender loop; verify scheduler is running; check batch limit |
| Phone number in delivered message | PII sanitization failed in payload builder AND revalidation | Rollback to OFF; fix both layers |
| Follow-up sends directly (bypasses queue) | Follow-up execution path not routed through approval queue | Rollback to OFF; investigate follow-up execution path |
| Dashboard shows health RED | Critical issue detected | Rollback to OFF; investigate immediately |
| Bot token in execution trace | Logging or tracing exposes secrets | Rollback to OFF; scrub logs; fix trace sanitization |

## Test Report

```
Date: _______________
Operator: _______________
Stage: APPROVED_LIVE_SEND
Environment: development / staging / production
Admin group verified: yes / no
Follow-ups enabled: yes / no
Mock bot used: yes / no

Section A (Approved Sends):
  Scenarios tested: ___/8
  Scenarios passed: ___
  Scenarios failed: ___

Section B (Rejected / Expired / Blocked):
  Scenarios tested: ___/8
  Scenarios passed: ___
  Scenarios failed: ___

Section C (Duplicate Prevention):
  Scenarios tested: ___/4
  Scenarios passed: ___
  Scenarios failed: ___

Section D (Token / Phone / Discount Blocked):
  Scenarios tested: ___/5
  Scenarios passed: ___
  Scenarios failed: ___

Section E (Failed Send Handling):
  Scenarios tested: ___/3
  Scenarios passed: ___
  Scenarios failed: ___

Section F (Mock Bot Verification):
  Scenarios tested: ___/2
  Scenarios passed: ___
  Scenarios failed: ___

Total: ___/30 passed

Dashboard checks passed: ___/24

Send metrics:
  proposals_created:          ___
  proposals_approved:         ___
  proposals_rejected:         ___
  proposals_expired:          ___
  proposals_blocked:          ___
  sends_attempted:            ___
  sends_delivered:            ___
  sends_failed:               ___
  duplicate_send_attempts:    ___ (must be 0)
  unapproved_sends:           ___ (must be 0)
  revalidation_blocks:        ___
  sandbox_validation_errors:  ___ (must be 0)

Failed scenarios (list numbers): ___
Issues found: _______________
Overall result: PASS / FAIL
Signed off by: _______________
```
