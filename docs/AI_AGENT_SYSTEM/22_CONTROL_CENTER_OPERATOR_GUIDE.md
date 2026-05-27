# Agent Control Center — Operator Guide

## Overview

The Agent Control Center at `/agent` provides real-time visibility into the AI agent system. It is **read-only by default** — settings mutation requires explicit flag activation.

## Sections

### Agent Status Header
Shows at-a-glance: current rollout stage, health status, mutation/runtime/live-sender status, and pending approval count.

### Operator Status Cards
Six cards: Agent Brain, Follow-ups, Safety, Approval Queue, Metrics, Settings. Each shows current status and action hints.

### Rollout Stage Timeline
Visual 7-stage progression: OFF → LOG_ONLY → DRY_RUN → CANARY → APPROVAL → LIVE SEND → LIMITED LIVE. Current stage is highlighted. Dangerous future stages show warnings.

### Rollout Presets
One-click stage presets with preview → diff → confirmation → apply flow. Critical presets blocked unless explicitly allowed.

### Overview Cards
Key metrics: journey events, hot/warm/cold leads, pending followups, pending approvals, executed/blocked actions.

### Follow-up & Safety Panels
Follow-up status (pending/sent/cancelled/failed/due) and safety metrics (stop signals, blocked actions, caps).

### Approval Queue
Pending execution records with approve/reject buttons. Only visible to admins.

### Settings Control
Feature flags table with toggle/preview/apply flow. Grouped by category, source/risk badges.

### Audit Log
History of settings changes with rollback buttons.

## How To

### Read the stage
- **OFF**: Agent fully disabled, no impact
- **LOG_ONLY**: Agent observes and writes traces, no user impact
- **DRY_RUN**: Payloads validated but not sent
- **CANARY**: Only canary users affected
- **APPROVAL**: Admin must approve each action
- **LIVE SEND**: Approved actions sent automatically

### Apply LOG_ONLY preset
1. Find "Rollout Presets" section
2. Click "Preview" on LOG_ONLY
3. Review the diff (which flags change)
4. If no blockers, click "Apply LOG_ONLY"
5. Confirm in the dialog
6. Stage should update to LOG_ONLY

### Approve/Reject execution
1. Find "Pending executions" table
2. Review action, risk, user, expiry
3. Click "Tasdiqlash" (Approve) or "Rad etish" (Reject)
4. Approved actions will be sent when live sender is enabled

### Rollback
1. Open "Audit Log" in Settings Control
2. Find the change to rollback
3. Click "Rollback"
4. Or apply "OFF" preset to reset everything

## What NOT to touch
- Do not enable LIVE SEND without completing all previous stages
- Do not bypass confirmation tokens
- Do not set canary mode without configuring canary user IDs
- Do not disable daily/lifetime caps

## Stop/Rollback conditions
Immediately rollback to OFF if:
- Health status is RED
- Failed followups spike
- Non-canary user receives agent message
- User complaints increase
- Scheduler errors repeated
