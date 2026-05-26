# Stage 1 Emergency Rollback Card

## Immediate Action

1. **Apply OFF preset** via Control Center or API:
   ```
   POST /api/v1/admin/agent/settings/presets/off/apply
   {"confirmation_token": "", "reason": "emergency rollback"}
   ```

2. **Verify stage OFF** — check `/agent` dashboard, stage should show OFF

3. **Clear cache** — automatic after preset apply

4. **Restart if needed**:
   ```
   docker compose restart bot
   docker compose restart scheduler
   ```

5. **Check dashboard** — health green, no pending actions

## Verify Rollback

- Stage: OFF
- All agent flags: false
- No pending followups from agent
- No pending approvals from agent
- Bot behavior: back to normal
- Dashboard: no red indicators

## Contact

- Admin Telegram group for alerts
- Check logs for errors before restart
