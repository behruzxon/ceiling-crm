# Pre-Stage 1 Final Checklist

**Date**: 2026-05-27
**Status**: NOT DEPLOYED, NOT APPLIED

## CI / PR Checklist

- [ ] PR created from feature/vash-ai-hardening-session
- [ ] Ruff check passes (0 errors)
- [ ] Black check passes
- [ ] Mypy passes or non-blocking
- [ ] Unit tests pass (4814+)
- [ ] Integration tests pass (505+)
- [ ] PR reviewed and approved
- [ ] PR merged to main

## VPS Checklist

- [ ] VPS accessible via SSH
- [ ] Docker installed and running
- [ ] docker compose available
- [ ] postgres container running
- [ ] redis container running
- [ ] Git pull latest main on VPS
- [ ] .env file configured with all required vars
- [ ] BOT_TOKEN set (valid Telegram bot token)
- [ ] OPENAI_API_KEY set (valid key)
- [ ] POSTGRES_PASSWORD set
- [ ] BOT_ADMIN_GROUP_ID set (valid admin group)

## Backup Checklist

- [ ] PostgreSQL database backup created
- [ ] Backup verified (can restore)
- [ ] Redis data snapshot if critical
- [ ] .env file backed up
- [ ] Current docker-compose state documented

## Migration Checklist

- [ ] alembic upgrade head completed without error
- [ ] New tables created: crm_operator_handoff_requests
- [ ] Existing tables intact
- [ ] No data loss

## LOG_ONLY Apply Checklist

- [ ] python -c "from apps.bot.main import build_dispatcher" OK
- [ ] python -c "import apps.scheduler.main" OK
- [ ] python -c "from apps.api.main import app" OK
- [ ] python scripts/agent_stage1_readiness_check.py GREEN/YELLOW
- [ ] python scripts/agent_preflight_check.py GREEN/YELLOW
- [ ] All dangerous flags verified OFF in .env:
  - [ ] No ADMIN_SESSION_AUTH_ENABLED=true (unless intentionally enabling)
  - [ ] No CRM_CAMPAIGN_SEND_ENABLED=true
  - [ ] No AGENT_EXECUTION_LIVE_SENDER_ENABLED=true
  - [ ] No AGENT_FOLLOWUPS_ENABLED=true
- [ ] Open /agent dashboard -> Rollout Presets -> LOG_ONLY -> Preview -> Apply
- [ ] Verify: Stage=LOG_ONLY, Health=GREEN
- [ ] Verify: Followups=0, Live sender=OFF, Auto execute=OFF

## No-Send Verification

- [ ] No real Telegram messages sent automatically
- [ ] No campaign broadcasts queued
- [ ] No follow-up messages sent
- [ ] No operator auto-reply
- [ ] Bot only replies to user-initiated messages
- [ ] Admin group notifications are fire-and-forget only

## Post-Apply Test (5 messages)

1. "20 kv qancha" -> trace: wants_price
2. "qimmat ekan" -> trace: price objection
3. "operator kerak" -> trace: wants_operator
4. "kerak emas" -> trace: stop_request
5. Normal greeting -> trace: greeting

## Monitor

- [ ] 30 min active monitoring (no errors in logs)
- [ ] CRM dashboard accessible
- [ ] Agent dashboard shows LOG_ONLY status
- [ ] No unexpected Telegram sends
- [ ] 24h passive observation clean

## Rollback Checklist

If issues found during Stage 1:

1. [ ] Open /agent dashboard -> Rollout Presets -> OFF -> Apply
2. [ ] Verify stage: OFF
3. [ ] Restart bot process: docker compose restart bot
4. [ ] Restart scheduler: docker compose restart scheduler
5. [ ] Verify bot responds normally
6. [ ] Check logs — no errors after rollback
7. [ ] Report issue before retry

**STOP immediately if:**
- User gets unexpected message
- Followup count > 0
- Live sender count > 0
- Health RED
- Error spike in logs
