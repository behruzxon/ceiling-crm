# CRM Domain

This document describes the current business domain model, entity lifecycles, and workflows.

---

## Lead Lifecycle

A lead represents a potential customer interested in stretch ceiling installation.

### Entry Points

Leads enter the system through 4 paths:

1. **Direct lead capture** (`lead_capture.py`) — user fills name, phone, district via FSM
2. **Measurement request** (`measurement_lead.py`) — "Bepul o'lchov" button, captures room dimensions + district + phone
3. **Order flow** (`order.py`) — full order FSM: design picker -> area -> district -> phone -> summary
4. **Package selection** (`packages.py`) — user selects a package (standard/premium/VIP), creates a lead

### Lead Model Fields

```
id, user_id, category, source_group_id, source
name, phone, district
room_length, room_width, room_area
addons (JSON), notes
utm_source, utm_campaign
assigned_manager_id
package_type, lead_status, last_action, score
lead_temperature, closing_confidence
next_follow_up_at, follow_up_count
lost_reason
created_at, updated_at
```

### Lead Status Values

| Status | Meaning |
|--------|---------|
| `hot` | High intent, ready to buy |
| `warm` | Interested, needs nurturing |
| `cold` | Low intent, may not convert |

Temperature is set by AI scoring (Redis score 0-100: hot >= 60, warm 30-59, cold < 30) and persisted to DB via `lead_temperature` column.

---

## Pipeline Stages

Pipeline is event-sourced via the `pipeline_stages` table (immutable, append-only). The "current stage" is always the latest entry for a given lead_id.

### Stage Progression

```
NEW -> PACKAGE_SELECTED -> CONTACTED -> MEASUREMENT -> QUOTE -> DEAL -> INSTALLATION -> COMPLETED
  \                                                                                      /
   \-----> LOST (from any stage) <-----------------------------------------------------/
```

### Allowed Transitions

Forward transitions follow the linear chain above. Backward transitions are allowed for admin overrides (via kanban move). `LOST` can be reached from any stage.

### Kanban View (5 Columns)

The admin kanban view maps 9 stages into 5 visual columns:

| Kanban Column | Pipeline Stages |
|---------------|----------------|
| NEW | NEW, PACKAGE_SELECTED |
| HOT | CONTACTED |
| MEASUREMENT | MEASUREMENT, QUOTE |
| WON | DEAL, INSTALLATION, COMPLETED |
| LOST | LOST |

### Pipeline Events

Each transition creates a `PipelineStageModel` record:
```
id, lead_id, stage, changed_by, note, created_at
```

The `lead_actions` table separately logs operator actions for performance tracking.

---

## Appointment Logic

### Types
- `MEASUREMENT` — free measurement visit (typically triggers after lead qualifies)
- `INSTALLATION` — ceiling installation after deal confirmed

### Status Flow
```
SCHEDULED -> CONFIRMED -> DONE
    |            |
    v            v
RESCHEDULED  CANCELLED
```

### Fields
```
id, lead_id, type, installer_id, brigade_id
scheduled_at, duration_minutes
district, address
status, notes, created_by, created_at
```

Appointments are linked to leads via `lead_id` (CASCADE delete). An installer can be assigned and queried by date range for scheduling.

---

## Payment Logic

### Status Flow
```
PENDING -> PAID
   |         |
   v         v
REJECTED  REFUNDED
   |
   v
CANCELED
```

### Methods
- `cash` — physical cash payment
- `card` — card payment
- `transfer` — bank transfer
- `manual` — bot-submitted payment awaiting admin approval

### Fields
```
id, lead_id, amount (BigInteger UZS), method, status
paid_at, receipt_url, notes, proof_file_id
created_by, created_at, updated_at
```

Multiple payments per lead are allowed. `paid_at` is set atomically when status transitions to `PAID`. The `proof_file_id` stores a Telegram file_id for payment proof photos.

### Constraints
- `amount > 0` (CHECK constraint)
- `lead_id` CASCADE delete

---

## Warranty Logic

### Fields
```
id, lead_id, issued_at (Date), expires_at (Date)
warranty_card_no, notes
created_by, created_at
```

