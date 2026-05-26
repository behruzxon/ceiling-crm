# 06 — Events and Triggers

> Event system architecture: how user actions flow through the system,
> trigger follow-ups, and drive the AI sales funnel.

---

## 1. Event Schema

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class JourneyEvent:
    """Immutable record of a customer journey milestone."""
    event_id: str          # UUID v4
    user_id: int           # Telegram user ID
    event_type: str        # From JourneyEventType enum
    timestamp: datetime    # UTC
    metadata: dict         # Event-specific payload (JSON-serializable)
    source_handler: str    # Which handler file emitted this event
```

---

## 2. Event Types

```python
from enum import Enum


class JourneyEventType(str, Enum):
    # ── Bot lifecycle ──────────────────────────────────
    STARTED_BOT              = "started_bot"
    # ── Catalog engagement ─────────────────────────────
    OPENED_CATALOG           = "opened_catalog"
    VIEWED_CATALOG_ITEM      = "viewed_catalog_item"
    # ── Price calculation ──────────────────────────────
    USED_PRICE_CALCULATOR    = "used_price_calculator"
    PRICE_CALCULATED         = "price_calculated"
    # ── Order funnel ───────────────────────────────────
    CLICKED_ORDER            = "clicked_order"
    ORDER_FORM_STARTED       = "order_form_started"
    ORDER_FORM_STEP_COMPLETED = "order_form_step_completed"
    ORDER_FORM_ABANDONED     = "order_form_abandoned"
    # ── Contact collection ─────────────────────────────
    PHONE_SHARED             = "phone_shared"
    LOCATION_SHARED          = "location_shared"
    IMAGE_SENT               = "image_sent"
    # ── Human handoff ──────────────────────────────────
    OPERATOR_REQUESTED       = "operator_requested"
    # ── AI interaction ─────────────────────────────────
    AI_QUESTION_ASKED        = "ai_question_asked"
    OBJECTION_DETECTED       = "objection_detected"
    # ── Follow-up lifecycle ────────────────────────────
    FOLLOWUP_SENT            = "followup_sent"
    FOLLOWUP_REPLIED         = "followup_replied"
    # ── Admin actions ──────────────────────────────────
    ADMIN_NOTIFIED           = "admin_notified"
    # ── Terminal states ────────────────────────────────
    DEAL_CLOSED              = "deal_closed"
    LOST_LEAD                = "lost_lead"
