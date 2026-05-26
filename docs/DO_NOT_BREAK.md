# Do Not Break

This document lists every production Telegram bot flow and system that must continue working identically during and after any code changes. Use this as a checklist before merging any PR.

---

## Critical Bot Flows

### 1. Lead Capture

**What:** Users submit their name, phone, and district via FSM conversation.

**Entry points:**
- `apps/bot/handlers/private/lead_capture.py` — direct FSM flow
- `apps/bot/handlers/private/measurement_lead.py` — free measurement FSM
- `apps/bot/handlers/private/order.py` — order FSM
- `apps/bot/handlers/private/packages.py` — package selection

**What must work:**
- FSM state transitions (name -> phone -> district -> confirmation)
- Phone number extraction and validation
- Lead creation via `LeadService.create_lead()`
- Pipeline stage insertion (`NEW` or `PACKAGE_SELECTED`)
- Lead action logging
- Admin notification after lead creation
- AI scoring update after lead creation

**Test:** Submit a lead through each entry point. Verify: lead appears in DB, pipeline_stages has a NEW/PACKAGE_SELECTED entry, admin receives notification.

### 2. Pricing Calculator

**What:** Interactive FSM that calculates ceiling price from room dimensions and design.

**Handler:** `apps/bot/handlers/private/pricing.py`
**States:** `PricingStates` — room type -> width -> length -> design -> summary

**What must work:**
- Dimension input parsing (handles "5x4", "5 4", "5.5", etc.)
- Design selection keyboard
- Price calculation via `PricingService.calculate_quote()`
- Quote summary message with breakdown
- Addon pricing (LED, cornice, spots, chandelier, etc.)
- District modifier application

**Test:** Enter dimensions "5x4", select a design, verify price matches formula: `area * price_per_sqm * modifier - discount + addons`.

### 3. Catalog Flow

**What:** Users browse ceiling designs by category.

**Handler:** `apps/bot/handlers/private/catalog.py`
**Trigger:** "Katalog" button or `/catalog` command

**What must work:**
- Category selection keyboard
- Design photo/video display
- Inline navigation (prev/next)
- Deep link: `/start katalog`

### 4. AI Sales Assistant ("Madina")

**What:** GPT-4o-powered conversational sales agent in DMs.

**Handler:** `apps/bot/handlers/private/ai_support.py` (catch-all for free text)

**What must work:**
- Intent detection (dimensions, catalog, measurement, greeting, general)
- OpenAI API call with token budgeting
- Prompt injection firewall (pre + post)
- Conversation history persistence (rolling 12 messages + summary)
- Redis memory persistence (profile, 30-day TTL)
- Lead scoring (0-100 in Redis)
- Objection detection and handling
- Phone number extraction
- Follow-up scheduling
- Admin intelligence card notification
- Rate limiting (100 messages/day/user)

**Test:** Send several messages. Verify: responses are relevant Uzbek text, score changes in Redis, admin card arrives with intelligence data.

### 5. Admin Notifications

**What:** Real-time alerts sent to admin group and admin DM.

**Service:** `core/services/lead_notification_service.py`

**What must work:**
- New lead card with inline status keyboard
- Hot lead alerts (deduped via `last_action`)
- AI intelligence card (deal probability, buyer type, revenue, radar, risk flags)
- Operator assist button
- Status update callbacks (`lead:{id}:status:{status}`)

**Test:** Create a lead. Verify: admin group receives card, card has 5 status buttons + operator assist button.

### 6. Broadcast System

**What:** Admin sends messages to segments of users.

**Handler:** `apps/bot/handlers/admin/broadcasts.py`
**Worker:** `infrastructure/queue/tasks/broadcast_tasks.py`

**What must work:**
- Broadcast FSM (segment -> stage -> payload -> text/media -> confirm)
- Segment types: ALL_PRIVATE, LEAD_STAGE, ADMIN_GROUPS
- Payload types: TEXT, PHOTO, VIDEO, DOCUMENT
- Celery task execution with retry on TelegramRetryAfter
- Blocked chat auto-cleanup
- Admin DM report with sent/failed/blocked counts
- Flush counters every 50 sends

**Test:** Create a broadcast to ALL_PRIVATE with text. Verify: messages sent, report received, blocked chats updated.

### 7. Pipeline Transitions

**What:** Leads move through 9 pipeline stages.

