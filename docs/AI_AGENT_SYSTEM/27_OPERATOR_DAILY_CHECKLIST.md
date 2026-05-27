# Operator Daily Checklist

Run through this checklist at the start of each shift. Open the Control Center dashboard at `/agent` and verify each item.

**Date:** _______________  
**Operator:** _______________  
**Shift:** _______________

---

## Dashboard Access

- [ ] Control Center dashboard loads at `/agent` without errors
- [ ] Page shows current data (not stale/cached -- check timestamp)

## Health and Stage

- [ ] Health status is **GREEN** or **YELLOW** (not RED)
- [ ] If YELLOW: note the warning reason here: _______________
- [ ] Current rollout stage matches the expected stage: _______________
- [ ] Stage has not changed since last shift (unless a planned change was scheduled)

## Approval Queue

- [ ] Pending approvals count is normal (expected range: 0-10 for APPROVAL stage, 0 for earlier stages)
- [ ] No proposals older than 30 minutes (expired items should auto-clear)
- [ ] No rejected proposals reappearing

## Follow-ups

- [ ] Pending follow-ups count is within normal range (<50)
- [ ] Failed follow-ups in last 24h: ___ (threshold: <5)
- [ ] No spike in cancelled follow-ups

## Safety Panel

- [ ] Stop signals are being recorded (count increasing naturally, not stuck at zero in active hours)
- [ ] Blocked actions count is stable (not spiking)
- [ ] Daily cap (3/user/day) and lifetime cap (5 total) are active and enforced

## Sender Status

- [ ] **Live Sender** is OFF (unless current stage is 5 - LIVE SEND)
- [ ] **Auto Execute** is OFF (unless current stage is 5 - LIVE SEND and explicitly approved)

## External Checks

- [ ] No unexpected user complaints in admin Telegram group
- [ ] Bot responds normally to test message (send "/start" from test account)
- [ ] Scheduler is running (check `docker compose ps scheduler` or dashboard scheduler indicator)

---

## Action Items

If any checkbox above is NOT checked:

| Severity | Condition | Action |
|----------|-----------|--------|
| **Critical** | Health RED | Rollback to OFF immediately (see doc 29) |
| **Critical** | Unexpected stage change | Rollback to OFF, investigate audit log |
| **Critical** | Live Sender ON at wrong stage | Rollback to OFF immediately |
| **High** | Failed follow-ups >5 | Escalate to admin, consider rollback |
| **High** | Pending approvals >50 | Escalate to admin, consider rollback |
| **Medium** | Health YELLOW >1h | Monitor closely, prepare for rollback |
| **Medium** | Dashboard not loading | Check server status, restart if needed |
| **Low** | Minor metric anomaly | Note and monitor next check |

## Sign-off

- Checklist completed: [ ] Yes
- Issues found: [ ] None / [ ] Yes (see notes above)
- Escalated to: _______________

Signature: _______________