```

---

## 3. Trigger Mapping Table

### 3.1 User-initiated events

| Event Type | Source Handler | Trigger Condition | Follow-up Action | Delay | Redis Key for State |
|-----------|---------------|-------------------|-----------------|-------|-------------------|
| `STARTED_BOT` | `support.py` | `/start` command | Show main menu + greeting | Immediate | - |
| `OPENED_CATALOG` | `catalog.py` | "Katalog" button or `/catalog` | Schedule catalog follow-up | 5-10 min | `madina:catalog_followup:{uid}` |
| `VIEWED_CATALOG_ITEM` | `catalog.py` | Inline button tap on design | Score +5 | Immediate | - |
| `USED_PRICE_CALCULATOR` | `pricing.py` | "Narx" button or `/price` | Wait for area input | Immediate | - |
| `PRICE_CALCULATED` | `ai_pricing_helpers.py` | Area + design submitted | Price follow-up if no action | 10 min | `madina:followup_nonce:{uid}` |
| `CLICKED_ORDER` | `order.py` | "Buyurtma" button or `/order` | Start order FSM | Immediate | - |
| `ORDER_FORM_STARTED` | `order.py` | First step answered | Track progress in memory | Immediate | - |
| `ORDER_FORM_STEP_COMPLETED` | `order.py` | Each form step answered | Update `order_form_progress` | Immediate | - |
| `ORDER_FORM_ABANDONED` | `order.py` | FSM timeout or exit during form | Abandoned form follow-up | 10 min | `madina:followup_nonce:{uid}` |
| `PHONE_SHARED` | `lead_capture.py`, `ai_support.py` | Contact shared or phone regex matched | Admin notification, score +40 | Immediate | `ai:score:{uid}` |
| `LOCATION_SHARED` | `lead_capture.py` | Location message sent | Attach to lead record | Immediate | - |
| `IMAGE_SENT` | `ai_support.py` | Photo message in AI mode | Enter photo funnel | Immediate | - |
| `OPERATOR_REQUESTED` | `operator.py` | "Operator" button or keyword | Admin notification + handoff | Immediate | - |
| `AI_QUESTION_ASKED` | `ai_support.py` | Free-text message in AI state | Refresh follow-up nonce | Immediate | `madina:followup_nonce:{uid}` |
| `OBJECTION_DETECTED` | `ai_scoring.py` | Keyword/regex match | Negotiation reply + score adjust | Immediate | - |

### 3.2 System-initiated events

| Event Type | Source Handler | Trigger Condition | Follow-up Action | Delay | Redis Key for State |
|-----------|---------------|-------------------|-----------------|-------|-------------------|
| `FOLLOWUP_SENT` | `ai_followups.py` | Timer expired, nonce valid | Send reminder message | 10 min / 60 min | `ai:followup_state:{uid}` |
| `FOLLOWUP_REPLIED` | `ai_support.py` | User responds after follow-up | Cancel pending follow-ups | Immediate | `madina:followup_nonce:{uid}` (refreshed) |
| `ADMIN_NOTIFIED` | `ai_notifications.py` | Lead collected (phone+district) | Full intelligence card to admin | Immediate | `lead:{id}:card_sent` |
| `DEAL_CLOSED` | `lead_status.py` | Admin marks lead as "deal" | Clear `next_follow_up_at` | Immediate | - |
| `LOST_LEAD` | `followup_jobs.py` | 7 days no response | Mark lead_status = "lost" | After 168h | - |

---

## 4. Follow-up Timer Architecture

### 4.1 In-process timers (asyncio.sleep)

Used for short-lived, user-scoped follow-ups during an active bot session.

```
User action → asyncio.create_task(_followup_task(...))
                   ↓
              asyncio.sleep(N * 60)
                   ↓
              Check nonce → still valid?
                   ├── YES → send follow-up message
                   └── NO  → silently cancel
