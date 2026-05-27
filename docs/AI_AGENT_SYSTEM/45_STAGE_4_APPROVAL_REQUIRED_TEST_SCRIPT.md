# Stage 4 (APPROVAL_REQUIRED) Test Script

Step-by-step test script to verify Stage 4 APPROVAL_REQUIRED is working correctly. Run this after applying the APPROVAL_REQUIRED preset.

## Prerequisites

- Stage is set to **APPROVAL_REQUIRED** (verify in dashboard)
- Health status is **GREEN**
- Sandbox is **ON**
- Execution mode is **approval_required**
- Queue is **ON**
- Approval admin notify is **ON**
- Approval TTL is **30 min**
- Live Sender is **OFF**
- Auto Execute is **OFF**
- Canary IDs are **empty**
- AI Composer is **OFF**
- Stage 3 observation report filed with PASS result
- You have at least one **regular user** Telegram account (any non-admin)
- You have at least one **admin** Telegram account with access to the admin group
- You have at least one **non-admin** Telegram account to test unauthorized approval attempts
- Follow-ups are enabled with production delays (10 min)

## How to Run Each Test

1. Identify the actor: **user** (sends trigger message), **admin** (reviews proposal in admin group), or **non-admin** (attempts unauthorized action)
2. User sends the input message from their Telegram account to the bot
3. Verify a **proposal card** appears in the admin group (or is blocked as expected)
4. Admin or non-admin performs the action in the admin group
5. Verify the outcome matches the Expected columns
6. Open the Control Center dashboard and check execution traces
7. Mark Pass or Fail

---

## Test Scenarios

### Section A --- Proposal Creation (scenarios 1-10)

| # | User Input / Action | Expected Queue Status | Expected Admin Card | User Receives Message? | Pass/Fail |
|---|---------------------|----------------------|--------------------|-----------------------|-----------|
| 1 | User sends `narxi qancha` | `proposed` | Card with intent `wants_price`, message preview, approve/reject buttons | **NO** --- user receives nothing until admin acts | |
| 2 | User sends `20 kv qancha turadi` | `proposed` | Card with intent `wants_price`, area `20`, price preview | **NO** --- waiting for admin | |
| 3 | User sends `5x4 hisobla` | `proposed` | Card with intent `wants_price`, area `20` (parsed from dimensions) | **NO** --- waiting for admin | |
| 4 | User sends `katalog ko'rsating` | `proposed` | Card with intent `wants_catalog`, catalog offer preview | **NO** --- waiting for admin | |
| 5 | User sends `zakaz beraman` | `proposed` | Card with intent `wants_order`, order CTA preview | **NO** --- waiting for admin | |
| 6 | User sends `qimmat ekan, arzonroq bormi` | `proposed` | Card with objection `price`, tactic `cheaper_alternative` | **NO** --- waiting for admin | |
| 7 | User sends `kafolat bormi` | `proposed` | Card with objection `trust`, tactic `warranty` | **NO** --- waiting for admin | |
| 8 | User sends `boshqa kompaniyada arzonroq` | `proposed` | Card with objection `compare`, tactic `value_reframe` | **NO** --- waiting for admin | |
| 9 | User sends `нархи қанча` (Cyrillic Uzbek) | `proposed` | Card with intent `wants_price`, cyrillic normalized | **NO** --- waiting for admin | |
| 10 | User sends `operator chaqiring` | `proposed` | Card with intent `wants_operator`, action `handoff` | **NO** --- waiting for admin | |

### Section B --- Admin Approve/Reject (scenarios 11-18)

| # | Setup | Admin Action | Expected Queue Status | User Receives Message? | Pass/Fail |
|---|-------|--------------|--------------------|----------------------|-----------|
| 11 | Proposal from scenario 1 pending | Admin clicks **Approve** | `approved` | **YES** --- user receives the price reply | |
| 12 | Proposal from scenario 4 pending | Admin clicks **Approve** | `approved` | **YES** --- user receives the catalog showcase | |
| 13 | Proposal from scenario 6 pending | Admin clicks **Approve** | `approved` | **YES** --- user receives the negotiation response | |
| 14 | Proposal from scenario 10 pending | Admin clicks **Approve** | `approved` | **YES** --- handoff acknowledgment delivered, then silence | |
| 15 | User sends `paketlar ko'rsating` | Admin clicks **Reject** | `rejected` | **NO** --- user receives nothing, proposal is final | |
| 16 | User sends `yana narx ayting` | Admin clicks **Reject** | `rejected` | **NO** --- user receives nothing, proposal is final | |
| 17 | Proposal already approved (scenario 11) | Admin clicks **Approve** again | `already_approved` | No duplicate message --- original delivery stands | |
| 18 | Proposal already rejected (scenario 15) | Admin clicks **Approve** | `already_rejected` | **NO** --- rejected proposals cannot be re-approved | |

