# Stage 1 LOG_ONLY — Final Apply Pack (Latest)

**Date**: 2026-05-27
**Branch**: feature/vash-ai-hardening-session
**Latest Commit**: a1216e2
**Tests**: 5520 passing (4946 unit + 574 integration/simulation)
**Deploy**: NO
**VPS**: NO
**Flags**: NOT ENABLED
**Stage 1 LOG_ONLY**: NOT APPLIED

## A) Current Baseline

| Item | Status |
|------|--------|
| AI knowledge base | Hardened (8 sections + forbidden claims + room recs) |
| Price calculator | Wired into bot (deterministic, DESIGN_PRICES_CUSTOMER) |
| Operator handoff | Queue foundation wired (ETA-safe, dedup, priority) |
| AI button UX | 6 quick buttons + /ai_help + /ai_reset |
| Compare objection | Fixed (8 new keywords) |
| Room recommendations | Added (6 rooms) |
| Quality simulator | 70+ scenarios, all safe |
| Handler tests | All 6 handlers covered |
| Ruff/black | Clean |
| Bot/scheduler/API smoke | OK |

## B) Latest Commits Summary

1. d3fc6f3 — AI knowledge hardening (45 files)
2. 9bcfcdf — Operator handoff queue foundation
3. 72ca769 — Price calculator source-of-truth
4. 5c29f31 — Bot service wiring (price + handoff)
5. 8d02106 — Ruff auto-fix
6. 3dddc97 — Ruff config + black format
7. 96d5b3b — Deep improvement audit docs
8. 089ace5 — Agent quality simulator (132 tests)
9. a1216e2 — Agent decision fixes (objection + room recs)

## C) What Changed Since Old Checklist

- Commit ref: e0fc58a -> a1216e2
- Tests: 3968 -> 5520 (+1552)
- New services: PriceCalculatorService, CRMOperatorHandoffService, AgentQualitySimulatorService
- New migration: crm_operator_handoff_requests table
- Knowledge base: 8 new sections, price fixes, room recommendations
- System prompt: versioned, 3 safety blocks added
- Compare objection: 8 new keywords
- AI keyboard: 1 button -> 6 buttons

## D) Final Readiness Verdict

**CONDITIONAL GO**

Conditions before apply:
1. PR merged or branch deployed from feature/vash-ai-hardening-session
2. VPS accessible with Docker + postgres + redis
3. DB backup completed
4. alembic upgrade head successful (new table: crm_operator_handoff_requests)
5. .env configured with all required vars

## E) Pre-Apply Checklist

- [ ] DB backup completed and verified
- [ ] Git pull latest commit (a1216e2 or later)
- [ ] Git status CLEAN
- [ ] alembic upgrade head completed without error
- [ ] python -c "from apps.bot.main import build_dispatcher" OK
- [ ] python -c "import apps.scheduler.main" OK
- [ ] python -c "from apps.api.main import app" OK
- [ ] python scripts/agent_stage1_readiness_check.py GREEN/YELLOW
- [ ] All dangerous flags verified OFF in .env:
  - [ ] No AGENT_EXECUTION_LIVE_SENDER_ENABLED=true
  - [ ] No AGENT_FOLLOWUPS_ENABLED=true
  - [ ] No CRM_CAMPAIGN_SEND_ENABLED=true
  - [ ] No CRM_OPERATOR_REPLY_ENABLED=true
  - [ ] No ADMIN_SECURITY_ACTIONS_ENABLED=true
  - [ ] No ADMIN_IP_BLOCK_ENFORCEMENT_ENABLED=true

## F) Migration Checklist

- [ ] alembic upgrade head
- [ ] New table created: crm_operator_handoff_requests
- [ ] Existing tables intact
- [ ] No data loss

## G) LOG_ONLY Apply Steps

1. Open /agent dashboard
2. Rollout Presets -> LOG_ONLY -> Preview -> Apply
3. Restart bot process
4. Restart scheduler process
5. Verify: Stage=LOG_ONLY, Health=GREEN
6. Verify: Followups=0, Live sender=OFF, Auto execute=OFF

## H) Bot Test Scenarios (6 messages)

1. "20 kv gulli qancha" -> deterministic price estimate (PriceCalculatorService)
2. "5x4 led qancha" -> deterministic price estimate (area=20, design=hi-tech)
3. "boshqalar arzon ekan" -> compare objection detected
4. "operator kerak" -> ETA-safe handoff message (no fake time promise)
5. "kerak emas" -> stop signal, no follow-up
6. "нархи қанча" -> Cyrillic price detection

## I) Observation Checklist

### 30 min active
- [ ] Bot responding normally to all 6 test messages
- [ ] Price calculator returns formatted estimates
- [ ] Handoff queue records created (check DB)
- [ ] Compare objection triggers correct response
- [ ] Stop request disables followups
- [ ] No unexpected Telegram sends
- [ ] No error spike in logs
- [ ] CRM dashboard accessible
- [ ] Agent dashboard shows LOG_ONLY status

### 24h passive
- [ ] No user complaints
- [ ] No permission errors
- [ ] No memory leaks
- [ ] No fake ETA in any response
- [ ] No final price guarantee in any response
- [ ] No live sender activity
- [ ] No followup scheduled
- [ ] No admin escalation unless expected
- [ ] No campaign sends

## J) Stop/Rollback Triggers

**STOP immediately if:**
- User gets unexpected message
- Followup count > 0
- Live sender count > 0
- Health RED
- Error spike in logs
- Fake ETA detected in response
- "eng arzon" detected in response
- Admin group flooded with notifications

## K) Rollback Steps

1. Open /agent dashboard -> Rollout Presets -> OFF -> Apply
2. Verify stage: OFF
3. Restart bot: docker compose restart bot
4. Restart scheduler: docker compose restart scheduler
5. Verify bot responds normally
6. Check logs — no errors after rollback
7. Report issue before retry

## L) Final Recommendation

**Apply Stage 1 LOG_ONLY when:**
- VPS is accessible
- DB backup is done
- Migration is complete
- All pre-apply checks pass
- 30 min active monitoring time available

**Do NOT:**
- Enable live sender
- Enable followups
- Enable campaign send
- Skip DB backup
- Apply without monitoring time