**Service:** `CRMService.advance_stage()` (validates transitions), `PipelineService.move_stage()` (admin override)

**What must work:**
- Allowed transition validation
- Event-sourced stage insertion (append-only `pipeline_stages`)
- Kanban view with live counts
- Lost reason collection (FSM + presets)
- Admin callbacks: `kanban:stage:*`, `kanban:move:*`, `kanban:lead:*`
- Audit log insertion on move

**Test:** Move a lead from NEW to CONTACTED. Verify: pipeline_stages has new entry, audit_log has entry, kanban counts updated.

### 8. Payment Tracking

**What:** Payments linked to leads with status transitions.

**Handler:** `apps/bot/handlers/private/payment.py`
**Service:** `PaymentService`

**What must work:**
- Payment creation with amount validation (> 0)
- Status transitions: PENDING -> PAID, PENDING -> REJECTED, etc.
- `paid_at` set atomically on PAID transition
- Proof photo upload (`proof_file_id`)
- Admin notification on new payment

### 9. Scheduler / Follow-ups

**What:** APScheduler runs background jobs every 60 seconds.

**Entrypoint:** `apps/scheduler/main.py`
**Key jobs:** `followup_jobs.py` (due follow-ups, inactive leads, hot lead alerts)

**What must work:**
- Due follow-up query: `leads.next_follow_up_at <= now()`
- Reminder card sent to admin
- `follow_up_count` incremented
- Rescheduling via follow-up brain
- Max 5 follow-ups per lead cap
- Inactive lead detection (24h, 72h, 7d)
- Hot lead inactivity alert (2h business hours, 6h off-hours)
- Daily stats aggregation (23:59)
- Daily admin summary (20:00)

### 10. Order Flow (Full FSM)

**What:** Complete order submission with 7-step FSM, separate from lead capture.

**Handler:** `apps/bot/handlers/private/order.py`
**Trigger:** "Zakaz berish" button, `/order`, `/start zakaz`, `cta:order` callback

**What must work:**
- 7-step FSM: name -> phone -> district -> category -> area -> location -> confirmation
- Lead + pipeline stage creation on completion
- Admin notification on new order
- Deep link: `/start zakaz`

### 11. Package Browser

**What:** Users browse and order from predefined ceiling packages (standard/premium/VIP).

**Handler:** `apps/bot/handlers/private/packages.py`
**Trigger:** "Tayyor paketlar" button, `/start paketlar`
**Callbacks:** `pkg:detail:*`, `pkg:order:*`, `pkg:calc:*` (in `package_callbacks.py`)

**What must work:**
- Inline keyboard package listing
- Package detail view with price
- Package order (creates lead with `PACKAGE_SELECTED` stage)
- Admin notification on package order
- Celery follow-up task (15-min check)

### 12. My Orders / Order History

**What:** Users check their orders, payment history, and warranty info.

**Handler:** `apps/bot/handlers/private/my_orders.py`
**Trigger:** "Buyurtmalarim" button

**What must work:**
- Last 5 orders display
- Latest pipeline stage + status hints
- Last 10 payments history
- Warranty info for completed orders

### 13. Promotions / Discounts

**What:** Displays current discount tiers and CTAs.

**Handler:** `apps/bot/handlers/private/promotions.py`
**Trigger:** "Chegirmalar" button

**What must work:**
- Discount tier display
- CTA buttons (pricing, order, operator)

### 14. About Section

**What:** Company info with action buttons.

**Handler:** `apps/bot/handlers/private/about.py`
**Trigger:** "Biz haqimizda" button

**What must work:**
- Company description text
- Inline keyboard (Katalog, Narx, Operator, Zakaz)
- `open_catalog` callback

### 15. Group Welcome + Moderation

**What:** Welcome messages for new group members and anti-spam protection.

**Handlers:**
- `apps/bot/handlers/group/welcome.py` — welcome message with auto-delete + group menu
- `apps/bot/handlers/group/link_guard.py` — blocks unauthorized links
- `apps/bot/handlers/group/flood_guard.py` — throttles rapid message spam
- `apps/bot/handlers/group/admin.py` — `/admin` command in groups with `gs:*` settings callbacks