### Section C --- Expiry Handling (scenarios 19-21)

| # | Setup | Wait Duration | Expected Queue Status | User Receives Message? | Pass/Fail |
|---|-------|-------------|--------------------|-----------------------|-----------|
| 19 | User sends `qancha turadi 30 kv` | Wait 31+ minutes, admin does NOT act | `expired` | **NO** --- proposal expired, silently discarded | |
| 20 | Expired proposal from scenario 19 | Admin clicks **Approve** after expiry | `expired` (cannot approve) | **NO** --- expired proposals cannot be approved | |
| 21 | Expired proposal from scenario 19 | Admin clicks **Reject** after expiry | `expired` (already final) | **NO** --- already expired, reject is no-op | |

### Section D --- Non-Admin Rejection (scenario 22)

| # | Setup | Non-Admin Action | Expected Result | User Receives Message? | Pass/Fail |
|---|-------|-----------------|----------------|----------------------|-----------|
| 22 | Proposal pending in admin group | Non-admin clicks **Approve** button | Action rejected with error: insufficient permissions | **NO** --- only authorized admins can approve | |

### Section E --- Blocked Payloads (scenarios 23-26)

| # | User Input / Condition | Expected Queue Status | Expected Block Reason | Admin Card Created? | Pass/Fail |
|---|----------------------|---------------------|--------------------|-------------------|----|
| 23 | User sends `kerak emas` | `blocked` | `stop_signal` | **NO** --- blocked before queue, no proposal created | |
| 24 | User sends `rahmat, kerak emas` | `blocked` | `stop_signal` | **NO** --- polite refusal also triggers stop | |
| 25 | User sends any message after stop (scenario 23/24) | `blocked` | `stop_signal` (persisted) | **NO** --- agent remains silent after stop | |
| 26 | User sends `keyinroq qarayman` after scenario 25 stop | `blocked` | `stop_signal` (persisted) | **NO** --- stop persists across messages | |

### Section F --- Token/Phone/PII in Payload (scenarios 27-28)

| # | User Input | Expected Queue Status | Expected Behavior | Pass/Fail |
|---|-----------|---------------------|--------------------|-----------|
| 27 | User sends `telefon raqamim 901234567` | `proposed` (phone stored in lead, not in message) | Admin card shows acknowledgment text WITHOUT raw phone number; if approved, delivered message also has no phone | |
| 28 | Payload contains bot token or API key (simulated) | `blocked` | Sandbox validation catches PII/secret in payload text, blocks before queue | |

### Section G --- No Auto-Send Verification (scenarios 29-30)

| # | Condition | Expected Behavior | Auto-Send Occurs? | Pass/Fail |
|---|-----------|-------------------|-------------------|-----------|
| 29 | 5 proposals sitting in queue, no admin action for 10 minutes | All remain `proposed` (pending); none auto-execute | **NO** --- proposals never auto-send regardless of wait time | |
| 30 | Follow-up triggers after 10-min delay for a user who asked `narxi qancha` | Follow-up enters queue as new `proposed` item, not sent directly | **NO** --- follow-up proposals also require admin approval | |

---

## Scenario Notes

### Proposal Creation (1-10)

Every user message that triggers the agent pipeline must produce a proposal in the approval queue. The user must **not** receive any message until an admin explicitly approves. Verify each proposal card in the admin group shows: the target user's display name, the detected intent/objection, a preview of the message the agent wants to send, and approve/reject inline buttons.

### Admin Approve/Reject (11-18)

These test the core human-in-the-loop flow. Approved proposals must result in immediate delivery to the user. Rejected proposals must result in zero delivery. Re-approving an already-approved proposal must not send a duplicate. Attempting to approve a rejected proposal must fail gracefully.

### Expiry (19-21)

Proposals that exceed `AGENT_EXECUTION_APPROVAL_TTL_MINUTES` (30 min) must transition to `expired` status. Expired proposals cannot be approved or rejected --- they are final. The user receives nothing. Verify the expiry is automatic (scheduler-driven or lazy on next access).

### Non-Admin Rejection (22)

**Security test.** Only users with ADMIN or SUPERADMIN role should be able to approve or reject proposals. A non-admin clicking the approve button must receive an error response and the proposal must remain unchanged. If a non-admin can approve, the authorization layer is broken --- rollback immediately.

### Blocked Payloads (23-26)

Stop signals must block proposals **before they enter the queue**. No admin card should appear for a stopped user. The stop must be persistent --- subsequent messages from the same user are also blocked without creating proposals.

### PII Safety (27-28)

**Critical safety test.** Phone numbers shared by users must be stored in the lead record but must **never** appear in the proposed message text or the delivered message. Bot tokens and API keys must be caught by sandbox validation and blocked before entering the queue.

### No Auto-Send (29-30)

