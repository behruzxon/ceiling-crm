# Stage 1 LOG_ONLY — Go/No-Go Checklist

## Pre-Apply

- [ ] DB backup completed
- [ ] Git pull latest commit (e0fc58a or later)
- [ ] Git status CLEAN
- [ ] `alembic upgrade head` completed without error
- [ ] `python -c "from apps.bot.main import build_dispatcher"` OK
- [ ] `python -c "import apps.scheduler.main"` OK
- [ ] `python -c "from apps.api.main import app"` OK
- [ ] `python scripts/security_enablement_preflight.py` GREEN/YELLOW (no RED)
- [ ] All dangerous flags verified OFF in .env
- [ ] No ADMIN_SESSION_AUTH_ENABLED=true
- [ ] No CRM_CAMPAIGN_SEND_ENABLED=true
- [ ] No AGENT_EXECUTION_LIVE_SENDER_ENABLED=true

## Apply Stage 1

- [ ] Set agent flags to LOG_ONLY preset (observation only)
- [ ] Restart bot process
- [ ] Restart scheduler process
- [ ] Open /agent dashboard — verify status
- [ ] Send 5 test messages to bot
- [ ] Check logs — no errors
- [ ] Check admin group — no unexpected notifications

## Observe (30 min)

- [ ] Bot responding normally
- [ ] No unexpected Telegram sends
- [ ] No error spike in logs
- [ ] CRM dashboard accessible
- [ ] Agent dashboard shows LOG_ONLY status

## Observe (24h)

- [ ] No user complaints
- [ ] No permission errors
- [ ] No memory leaks
- [ ] Stage 1 observation report clean

## Rollback

If issues found:
1. Set all agent flags to OFF preset
2. Restart bot + scheduler
3. Verify bot responds normally
4. Report issue before retry
