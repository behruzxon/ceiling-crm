# Stage 1 LOG_ONLY — Execution Plan

## Overview

Stage 1 enables agent observation only. The bot continues working exactly as before. The agent writes traces to memory_data but sends NO messages, schedules NO follow-ups, and triggers NO admin escalations.

## Pre-Execution Checklist

Before applying LOG_ONLY, verify every item:

- [ ] `alembic upgrade head` — all migrations applied
- [ ] `python -c "from apps.bot.main import build_dispatcher"` — bot smoke OK
- [ ] `python -c "import apps.scheduler.main"` — scheduler smoke OK
- [ ] `python scripts/agent_stage1_readiness_check.py` — GREEN or YELLOW (no RED)
- [ ] `python scripts/agent_preflight_check.py` — GREEN or YELLOW
- [ ] `pytest tests/unit/ -q` — all pass
- [ ] `pytest tests/simulation/ -q` — all pass
- [ ] `pytest tests/integration/ -q` — all pass
- [ ] Control Center `/agent` page loads
- [ ] Health status: GREEN
- [ ] Current stage: OFF

## Apply Method

### Option A: Control Center UI (recommended)
1. Open `/agent` dashboard
2. Find "Rollout Presets" section
3. Click **Preview** on LOG_ONLY
4. Review diff — verify only observation flags change
5. Verify no blockers (red)
6. Click **Apply LOG_ONLY**
7. Confirm in dialog

### Option B: API
```
POST /api/v1/admin/agent/settings/presets/log_only/preview
POST /api/v1/admin/agent/settings/presets/log_only/apply
{"confirmation_token": "<from preview>", "reason": "Stage 1 trial"}
```

### Option C: .env (fallback)
Add to .env:
```
AGENT_LEAD_SIGNAL_ENABLED=true
AGENT_LEAD_SCORING_ENABLED=true
AGENT_DECISION_ENGINE_ENABLED=true
AGENT_DYNAMIC_OFFER_ENABLED=true
AGENT_CONVERSATION_POLICY_ENABLED=true
AGENT_RESPONSE_ORCHESTRATOR_ENABLED=true
AGENT_RESPONSE_ORCHESTRATOR_LOG_ONLY=true
```
Then restart bot + scheduler.

## Post-Apply Verification

Immediately after apply:

- [ ] Dashboard stage shows: **LOG_ONLY**
- [ ] Health: GREEN
- [ ] Followups enabled: **false**
- [ ] Live sender: **OFF**
- [ ] Auto execute: **OFF**
- [ ] Admin escalation: **OFF**

## Manual Test (5 minutes)

Send from admin test account:

| # | Send | Verify in Dashboard | Must NOT happen |
|---|------|--------------------|-----------------| 
| 1 | "20 kv qancha" | wants_price signal in trace | Follow-up scheduled |
| 2 | "qimmat ekan" | price objection in trace | Agent DM to user |
| 3 | "нархи қанча" | Cyrillic detected, wants_price | Different bot behavior |
| 4 | "operator kerak" | wants_operator signal | Admin escalation |
| 5 | "kerak emas" | stop_request signal | Any future agent action |

## Observation Window

- **First 30 min**: Active monitoring, check dashboard every 5 min
- **First 2 hours**: Check every 15 min
- **First 24 hours**: Check every 1-2 hours during business hours
- **After 24h**: Daily checklist (doc 27)

## Metrics to Monitor

| Metric | Expected | Hard Stop If |
|--------|----------|-------------|
| Health | GREEN | RED |
| Pending followups | 0 | >0 |
| Executed actions | 0 | >0 |
| Live sender activity | 0 | >0 |
| Admin escalations | 0 | >0 |
| User complaints | 0 | >0 |
| Bot response change | None | Any change |

## Hard Stop → Rollback

If ANY hard stop condition triggers:

1. **Apply OFF preset** (Control Center or API)
2. Verify stage: OFF
3. Verify health: GREEN
4. Restart if needed: `docker compose restart bot scheduler`
5. Report to admin group

See `29_EMERGENCY_ROLLBACK_OPERATOR_CARD.md`

## Success Criteria

After 24h observation:
- [ ] Health stayed GREEN
- [ ] Zero unexpected messages sent
- [ ] Zero follow-ups scheduled
- [ ] Traces written successfully
- [ ] Dashboard shows activity
- [ ] Bot behavior unchanged
- [ ] No user complaints

If all pass → Stage 1 complete, ready for Stage 2 DRY_RUN evaluation.
