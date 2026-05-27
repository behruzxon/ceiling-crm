# Next Session — Stage 1 LOG_ONLY Apply

When PC/VPS is available, follow these steps exactly.

## 1. Pre-checks
```
alembic upgrade head
python scripts/agent_stage1_readiness_check.py
python scripts/agent_preflight_check.py
python -c "from apps.bot.main import build_dispatcher"
python -c "import apps.scheduler.main"
```
All must pass (GREEN or YELLOW, no RED).

## 2. Apply LOG_ONLY
Open `/agent` dashboard → Rollout Presets → LOG_ONLY → Preview → Apply

## 3. Verify
- Stage: LOG_ONLY
- Health: GREEN
- Followups: 0
- Live sender: OFF
- Auto execute: OFF

## 4. Test (5 messages to bot)
1. "20 kv qancha" → trace: wants_price
2. "qimmat ekan" → trace: price objection
3. "нархи қанча" → trace: Cyrillic wants_price
4. "operator kerak" → trace: wants_operator
5. "kerak emas" → trace: stop_request

## 5. Monitor
- 30 min active monitoring
- 24h passive observation
- Check /agent dashboard periodically

## 6. Rollback (if needed)
OFF preset Apply → verify stage OFF → restart if needed

## 7. STOP immediately if
- User gets unexpected message
- Followup count > 0
- Live sender count > 0
- Health RED
