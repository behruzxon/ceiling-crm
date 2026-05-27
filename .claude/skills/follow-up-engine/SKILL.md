# Skill: Follow-Up Engine

Design, implement, and review the automated follow-up system for CeilingCRM. This skill covers timing, cooldowns, stop conditions, and testing requirements.

## Core Delay Schedule

| Trigger Event | Delay | Message Type |
|---------------|-------|--------------|
| Catalog viewed | 10 min | "Katalogda qaysi dizayn yoqdi?" + CTA |
| Price calculated | 10 min | "Narx ma'qul bo'ldimi?" + order CTA |
| Order started but not finished | 10 min | "Buyurtmangiz tugallanmadi" + continue CTA |
| Phone number captured | 15 min | "Operator tez orada bog'lanadi" + status |
| Soft reminder (no reply) | 24 hours | Personalized reminder with last context |
| Final attempt | 72 hours | Gentle final check + opt-out option |

## Cooldown Rules

- **Minimum gap**: 1 hour between any two follow-up messages to the same user
- **Hourly cap**: Max 2 follow-up messages per user per hour
- **Daily cap**: Max 5 automated messages per user per day (across all types)
- **Total cap**: Max 5 follow-up messages per user per lead lifecycle
- **Closing attempt cooldown**: 10 minutes minimum between closing attempts
- **Implementation**: Redis key `followup:cooldown:{user_id}` with TTL = cooldown period

## Stop Conditions

The follow-up engine MUST stop sending messages when any of these conditions is true:

1. **User replied** — Any message from the user resets the follow-up chain
2. **User ordered** — Lead status changed to DEAL or later pipeline stage
3. **User opted out** — User sent "kerak emas", "stop", "yoq", "rahmat, kerak emas"
4. **Operator requested** — User asked for human operator (set opt-out flag)
5. **Bot blocked** — TelegramForbiddenError received (add to blocked_chats)
6. **Max reached** — Total follow-up count >= 5
7. **Active conversation** — User's last message was less than 5 minutes ago
8. **Admin escalated** — Lead already escalated to admin (avoid duplicate pressure)

## Duplicate Prevention

- Use Redis NX (set-if-not-exists) for dedup keys
- Key format: `followup:sent:{user_id}:{event_type}:{event_id}`
- TTL: same as the cooldown period for that follow-up type
- Before sending any follow-up, check:
  1. Is the dedup key set? If yes, skip
  2. Is the cooldown key set? If yes, skip
  3. Has the daily cap been reached? If yes, skip
  4. Has any stop condition been triggered? If yes, skip

## Scheduler and Execution

- **Polling**: APScheduler checks for due follow-ups every 60 seconds
- **Execution**: Celery tasks handle actual message sending (async, retryable)
- **Persistence**: `scheduled_followups` table stores pending follow-ups (survives restarts)
- **Columns**: id, user_id, lead_id, event_type, scheduled_at, sent_at, status (pending/sent/cancelled/failed)
- **On restart**: APScheduler picks up all pending follow-ups from DB on startup
- **Idempotency**: check `sent_at IS NULL` before sending; set `sent_at` atomically

## Anti-Spam Hard Caps

These are non-negotiable limits that must never be exceeded:

| Limit | Value | Scope |
|-------|-------|-------|
| Messages per user per day | 5 | All automated message types combined |
| Follow-ups per hour | 2 | Per user |
| Follow-ups per lead lifecycle | 5 | Per user per lead |
| Closing attempts per day | 3 | Per user |
| Gap between messages | 1 hour min | Per user |
| Active conversation buffer | 5 min | Skip if user messaged recently |

## Admin Escalation

After 2 consecutive unanswered follow-ups:
1. Stop sending follow-ups to the user
2. Send admin notification with lead context (name, phone, area, last message, score)
3. Mark lead as `escalated` in follow-up tracking
4. Include quick-action buttons for admin: Call, Assign, Archive

## Message Personalization

Every follow-up message should include relevant context from agent memory:
- User's name (if known)
- Design they viewed or asked about
- Price they calculated
- Area they mentioned
- Package they selected
- Last objection or question

Template example:
```
{name}, {design} uchun {area} m² narx {price} so'm edi.
Buyurtma berasizmi? 😊
```

## Testing Requirements

Every follow-up rule must have a corresponding unit test:

- Test: follow-up sent after correct delay
- Test: follow-up NOT sent if cooldown active
- Test: follow-up NOT sent if daily cap reached
- Test: follow-up NOT sent if user replied
- Test: follow-up NOT sent if user opted out
- Test: follow-up NOT sent if bot blocked
- Test: follow-up NOT sent if active conversation
- Test: dedup key prevents duplicate sends
- Test: admin escalation after 2 unanswered
- Test: follow-up resumes after bot restart (from DB)

Use `freezegun` or manual time mocking to test delay/cooldown logic:
```python
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta

# Mock "now" to test timing
with patch("core.services.followup_service.datetime") as mock_dt:
    mock_dt.now.return_value = datetime(2024, 1, 1, 12, 0)
    # ... test that follow-up is not yet due

    mock_dt.now.return_value = datetime(2024, 1, 1, 12, 11)
    # ... test that follow-up is now due (10 min passed)
```

## Implementation Checklist

When building or extending the follow-up engine:

- [ ] Define follow-up type enum in `shared/constants/enums.py`
- [ ] Create or extend `scheduled_followups` model
- [ ] Create migration for new columns/tables
- [ ] Implement service in `core/services/followup_service.py`
- [ ] Add DI factory in `infrastructure/di.py`
- [ ] Register scheduler job in `apps/scheduler/`
- [ ] Create Celery task in `infrastructure/queue/tasks/`
- [ ] Add Redis key definitions to `infrastructure/cache/keys.py`
- [ ] Write unit tests for all rules
- [ ] Test with real Telegram bot in dev environment
