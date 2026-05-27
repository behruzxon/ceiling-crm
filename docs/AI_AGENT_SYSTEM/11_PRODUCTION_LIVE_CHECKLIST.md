# 11 — Production Live Checklist

## 1. Required Environment Variables

```env
# Master switch (set true only when ready)
AGENT_FOLLOWUPS_ENABLED=false

# Individual follow-up types
AGENT_CATALOG_FOLLOWUP_ENABLED=false
AGENT_PRICE_FOLLOWUP_ENABLED=false
AGENT_ORDER_FOLLOWUP_ENABLED=false

# Delays (minutes)
AGENT_CATALOG_FOLLOWUP_DELAY_MINUTES=10
AGENT_PRICE_FOLLOWUP_DELAY_MINUTES=10
AGENT_ORDER_FOLLOWUP_DELAY_MINUTES=10

# Admin escalation
AGENT_ADMIN_ESCALATION_ENABLED=false
AGENT_ADMIN_ESCALATION_AFTER_FOLLOWUPS=2
AGENT_ADMIN_ESCALATION_COOLDOWN_MINUTES=60

# AI composer
AGENT_AI_COMPOSER_ENABLED=false
AGENT_AI_COMPOSER_MODEL=gpt-4o-mini
AGENT_AI_COMPOSER_TIMEOUT_SECONDS=8
AGENT_AI_COMPOSER_MAX_TOKENS=180
```

## 2. Pre-Deploy Checklist

- [ ] `alembic upgrade head` — 4 new migrations applied
- [ ] `BOT_ADMIN_GROUP_ID` set — required for escalation alerts
- [ ] `OPENAI_API_KEY` set — required if AI composer enabled
- [ ] All `AGENT_*` flags set to `false` initially
- [ ] Bot restarted after `.env` changes
- [ ] Scheduler restarted after `.env` changes
- [ ] Redis running and accessible
- [ ] PostgreSQL running, migrations applied

## 3. Staged Rollout Plan

### Phase 1: Catalog follow-up only (1-3 days)
```env
AGENT_FOLLOWUPS_ENABLED=true
AGENT_CATALOG_FOLLOWUP_ENABLED=true
```
Monitor: follow-up sent count, user complaints, unsubscribe rate.

### Phase 2: Add price follow-up (3-5 days)
```env
AGENT_PRICE_FOLLOWUP_ENABLED=true
```
Monitor: price follow-up response rate, order conversion.

### Phase 3: Add abandoned order (5-7 days)
```env
AGENT_ORDER_FOLLOWUP_ENABLED=true
```
Monitor: order recovery rate, form completion after follow-up.

### Phase 4: Admin escalation (7-10 days)
```env
AGENT_ADMIN_ESCALATION_ENABLED=true
```
Monitor: admin alert volume, response time improvement.

### Phase 5: AI composer (10+ days)
```env
AGENT_AI_COMPOSER_ENABLED=true
```
Monitor: OpenAI cost, message quality, fallback rate.

## 4. Rollback

Instant rollback — set any flag to `false`:
```env
AGENT_FOLLOWUPS_ENABLED=false  # kills everything
```
No migration rollback needed. Data stays safe.

## 5. Anti-Spam Safety

| Guard | Value | Where |
|-------|-------|-------|
| Daily cap | 3 per user | Redis + DB fallback |
| Min gap | 10 min | Redis + DB fallback |
| Lifetime cap | 5 per user | DB column |
| Per-type dedup | 24h/2h/6h | Redis NX |
| followup_enabled flag | Boolean | DB column |
| Stop words | 10 UZ/RU words | Handler check |
| Business hours | 09:00-20:00 Toshkent | Scheduler check |
| Feature flags | All default false | Settings |

## 6. Monitoring

### Log events to watch
```
agent_followups_sent       — count of follow-ups sent per cycle
agent_followups_deferred   — rescheduled due to off-hours
followup_send_error        — Telegram API error
followup_rate_limited      — Telegram 429
ai_composer_timeout        — OpenAI slow
ai_composer_invalid        — AI output failed validation
ai_composer_error          — OpenAI API error
admin_escalations_sent     — admin alerts sent
stop_signal_handler_error  — stop word processing failed
journey_event_emit_failed  — event tracking failed
```

### Key metrics
- Follow-ups sent per hour (should be < 50 for typical traffic)
- Fallback rate (AI invalid / total AI calls, target < 10%)
- Admin escalation rate (should decrease over time)
- Stop signal rate (high = possible spam perception)

## 7. Restart Commands

```bash
# Bot restart
docker compose restart bot

# Scheduler restart
docker compose restart scheduler

# Both
docker compose restart bot scheduler

# Check logs
docker compose logs -f bot --tail=50
docker compose logs -f scheduler --tail=50
```

## 8. Cost Guard

OpenAI cost per follow-up (gpt-4o-mini):
- Input: ~200 tokens = $0.00003
- Output: ~100 tokens = $0.00006
- Total: ~$0.0001 per call
- 100 follow-ups/day = $0.01/day = $0.30/month

If `AGENT_AI_COMPOSER_ENABLED=false`, OpenAI cost = $0.

## 9. Feature Flag Matrix

| FOLLOWUPS | CATALOG | PRICE | ORDER | ESCALATION | AI | Result |
|-----------|---------|-------|-------|------------|-----|--------|
| false | any | any | any | any | any | Everything off |
| true | false | false | false | false | false | Events tracked, no follow-ups |
| true | true | false | false | false | false | Catalog follow-up only, deterministic |
| true | true | true | false | false | false | Catalog + price, deterministic |
| true | true | true | true | false | false | All follow-ups, deterministic |
| true | true | true | true | true | false | + admin alerts |
| true | true | true | true | true | true | Full AI agent mode |

## 10. Dev/Test Quick Start

```env
AGENT_FOLLOWUPS_ENABLED=true
AGENT_CATALOG_FOLLOWUP_ENABLED=true
AGENT_PRICE_FOLLOWUP_ENABLED=true
AGENT_ORDER_FOLLOWUP_ENABLED=true
AGENT_ADMIN_ESCALATION_ENABLED=true
AGENT_AI_COMPOSER_ENABLED=false
AGENT_CATALOG_FOLLOWUP_DELAY_MINUTES=1
AGENT_PRICE_FOLLOWUP_DELAY_MINUTES=1
AGENT_ORDER_FOLLOWUP_DELAY_MINUTES=1
AGENT_ADMIN_ESCALATION_AFTER_FOLLOWUPS=1
AGENT_ADMIN_ESCALATION_COOLDOWN_MINUTES=5
```

Test scenario:
1. `/start` → Katalog → 1 min → follow-up keladi
2. Stop word yoz → follow-up to'xtaydi
3. Yangi user → Narx hisoblash → 1 min → price follow-up
4. Yangi user → Zakaz → ism kiritish → 1 min → abandoned order follow-up
5. Jim turish → admin alert keladi (admin guruhda)
