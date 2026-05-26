# Emergency Rollback Card

Print this card. Keep it visible at your workstation.

---

## Step 1 -- Apply OFF Preset

Open Control Center (`/agent`) and apply the **OFF** preset:

1. Find "Rollout Presets"
2. Click **OFF** > **Apply**
3. Confirm

If dashboard is unreachable, set these in `.env` and restart:

```
AGENT_RESPONSE_ORCHESTRATOR_ENABLED=false
AGENT_EXECUTION_SANDBOX_ENABLED=false
AGENT_EXECUTION_QUEUE_ENABLED=false
AGENT_EXECUTION_LIVE_SENDER_ENABLED=false
AGENT_FOLLOWUPS_ENABLED=false
AGENT_EXECUTION_AUTO_EXECUTE_APPROVED=false
```

## Step 2 -- Verify

- [ ] Stage shows **OFF**
- [ ] Live Sender shows **OFF**
- [ ] Health shows **GREEN**
- [ ] Pending approvals: **0** (or expiring)

## Step 3 -- Restart (if needed)

```
docker compose restart bot
docker compose restart scheduler
```

## Step 4 -- Contact

- Post in the **admin Telegram group** immediately
- State: what happened, when, what you did
- Preserve all logs -- do not clear or delete anything

---

**Remember: it is always safe to apply OFF. When in doubt, rollback first, investigate later.**