**Core safety guarantee of Stage 4.** Under no circumstances should a proposal auto-execute. Proposals must remain in `proposed` status indefinitely until an admin acts or the TTL expires. Follow-up actions must also enter the queue as proposals, not bypass it. If any message is sent without explicit admin approval, this is a critical failure.

---

## Dashboard Verification Checklist

After running all 30 scenarios, verify in the Control Center:

- [ ] Stage still shows **APPROVAL_REQUIRED** (has not changed)
- [ ] Health still **GREEN**
- [ ] Sandbox is **ON**
- [ ] Execution mode still **approval_required**
- [ ] Queue is **ON**
- [ ] `proposals_created` > 0 (proposals are being queued)
- [ ] `proposals_approved` matches count of approve actions from Section B
- [ ] `proposals_rejected` matches count of reject actions from Section B
- [ ] `proposals_expired` matches count from Section C
- [ ] **`auto_sends_total` = 0** (critical --- no messages sent without approval)
- [ ] **`live_sender_activity` = 0** (critical --- live sender must remain off)
- [ ] Block reasons include: `stop_signal` (from scenarios 23-26)
- [ ] No block reason is `unknown`
- [ ] Sandbox validation errors: **0** (or only for simulated PII scenario 28)
- [ ] No PII (phone numbers, tokens) visible in any proposal card or delivered message text
- [ ] Proposals pending count: matches expected (unacted proposals from Section G)
- [ ] Follow-up proposals appear in queue (scenario 30)
- [ ] Admin escalation count: **0**
- [ ] Daily cap tracked correctly per user

## Common Failures and What They Mean

| Symptom | Likely Cause | Action |
|---------|-------------|--------|
| No proposal card appears in admin group | Queue or admin notify not enabled, or admin group misconfigured | Verify `AGENT_EXECUTION_QUEUE_ENABLED=true` and `AGENT_EXECUTION_APPROVAL_ADMIN_NOTIFY=true`, check admin group ID |
| User receives message without admin approval | Auto-execute enabled, or approval bypass in send path | Rollback to OFF immediately, verify `AGENT_EXECUTION_AUTO_EXECUTE_APPROVED=false` |
| Approved proposal not delivered | Send path after approval is broken, or sandbox blocks approved payload | Check execution trace for the approved proposal, verify sandbox allows approved payloads |
| Rejected proposal still delivered | Rejection not enforced in execution path | Rollback to OFF immediately, investigate rejection handling |
| Expired proposal delivered | Expiry check missing in execution path | Rollback to OFF immediately |
| Non-admin can approve | Authorization check missing on approval callback | Rollback to OFF immediately, fix RBAC on approval handler |
| Stop signal does not prevent proposal | Stop signal not checked before queue insertion | Rollback, investigate signal-to-queue pipeline |
| Phone number in proposal text | PII sanitization not applied before queuing | Rollback to OFF, fix sanitization in payload builder |
| Follow-up sends directly (bypasses queue) | Follow-up execution path not routed through approval queue | Rollback to OFF, investigate follow-up execution path |
| Proposals pile up, admin overwhelmed | TTL too long, or traffic too high for manual review | Consider shorter TTL, or evaluate readiness for Stage 5 |
| Dashboard shows health RED | Critical issue detected | Rollback to OFF, investigate immediately |
| Duplicate proposals for same user message | Deduplication missing in queue insertion | Check for idempotency logic in proposal creation |

## Test Report

```
Date: _______________
Operator: _______________
Stage: APPROVAL_REQUIRED
Admin group verified: yes / no
Follow-ups enabled: yes / no

Section A (Proposal Creation):
  Scenarios tested: ___/10
  Scenarios passed: ___
  Scenarios failed: ___

Section B (Admin Approve/Reject):
  Scenarios tested: ___/8
  Scenarios passed: ___
  Scenarios failed: ___

Section C (Expiry Handling):
  Scenarios tested: ___/3
  Scenarios passed: ___
  Scenarios failed: ___

Section D (Non-Admin Rejection):
  Scenarios tested: ___/1
  Scenarios passed: ___
  Scenarios failed: ___

Section E (Blocked Payloads):
  Scenarios tested: ___/4
  Scenarios passed: ___
  Scenarios failed: ___

Section F (PII Safety):
  Scenarios tested: ___/2
  Scenarios passed: ___
  Scenarios failed: ___

Section G (No Auto-Send):
  Scenarios tested: ___/2
  Scenarios passed: ___
  Scenarios failed: ___

Total: ___/30 passed

Dashboard checks passed: ___/19

Queue metrics:
  proposals_created:          ___
  proposals_approved:         ___
  proposals_rejected:         ___
  proposals_expired:          ___
  proposals_blocked:          ___
  auto_sends_total:           ___ (must be 0)
  live_sender_activity:       ___ (must be 0)
  validation_errors:          ___ (must be 0)

Failed scenarios (list numbers): ___
Issues found: _______________
Overall result: PASS / FAIL
Signed off by: _______________
```