```

**Implemented follow-up tasks**:

| Task | File | Sleep | Nonce Key |
|------|------|-------|-----------|
| Catalog follow-up | `ai_followups.py` | 5-10 min (random) | `madina:catalog_followup:{uid}` |
| AI reminder #1 | `ai_followups.py` | 10 min | `madina:followup_nonce:{uid}` |
| AI reminder #2 | `ai_followups.py` | 60 min (50 min after #1) | `madina:followup_nonce:{uid}` |
| Photo funnel follow-up | `ai_followups.py` | 7 min | FSM state check |

**Cancellation**: New user interaction calls `_refresh_ai_followup_nonce()`, which generates a new random nonce. The sleeping task wakes up, compares its captured nonce to the stored one, sees they differ, and exits silently.

### 4.2 Persistent scheduled jobs (APScheduler)

Used for long-lived, cross-restart follow-ups managed by the scheduler process.

| Job ID | Interval | File | Purpose |
|--------|----------|------|---------|
| `check_due_followups` | 60 seconds | `followup_jobs.py` | Brain-driven follow-ups for leads with `next_follow_up_at <= now()` |
| `check_inactive_leads` | 15 minutes | `followup_jobs.py` | Tiered inactivity reminders (24h, 72h, 7d) |
| `check_hot_lead_inactivity` | 10 minutes | `followup_jobs.py` | AI-powered suggestions for HOT leads inactive 2h+ |

### 4.3 APScheduler vs Celery decision matrix

| Criteria | APScheduler | Celery |
|---------|-------------|--------|
| **Use when** | Periodic polling, DB scans, admin alerts | One-shot background tasks, broadcasts |
| **Persistence** | Job definitions in code, re-registered on restart | Tasks queued in Redis (broker), survive restarts |
| **Concurrency** | `max_instances=1` per job | Worker pool, multiple tasks in parallel |
| **Error recovery** | `misfire_grace_time=60s`, coalesce missed runs | Automatic retry with configurable backoff |
| **Current usage** | Follow-ups, analytics, cache warmup, conversation intelligence | Broadcasts, package follow-ups |

### 4.4 Duplicate prevention

| Level | Mechanism | Key/Column |
|-------|-----------|-----------|
| In-process follow-ups | Random nonce comparison | `madina:followup_nonce:{uid}` |
| Catalog follow-ups | Redis NX (set-if-not-exists) | `madina:catalog_followup:{uid}` |
| Due follow-ups | DB `next_follow_up_at` + `follow_up_count` | `leads.next_follow_up_at` |
| Inactive lead reminders | `follow_up_count` threshold check | `leads.follow_up_count` |
| HOT lead alerts | Redis NX with 6h TTL | `hot_alert:2h:{lead_id}` |
| HOT objection alerts | Redis NX with 2h TTL | `hot_obj_alert:{user_id}` |
| Sales closer CTA | Redis NX with 10-min TTL | `closer:last:{user_id}` |
| Lead card dedup | Redis NX with 5-min TTL | `lead:{id}:card_sent` |

---

## 5. Scheduler Jobs (Complete Registry)

All jobs registered in `apps/scheduler/main.py`:

### 5.1 Follow-up jobs (`followup_jobs.py`)

| Job | Interval | Description |
|-----|----------|-------------|
| `check_due_followups` | 60s | Process leads with overdue `next_follow_up_at` |
| `check_inactive_leads` | 15 min | Tiered reminders: 24h, 72h, 7d inactivity |
| `check_hot_lead_inactivity` | 10 min | AI-powered admin alerts for silent HOT leads |

### 5.2 Analytics jobs (`analytics_jobs.py`)

| Job | Interval | Description |
|-----|----------|-------------|
| Analytics aggregation | Configurable | Aggregate daily metrics |

### 5.3 Cache jobs (`cache_jobs.py`)

| Job | Interval | Description |
|-----|----------|-------------|
| Cache warmup | Configurable | Pre-fill Redis with group configs, pricing |

### 5.4 Conversation intelligence (`conversation_intelligence_jobs.py`)

| Job | Interval | Description |
|-----|----------|-------------|
| Conversation analysis | Configurable | Detect cooling leads, manager delays |

### 5.5 Sales autopilot (`sales_autopilot_jobs.py`)

| Job | Interval | Description |
|-----|----------|-------------|
| Autopilot scan | Configurable | Opportunity/risk/closing suggestions |

### 5.6 Closing jobs (`closing_jobs.py`)

| Job | Interval | Description |
|-----|----------|-------------|
| Closing readiness check | Configurable | Detect close-ready leads |

### 5.7 Auto-sales jobs (`auto_sales_jobs.py`)

| Job | Interval | Description |
|-----|----------|-------------|
| Auto-reply monitoring | Configurable | Track consecutive auto-replies, escalate |

### 5.8 Outcome resolver (`outcome_resolver_jobs.py`)

| Job | Interval | Description |
|-----|----------|-------------|
| Tactic outcome resolution | Configurable | Resolve pending tactic outcomes for learning |

### 5.9 Broadcast jobs (`broadcast_jobs.py`)

| Job | Interval | Description |
|-----|----------|-------------|
| Scheduled broadcast check | Configurable | Execute broadcasts at scheduled times |

---

## 6. Event Flow: Complete User Journey

```
/start
  │
  ├── STARTED_BOT → show greeting (memory-personalized) + main menu
  │
  ├── [📚 Katalog] ─→ OPENED_CATALOG
  │       │
  │       ├── [Design tapped] → VIEWED_CATALOG_ITEM (score +5)
  │       │       └── [5-10 min silence] → FOLLOWUP_SENT (catalog follow-up)
  │       │
  │       └── [text message] → AI_QUESTION_ASKED
  │
  ├── [💰 Narx] ─→ USED_PRICE_CALCULATOR
  │       │
  │       ├── [area entered] → parse_area() + design selection
  │       │       │
  │       │       └── [design selected] → PRICE_CALCULATED (score +10)
  │       │               │
  │       │               ├── [🛒 Buyurtma] → CLICKED_ORDER
  │       │               ├── [📞 Operator] → OPERATOR_REQUESTED
  │       │               └── [10 min silence] → FOLLOWUP_SENT (price follow-up)
  │       │
  │       └── [district detected] → score +10
  │
  ├── [🛒 Buyurtma] ─→ ORDER_FORM_STARTED
  │       │
  │       ├── [step completed] → ORDER_FORM_STEP_COMPLETED
  │       │       │
  │       │       ├── [phone shared] → PHONE_SHARED (score +40)
  │       │       │       │
  │       │       │       └── [district shared] → Lead created → ADMIN_NOTIFIED
  │       │       │
  │       │       └── [all steps done] → DEAL_CLOSED (order confirmed)
  │       │
  │       └── [form abandoned] → ORDER_FORM_ABANDONED
  │               └── [10 min silence] → FOLLOWUP_SENT (abandoned form)
  │
  ├── [📞 Operator] ─→ OPERATOR_REQUESTED → ADMIN_NOTIFIED (escalation card)
  │
  ├── [🤖 AI chat] ─→ AI_QUESTION_ASKED
  │       │
  │       ├── [objection detected] → OBJECTION_DETECTED
  │       │       ├── Negotiation engine reply
  │       │       ├── Score adjustment (+5 or -5/-10)
  │       │       └── [HOT lead + first objection] → ADMIN_NOTIFIED (real-time alert)
  │       │
  │       ├── [area/district/design extracted] → Memory updated, score adjusted
  │       │
  │       ├── [phone detected in text] → PHONE_SHARED → ADMIN_NOTIFIED
  │       │
  │       └── [10 min silence] → FOLLOWUP_SENT (AI reminder #1)
  │               └── [50 more min silence] → FOLLOWUP_SENT (AI reminder #2)
  │
  └── [📦 Paketlar] ─→ Package browsed
          │
          ├── [package ordered] → score +10, lead created
          └── [15 min check] → Celery package follow-up task
```

---

## 7. Inactivity Escalation Timeline

```
T=0        Last user interaction
│
T+10 min   AI Reminder #1 (in-process asyncio timer)
│          "Yordam kerakmi? Xona maydonini yozing..."
│
T+60 min   AI Reminder #2 (in-process asyncio timer)
│          "Bepul o'lchov xizmatimiz ham bor..."
│
T+2 hr     HOT lead inactivity alert to admin (scheduler, biz hours only)
│          AI-powered suggestion: "Bepul o'lchov uchun qo'ng'iroq qiling"
│
T+6 hr     Off-hours HOT lead alert (scheduler, extended threshold)
│
T+24 hr    First admin reminder (scheduler)
│          "1-eslatma (24 soat) — Lid #123 — Bobur"
│
T+72 hr    Second admin reminder (scheduler)
│          "2-eslatma (72 soat) — Lid #123 — Bobur"
│
T+168 hr   Auto-mark LOST (scheduler, runs anytime)
│          "LOST candidate — Lid #123 — Sabab: no_response"
│
T+30 days  Redis memory expires (TTL auto-cleanup)
│
T+90 days  PostgreSQL memory purge (scheduled cleanup)
```

---

## 8. Database Tables

### 8.1 customer_journey_events

Stores every significant user journey milestone for analytics and replay.

```sql
CREATE TABLE customer_journey_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         BIGINT NOT NULL REFERENCES users(id),
    event_type      VARCHAR(50) NOT NULL,
    metadata        JSONB DEFAULT '{}',
    source_handler  VARCHAR(100),
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Query patterns: user timeline, funnel analysis, event counts
CREATE INDEX ix_journey_user_id    ON customer_journey_events (user_id);
CREATE INDEX ix_journey_event_type ON customer_journey_events (event_type);
CREATE INDEX ix_journey_created_at ON customer_journey_events (created_at);
```

**Column details**:

| Column | Type | Nullable | Description |
|--------|------|----------|-------------|
| `id` | UUID | NO | Auto-generated primary key |
| `user_id` | BIGINT | NO | FK to `users.id` |
| `event_type` | VARCHAR(50) | NO | From `JourneyEventType` enum |
| `metadata` | JSONB | YES | Event-specific data: `{"area_m2": 25, "design": "Gulli"}` |
| `source_handler` | VARCHAR(100) | YES | File that emitted: `"ai_support.py"` |
| `created_at` | TIMESTAMPTZ | NO | UTC event timestamp |

**Metadata examples by event type**:

```json
// PRICE_CALCULATED
{"area_m2": 25.0, "design": "Gulli", "price_uzs": 3000000}

// OBJECTION_DETECTED
{"objection_type": "expensive", "severity": "high", "text_snippet": "juda qimmat"}

// PHONE_SHARED
{"source": "contact_share"}  // never store actual phone here

// ORDER_FORM_STEP_COMPLETED
{"step": 3, "step_name": "district", "value": "Qarshi"}
```

### 8.2 customer_agent_state

Current agent state per user. Single row per user, updated on every event.

```sql
CREATE TABLE customer_agent_state (
    user_id         BIGINT PRIMARY KEY REFERENCES users(id),
    journey_state   VARCHAR(30) NOT NULL DEFAULT 'idle',
    last_event_type VARCHAR(50),
    last_event_at   TIMESTAMPTZ,
    followup_count  INTEGER DEFAULT 0,
    next_followup_at TIMESTAMPTZ,
    followup_type   VARCHAR(50),
    agent_memory    JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
```

**Column details**:

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `user_id` | BIGINT | NO | - | PK + FK to `users.id` |
| `journey_state` | VARCHAR(30) | NO | `'idle'` | Current journey phase: idle, browsing, calculating, ordering, contacted, converted, lost |
| `last_event_type` | VARCHAR(50) | YES | NULL | Most recent `JourneyEventType` |
| `last_event_at` | TIMESTAMPTZ | YES | NULL | When last event occurred |
| `followup_count` | INTEGER | NO | 0 | Total follow-ups sent |
| `next_followup_at` | TIMESTAMPTZ | YES | NULL | When next follow-up is due |
| `followup_type` | VARCHAR(50) | YES | NULL | Type of next follow-up: catalog, price, abandoned_form, soft_reminder, final_offer |
| `agent_memory` | JSONB | NO | `'{}'` | Denormalized snapshot of AgentMemory for fast access |
| `created_at` | TIMESTAMPTZ | NO | `now()` | Row creation time |
| `updated_at` | TIMESTAMPTZ | NO | `now()` | Last modification time |

**Relationships**:
- `user_id` references `users(id)` — one state per user
- Read by scheduler jobs to find users due for follow-up
- Updated by event handlers on every significant action

### 8.3 scheduled_followups

Tracks individual follow-up messages: scheduled, executed, or cancelled.

```sql
CREATE TABLE scheduled_followups (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           BIGINT NOT NULL REFERENCES users(id),
    followup_type     VARCHAR(50) NOT NULL,
    trigger_event_id  UUID REFERENCES customer_journey_events(id),
    scheduled_at      TIMESTAMPTZ NOT NULL,
    executed_at       TIMESTAMPTZ,
    cancelled_at      TIMESTAMPTZ,
    status            VARCHAR(20) DEFAULT 'pending',
    message_template  VARCHAR(100),
    metadata          JSONB DEFAULT '{}',
    created_at        TIMESTAMPTZ DEFAULT now()
);

-- Primary query: find pending follow-ups due now
CREATE INDEX ix_followup_scheduled ON scheduled_followups (scheduled_at)
    WHERE status = 'pending';

-- Secondary query: user's follow-up history
CREATE INDEX ix_followup_user ON scheduled_followups (user_id);
```

**Column details**:

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | auto | Primary key |
| `user_id` | BIGINT | NO | - | FK to `users.id` |
| `followup_type` | VARCHAR(50) | NO | - | catalog_followup, price_followup, abandoned_form, soft_24h, final_72h, hot_inactivity |
| `trigger_event_id` | UUID | YES | NULL | FK to the event that caused this follow-up |
| `scheduled_at` | TIMESTAMPTZ | NO | - | When follow-up should fire |
| `executed_at` | TIMESTAMPTZ | YES | NULL | When it was actually sent |
| `cancelled_at` | TIMESTAMPTZ | YES | NULL | When it was cancelled (user acted first) |
| `status` | VARCHAR(20) | NO | `'pending'` | pending, executed, cancelled, failed |
| `message_template` | VARCHAR(100) | YES | NULL | Reference to prompt template name |
| `metadata` | JSONB | NO | `'{}'` | Context for template rendering: `{"area": 25, "design": "Gulli"}` |
| `created_at` | TIMESTAMPTZ | NO | `now()` | Row creation time |

**Status lifecycle**:

```
pending → executed    (follow-up sent successfully)
pending → cancelled   (user interacted before timer)
pending → failed      (TelegramForbiddenError, bot blocked)
```

**Relationships**:
- `user_id` references `users.id` — multiple follow-ups per user
- `trigger_event_id` references `customer_journey_events.id` — traces cause
- Partial index on `scheduled_at WHERE status = 'pending'` — efficient scheduler polling

---

## 9. Existing Tables Used by Event System

These tables already exist and are used by the current follow-up/event infrastructure:

| Table | Purpose in Event System |
|-------|------------------------|
| `leads` | `next_follow_up_at`, `follow_up_count`, `lead_temperature`, `closing_confidence`, `score` |
| `pipeline_stages` | Stage transitions logged as events |
| `lead_actions` | Action log: `lead_created`, `stage_changed`, `hot_alert_sent` |
| `ai_conversations` | Rolling 12-message window + summary per user |
| `ai_user_memory` | Persistent profile JSONB per user |
| `ai_tactic_outcome` | Outcome-based learning: which tactic led to conversion |
| `audit_log` | Admin actions on leads (stage moves, status changes) |
| `blocked_chats` | Blocked users excluded from follow-ups and broadcasts |

---

## 10. Business Hours Awareness

Follow-up timing respects Uzbekistan business hours via `shared/utils/business_hours.py`:

| Context | Business Hours | Off Hours |
|---------|---------------|-----------|
| User-facing follow-ups | Sent normally | Deferred to next business hour |
| Admin alerts (normal) | Sent normally | Suppressed |
| LOST marking | Runs anytime | Runs anytime |
| HOT inactivity threshold | 2 hours | 6 hours |

Timezone: `Asia/Tashkent` (UTC+5), configured in `apps/scheduler/main.py`.

---

## 11. Error Handling

### Scheduler error listener

All APScheduler job errors are logged to `system_errors` table:

```python
def _on_job_error(event):
    log.exception("scheduler_job_error", job_id=job_id)
    asyncio.ensure_future(log_system_error("scheduler", exc, message=f"job={job_id}: {exc}"))
```

### Follow-up error handling

| Error | Behavior |
|-------|----------|
| Redis connection failure | Follow-up silently skipped (non-fatal) |
| Telegram API error | Logged, follow-up marked as failed |
| `TelegramForbiddenError` | User blocked bot — add to `blocked_chats` |
| `TelegramRetryAfter` | Sleep for retry_after seconds, then retry |
| Database error | Logged, state rollback |

### Job configuration

```python
scheduler = AsyncIOScheduler(
    timezone="Asia/Tashkent",
    job_defaults={
        "coalesce": True,          # collapse missed runs into one execution
        "max_instances": 1,        # never run same job twice in parallel
        "misfire_grace_time": 60,  # tolerate up to 60s late start
    },
)
```