**What must work:**
- Welcome message sent on member join
- Auto-delete of welcome message after configured delay
- Group menu keyboard (9 URL buttons) attached to welcome
- Link detection and deletion (non-admin)
- Flood detection and warning (5 msgs / 10s threshold)
- Group settings panel via `/admin` (welcome toggle, captcha, link blocking, flood guard)

### 16. CTA Callback System

**What:** Call-to-action buttons used across notification cards and reminder messages.

**Handler:** `apps/bot/handlers/callbacks/cta_callbacks.py`
**Callbacks:** `cta:discount`, `cta:order`, `cta:pricing`, `cta:operator`, `cta:catalog`

**What must work:**
- Each callback routes to the correct private handler flow
- Used by: inactive reminder tasks, AI follow-ups, admin notification cards

### 17. Docker Deployment

**What:** The entire system runs in Docker Compose.

**Files:** `docker-compose.yml` (dev), `docker-compose.prod.yml` (production)

**What must work:**
- `docker compose up -d` starts all services
- Alembic migrations run on bot startup (entrypoint.sh)
- Health checks for postgres and redis
- Bot, worker, scheduler all connect to same DB and Redis
- Media volume persistence
- Prometheus metrics collection
- Grafana dashboard availability

---

## Middleware Execution Order

The following order must be preserved in `build_dispatcher()`:

```
1. AuthMiddleware        (outermost — opens session, injects db_user)
2. SecurityMiddleware    (burst detection, sanitization)
3. LocaleMiddleware      (resolves language)
4. GroupContextMiddleware (resolves group category)
5. RateLimitMiddleware    (per-user rate limiting)
6. AuditMiddleware       (innermost — audit logging)
```

Changing this order will break handler data injection. For example, `RateLimitMiddleware` depends on `db_user` from `AuthMiddleware`.

---

## Router Registration Order

Router order in `build_dispatcher()` determines handler priority. The current order must be preserved:

```
1. admin_router          (admin commands first)
2. callbacks_router      (inline keyboard callbacks)
3. group_router          (group events)
4. private_router        (DM flows)
5. moderation_router     (link/flood guard)
6. group_messages_router (silent catch-all, always last)
```

Within `callbacks_router`, the sub-router order matters:
```
lead_callbacks > kanban_callbacks > lead_status > cta_callbacks >
sales_closer_callbacks > operator_callbacks > pipeline_callbacks >
payment_callbacks > package_callbacks
```

Within `private_router`, ai_support_router must be LAST (it's the catch-all).

---

## Database Constraints That Must Not Be Violated

- All enum columns use `values_callable=lambda x: [e.value for e in x]`
- `users.id > 0` (CHECK constraint — no bot/negative IDs)
- `payments.amount > 0` (CHECK constraint)
- `leads.closing_confidence` between 0.0 and 1.0 (CHECK constraint)
- `warranties.lead_id` is UNIQUE (one per lead)
- `pipeline_stages` is append-only (never update or delete)
- `audit_logs` is append-only
- `system_errors` is append-only

---

## Redis Key Conventions

All cache keys follow the pattern defined in `infrastructure/cache/keys.py`. Never use raw key strings in application code. Key TTLs are defined in `CacheTTL` constants. Changing a key format or TTL without updating all consumers will cause silent data loss.

Critical keys:
- `ai:score:{user_id}` — lead score (30-day TTL)
- `ai:memory:{user_id}` — AI memory (30-day TTL)
- `closer:last:{user_id}` — closing cooldown (10-min TTL)
- `agent:cooldown:{trigger}:{user_id}:{lead_id}` — agent dedup (60s TTL)

---

## Verification Checklist

Before any deployment, verify:

- [ ] `pytest tests/unit/ -q` passes
- [ ] `ruff check .` passes
- [ ] `alembic upgrade head` runs without errors
- [ ] `docker compose up -d` starts all services
- [ ] Bot responds to `/start` command
- [ ] Lead capture FSM completes successfully
- [ ] AI responds to free-text message
- [ ] Admin receives notification for new lead
- [ ] `/pipeline` shows kanban with correct counts
- [ ] Broadcast sends and reports back
- [ ] Order FSM completes and creates lead
- [ ] Package browser loads and inline buttons work
- [ ] "Buyurtmalarim" shows order history
- [ ] Pricing calculator produces correct quote
- [ ] Catalog displays designs by category
- [ ] Group welcome message appears for new members
- [ ] CTA callbacks (`cta:order`, `cta:pricing`, etc.) route correctly