### Rules
- One warranty per lead (UNIQUE constraint on `lead_id`)
- Linked via CASCADE delete
- `expires_at` indexed for expiration queries
- Currently 15-year warranty period (business rule, not enforced in code)

---

## Admin / Operator Workflow

### Roles

| Role | Capabilities |
|------|-------------|
| SUPERADMIN | All admin commands + promote to ADMIN |
| ADMIN | Dashboard, reports, broadcasts, scheduler, media, promote to MANAGER/INSTALLER |
| MANAGER | Lead management, pipeline transitions, appointments |
| INSTALLER | Assigned appointments, installation status updates |
| CLIENT | Catalog, pricing calculator, lead submission |

### Admin Commands

| Command | Purpose |
|---------|---------|
| `/dashboard` | CRM summary stats |
| `/leads [days]` | Bulk lead listing |
| `/pipeline [days]` | Pipeline/kanban view |
| `/radar` | Top 5 leads by priority |
| `/analytics [days]` | Sales analytics + recommendations |
| `/sales_report` | Revenue + conversion metrics |
| `/lead_advice {id}` | AI-powered lead recommendation |
| `/stats [days]` | Time-period stats |
| `/operator_stats` | Operator performance |
| `/reports` | Multi-period reports |
| `/broadcasts` / "Rassilka" button | Broadcast composer |
| `/scheduler` | Job scheduling |
| `/media` | Media upload manager |
| `/autopilot` | AI sales autopilot |
| `/close_advice` | AI closer readiness |
| `/system_status` | DB/Redis/bot health |

### Notification Flow

When a lead is captured or scores change:
1. `LeadNotificationService.notify_new_lead(lead)` sends card to admin group + admin DM
2. Card includes inline keyboard with status buttons: hot, warm, cold, contacted, lost
3. `LeadNotificationService.notify_hot_lead(lead_id)` sends alert for high-score leads (deduped)
4. AI intelligence card (`notify_ai_lead_collected`) adds: deal probability, buyer type, revenue, radar bucket, risk flags, next action

### Operator Assist (On-Demand)

Admin can press "Operator yordam" button on any lead card:
1. Shows 4 suggestion buttons: soft reply, close reply, budget reply, call script
2. Each loads lead data, runs intelligence stack, generates copyable Uzbek reply

---

## Analytics Workflow

### `/analytics [days]` Report Sections

1. **Total summary** — leads created, won, lost, conversion rate
2. **Source performance** — leads by source (group, deeplink, ads, etc.)
3. **Buyer type conversion** — conversion rate per buyer type
4. **Objection breakdown** — frequency of each objection type
5. **Funnel dropoff** — largest relative drop between consecutive stages
6. **Follow-up performance** — coverage and effectiveness
7. **Score distribution** — hot/warm/cold breakdown
8. **Revenue summary** — predicted revenue from active leads
9. **Recommendations** — up to 5 deterministic suggestions

### Daily Automated Reports

Scheduled via APScheduler:
- 20:00 — Daily admin summary (sent to admin DM)
- 21:00 — AI daily report (conversation metrics)
- 23:59 — Daily stats aggregation

---

## Missing CRM Entities for Future Platform

These entities do not exist yet but will be needed for a full web CRM/ERP:

| Entity | Purpose | Priority |
|--------|---------|----------|
| **Organization / Tenant** | Multi-tenancy, team management | Critical for SaaS |
| **Contact** | Separate from lead — a person can have multiple leads | High |
| **Company** | B2B entity (e.g., a construction firm ordering for multiple sites) | Medium |
| **Deal / Opportunity** | Currently leads serve as deals; need separation | High |
| **Invoice** | Formal document with number sequencing, line items, tax | High |
| **Product / Service catalog** | DB-backed catalog instead of hardcoded constants | Medium |
| **Custom fields** | User-defined lead/contact attributes | Medium |
| **Activity log** | Unified timeline (calls, emails, notes, status changes) | High |
| **Team / Assignment** | Team structure, workload balancing | Medium |
| **Integration webhook** | Outbound event delivery to external systems | Medium |
| **Notification preference** | Per-user notification settings | Low |
| **File / Document** | Centralized file management beyond Telegram file_ids | Medium |
| **Calendar event** | Standalone events not tied to appointments | Low |
| **Email template** | For future email channel | Low |
