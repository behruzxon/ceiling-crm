# Operator Training Pack

This guide trains operators to safely monitor and manage the CeilingCRM AI Agent system via the Control Center dashboard at `/agent`.

## What is the Control Center?

The Control Center is the web dashboard where operators observe the AI agent's behavior, review proposed actions, and control which stage the agent is running in. It is **read-only by default** -- the agent does not send any messages unless an operator explicitly enables higher stages and confirms.

The dashboard shows: current rollout stage, health status, pending approvals, follow-up queues, safety metrics, and a settings audit log.

## Agent Rollout Stages

The agent has 6 stages, from fully off to fully live. Each stage unlocks more behavior. **You must never skip stages.**

| Stage | Name | What the agent does | Messages sent to users? |
|-------|------|---------------------|------------------------|
| 0 | **OFF** | Nothing. Agent fully disabled. | No |
| 1 | **LOG_ONLY** | Observes messages, extracts signals, writes traces. | No |
| 2 | **DRY_RUN** | Validates payloads in sandbox, records what it *would* send. | No |
| 3 | **CANARY** | Sends real messages, but **only to canary test users** (admin accounts). | Yes -- canary users only |
| 4 | **APPROVAL_REQUIRED** | Proposes messages for all users; admin must approve each one before send. | Yes -- only after admin approval |
| 5 | **LIVE SEND** | Approved messages sent automatically. Full production mode. | Yes -- automatically |

**Key rule**: Stages 0-2 never send any message to any user. Stage 3+ can send real messages. The boundary between "safe observation" and "real user impact" is between DRY_RUN and CANARY.

## What the Operator Sees in the Dashboard

### Status Header
- **Rollout Stage**: Current stage name and number (e.g., "Stage 1 - LOG_ONLY")
- **Health Status**: GREEN / YELLOW / RED indicator
- **Live Sender**: ON or OFF badge
- **Pending Approvals**: Count of actions waiting for admin review

### Operator Cards
Six cards summarizing subsystems:
1. **Agent Brain** -- signal extraction, decision engine status
2. **Follow-ups** -- pending, sent, cancelled, failed follow-up counts
3. **Safety** -- stop signals received, blocked actions, daily/lifetime caps
4. **Approval Queue** -- pending proposals with approve/reject buttons
5. **Metrics** -- journey events, lead scores, hot/warm/cold counts
6. **Settings** -- current flag values, recent changes

### Rollout Presets
One-click preset buttons (OFF, LOG_ONLY, DRY_RUN, CANARY, APPROVAL, LIVE SEND). Each preset shows a preview diff before applying.

## Buttons You Must NOT Press

| Button / Preset | Why it is dangerous | When it is safe |
|-----------------|--------------------|-----------------| 
| **CANARY preset** | Sends real messages to canary users | Only after DRY_RUN passes for 24h and canary user IDs are configured |
| **APPROVAL preset** | Sends real messages after admin approval | Only after CANARY passes for 2-4h |
| **LIVE SEND preset** | Sends messages automatically to all users | Only after APPROVAL runs for 2-3 days with admin monitoring |
| **Auto Execute ON** toggle | Approved messages fire automatically | Only at Stage 5 with explicit team agreement |
| **Live Sender ON** toggle | Enables real Telegram sending | Only at Stage 5, never at earlier stages |

**If you are unsure, do not press anything. Apply OFF preset and escalate.**

## How to Read Health Status

| Color | Meaning | Action |
|-------|---------|--------|
| GREEN | All systems normal. Metrics within thresholds. | Continue monitoring. |
| YELLOW | Warning. One or more metrics approaching limits (e.g., failed follow-ups rising, queue growing). | Watch closely. Check follow-up panel and safety panel. If yellow persists >1h, consider rollback. |
| RED | Critical. Thresholds exceeded. Immediate intervention required. | **Rollback immediately.** Apply OFF preset. See Emergency Rollback Card (doc 29). |

## How to Read the Approval Queue

The approval queue shows proposed agent actions waiting for admin review:

| Column | Meaning |
|--------|---------|
| **User** | Telegram user the message would be sent to |
| **Action** | What the agent wants to do (follow-up, closing CTA, catalog nudge) |
| **Risk** | Low / Medium / High badge |
| **Payload** | The actual message text |
| **Expires** | When this proposal expires (30-min TTL by default) |
| **Buttons** | "Tasdiqlash" (Approve) / "Rad etish" (Reject) |

Review guidelines:
- Read the payload text carefully before approving
- Reject if the message mentions specific prices, makes promises, or contains phone numbers
- Reject if the user has sent a stop signal ("kerak emas", "stop")
- Expired proposals are automatically discarded -- this is normal
- A growing queue (>50 pending) means the agent is proposing faster than you can review -- consider rollback

## How to Rollback

### Normal Rollback
1. Open Control Center (`/agent`)
2. Find "Rollout Presets" section
3. Click **Preview** on the **OFF** preset
4. Review the diff -- all agent flags should go to false/disabled
5. Click **Apply OFF**
6. Confirm in the dialog
7. Verify: stage shows OFF, health shows GREEN, live sender OFF

### Emergency Rollback
See `29_EMERGENCY_ROLLBACK_OPERATOR_CARD.md` for the short card.

## Red Flag Situations

**Rollback immediately (apply OFF preset) if ANY of these occur:**

- Health status turns **RED**
- A non-canary user reports receiving an unexpected DM from the bot
- Duplicate messages sent to the same user
- Message text contains raw phone numbers or API tokens
- Failed follow-ups spike (>20 in 24h)
- Scheduler errors repeat (>5 in 1 hour)
- Approval queue grows beyond 50 pending items
- User sends "kerak emas" / "stop" but still receives messages after
- Any user complaint about bot spam

After rollback, preserve logs for investigation. Do not clear data. Notify the admin team.
