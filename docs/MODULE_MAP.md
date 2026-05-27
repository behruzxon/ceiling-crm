# Module Map

This document lists every module group, its purpose, and whether it is safe to reuse from a future REST API or is Telegram-specific.

## Legend

- **Reusable** — can be called directly from FastAPI routes without changes
- **Needs adapter** — usable from API but requires a thin wrapper (e.g., different input/output format)
- **Telegram-only** — depends on aiogram types, Telegram API, or bot-specific patterns

---

## apps/bot/ (Telegram-only)

All modules under `apps/bot/` are Telegram-specific. They depend on aiogram `Message`, `CallbackQuery`, `FSMContext`, inline keyboards, etc. None should be imported from the API layer.

### apps/bot/handlers/admin/

| Module | Purpose | Reuse |
|--------|---------|-------|
| `dashboard.py` | `/dashboard` stats summary | Telegram-only — renders HTML text |
| `leads.py` | `/leads [days]` bulk listing | Telegram-only |
| `pipeline.py` | `/pipeline`, `/stage`, `/lead` commands | Telegram-only |
| `radar.py` | `/radar` deal priority ranking | Telegram-only |
| `analytics.py` | `/analytics [days]` sales analytics | Telegram-only |
| `sales_report.py` | `/sales_report` revenue metrics | Telegram-only |
| `lead_advice.py` | `/lead_advice {id}` AI recommendation | Telegram-only |
| `broadcasts.py` | Broadcast composer FSM | Telegram-only |
| `scheduler.py` | `/scheduler` job management | Telegram-only |
| `operator_stats.py` | `/operator_stats` performance | Telegram-only |
| `reports.py` | `/reports` multi-period analytics | Telegram-only |
| `media.py` | `/media` upload manager | Telegram-only |
| `autopilot.py` | `/autopilot` AI suggestions | Telegram-only |
| `close_advice.py` | `/close_advice` closer readiness | Telegram-only |
| `stats.py` | `/stats [days]` time-period stats | Telegram-only |
| `system_status.py` | `/system_status` health diagnostics | Telegram-only |
| `lead_status.py` | `lead:{id}:status:{status}` callbacks | Telegram-only |
| `error_handler.py` | Global exception handler | Telegram-only |

### apps/bot/handlers/private/

| Module | Purpose | Reuse |
|--------|---------|-------|
| `support.py` | `/start`, `/help`, `/cancel`, deep links | Telegram-only |
| `catalog.py` | Catalog section browser | Telegram-only |
| `promotions.py` | Discount display | Telegram-only |
| `about.py` | Company info | Telegram-only |
| `packages.py` | Package browser + order | Telegram-only |
| `pricing.py` | Pricing calculator FSM | Telegram-only |
| `my_orders.py` | Order history | Telegram-only |
| `payment.py` | Payment FSM | Telegram-only |
| `order.py` | Full order FSM | Telegram-only |
| `operator.py` | Operator contact flow | Telegram-only |
| `measurement_lead.py` | Free measurement FSM | Telegram-only |
| `lead_capture.py` | Lead capture FSM | Telegram-only |
| `ai_support.py` | AI conversation handler (catch-all) | Telegram-only |
| `ai_states.py` | FSM states + constants for AI support (AiSupportStates) | Telegram-only |
| `ai_detection.py` | Intent detection logic | **Needs adapter** — pure logic, but imports aiogram types |
| `ai_memory.py` | Redis AI memory management | **Needs adapter** |
| `ai_scoring.py` | Lead scoring + objection detection | **Needs adapter** — pure logic inside |
| `ai_openai.py` | OpenAI API integration | **Needs adapter** — should move to core/ |
| `ai_notifications.py` | Admin notification orchestration | Telegram-only |
| `ai_followups.py` | Async follow-up scheduling | Telegram-only |
| `ai_pricing_helpers.py` | Price display helpers | Telegram-only |
| `sales_closer.py` | Sales closing helpers | Telegram-only |

### apps/bot/handlers/callbacks/ (8 files)

| Module | Purpose | Reuse |
|--------|---------|-------|
| `cta_callbacks.py` | CTA button routing | Telegram-only |
| `kanban_callbacks.py` | Kanban pipeline management | Telegram-only |
| `lead_callbacks.py` | Lead detail callbacks | Telegram-only |
| `operator_callbacks.py` | Operator assist suggestions | Telegram-only |
| `package_callbacks.py` | Package inline buttons | Telegram-only |
| `payment_callbacks.py` | Payment flow callbacks | Telegram-only |
| `pipeline_callbacks.py` | Pipeline transition callbacks | Telegram-only |
| `sales_closer_callbacks.py` | Sales closer CTA buttons | Telegram-only |

Note: `lead_status.py` (the `lead:{id}:status:{status}` callback handler) lives in `handlers/admin/`, not here.

### apps/bot/handlers/group/

All 11 modules are Telegram-only (group chat events, moderation, welcome).

### apps/bot/middlewares/

All 7 middlewares are Telegram-only. The API will need its own middleware (JWT auth, CORS, etc.).

### apps/bot/states/

All 8 FSM state groups are Telegram-only (aiogram `StatesGroup`).

### apps/bot/keyboards/

All 9 keyboard modules are Telegram-only (aiogram `InlineKeyboardMarkup`, `ReplyKeyboardMarkup`).

### apps/bot/ai/

| Module | Purpose | Reuse |
|--------|---------|-------|
| `system_prompt.py` | GPT-4o system prompt + sanitization | **Needs adapter** — `sanitize_*` functions should move to `shared/utils/` |

---

## apps/scheduler/ (Reusable with caution)

| Module | Purpose | Reuse |
|--------|---------|-------|
| `main.py` | APScheduler bootstrap | Process-specific, not importable |
| `jobs/followup_jobs.py` | Follow-up checks | Reusable — calls services |
| `jobs/analytics_jobs.py` | Daily stats aggregation | Reusable |
| `jobs/broadcast_jobs.py` | Scheduled broadcast check | Reusable |
| `jobs/cache_jobs.py` | Redis cache maintenance | Reusable |
| `jobs/conversation_intelligence_jobs.py` | Conversation analysis | Reusable |
| `jobs/sales_autopilot_jobs.py` | Autopilot suggestions | Reusable |
| `jobs/closing_jobs.py` | Deal closing checks | Reusable |
| `jobs/auto_sales_jobs.py` | Auto-sales logic | Reusable |
| `jobs/outcome_resolver_jobs.py` | Tactic outcome resolution | Reusable |

---

## core/domain/ (Fully Reusable)

All domain models are frozen Pydantic models with no framework dependencies.

| Module | Entity | Reuse |
|--------|--------|-------|
| `user.py` | User | **Reusable** |
| `lead.py` | Lead, LeadAddons | **Reusable** |
| `appointment.py` | Appointment | **Reusable** |
| `audit.py` | AuditRecord | **Reusable** |
| `broadcast.py` | Broadcast | **Reusable** |
| `payment.py` | Payment | **Reusable** |
| `quote.py` | Quote, QuoteAddonDetail | **Reusable** |
| `warranty.py` | Warranty | **Reusable** |

---

## core/repositories/ (Fully Reusable)

13 abstract repository interfaces + 1 generic base. All pure ABCs with no framework dependency.

| Module | Interface | Reuse |
|--------|-----------|-------|
| `base.py` | `BaseRepository[T, IDType]` (generic CRUD contract) | **Reusable** |
| `user_repo.py` | `AbstractUserRepository` | **Reusable** |
| `lead_repo.py` | `AbstractLeadRepository` | **Reusable** |
| `pipeline_repo.py` | `AbstractPipelineRepository` | **Reusable** |
| `appointment_repo.py` | `AbstractAppointmentRepository` | **Reusable** |
| `broadcast_repo.py` | `AbstractBroadcastRepository` | **Reusable** |
| `payment_repo.py` | `AbstractPaymentRepository` | **Reusable** |
| `warranty_repo.py` | `AbstractWarrantyRepository` | **Reusable** |
| `admin_group_repo.py` | `AbstractAdminGroupRepository` | **Reusable** |
| `blocked_chat_repo.py` | `AbstractBlockedChatRepository` | **Reusable** |
| `group_join_repo.py` | `AbstractGroupJoinRepository` | **Reusable** |
| `group_settings_repo.py` | `AbstractGroupSettingsRepository` | **Reusable** |
| `tactic_outcome_repo.py` | `AbstractTacticOutcomeRepository` | **Reusable** |

Note: `lead_repo.py` is not listed separately in `core/repositories/` — there is no standalone `lead_action_repo` abstract. The concrete `PostgresLeadActionRepository` exists in infrastructure without an abstract counterpart.

---

## core/services/ (Mostly Reusable)

### CRM services (Reusable — accept AsyncSession via DI)

| Module | Class | Reuse |
|--------|-------|-------|
| `user_service.py` | `UserService` | **Reusable** |
| `lead_service.py` | `LeadService` | **Reusable** |
| `crm_service.py` | `CRMService` | **Reusable** |
| `pipeline_service.py` | `PipelineService` | **Reusable** |
| `pricing_service.py` | `PricingService` | **Reusable** (needs Redis) |
| `broadcast_service.py` | `BroadcastService` | **Reusable** |
| `payment_service.py` | `PaymentService` | **Reusable** |
| `warranty_service.py` | `WarrantyService` | **Reusable** |
| `admin_group_service.py` | `AdminGroupService` | **Reusable** |
| `group_settings_service.py` | `GroupSettingsService` | **Reusable** |
| `stats_service.py` | `StatsService` | **Reusable** |
| `lead_analytics_service.py` | `LeadAnalyticsService` | **Reusable** |
| `followup_service.py` | `FollowupService` | **Needs adapter** — sends Telegram messages internally |
| `lead_notification_service.py` | `LeadNotificationService` | Telegram-only — creates Bot instance |

### AI intelligence services (Reusable — pure functions, no I/O)

| Module | Function/Class | Reuse |
|--------|---------------|-------|
| `ai_orchestrator_service.py` | `build_ai_orchestrator_state()` | **Reusable** |
| `ai_sales_brain_service.py` | `build_sales_brain()` | **Reusable** |
| `ai_auto_closer_service.py` | `build_auto_close_reply()` | **Reusable** |
| `lead_intelligence_service.py` | `analyze_buyer_type()` | **Reusable** |
| `deal_radar_service.py` | `rank_lead_for_radar()` | **Reusable** |
| `conversation_intelligence_service.py` | `analyze_conversation()` | **Reusable** |
| `negotiation_engine_service.py` | `analyze_negotiation()` | **Reusable** |
| `conversation_memory_graph_service.py` | `analyze_conversation_graph()` | **Reusable** |
| `followup_brain_service.py` | `decide_follow_up()` | **Reusable** |
| `operator_assistant_service.py` | `build_operator_assist()` | **Reusable** |
| `revenue_predictor_service.py` | `predict_lead_revenue()` | **Reusable** |
| `sales_analytics_service.py` | `build_sales_analytics()` | **Reusable** |
| `signal_vector_service.py` | Signal normalization | **Reusable** |

### Services with dependency violations (need refactoring)

| Module | Issue | Fix |
|--------|-------|-----|
| `ai_sales_advice.py` | Imports from `apps.bot.ai.system_prompt` and `apps.bot.handlers.private.ai_openai` | Move `sanitize_*` to `shared/utils/`, move OpenAI client to `core/` |
| `deal_closer_service.py` | Imports from `apps.bot.ai.system_prompt` | Same fix |

---

## core/events/ (Reusable but underutilized)

| Module | Contents | Status |
|--------|----------|--------|
| `bus.py` | `EventBus`, `LeadCreated`, `StageChanged`, `AppointmentBooked`, `BroadcastCompleted` | Only `LeadCreated` and `StageChanged` are emitted. `handlers/` directory is empty. |

---

## infrastructure/ (Reusable)

### infrastructure/database/models/ (Reusable)

All 20 ORM models are framework-agnostic SQLAlchemy. Fully reusable from API layer.

### infrastructure/database/repositories/ (Reusable)

All 14 concrete repositories are reusable — they accept `AsyncSession` and return domain objects.

### infrastructure/database/session.py (Reusable)

- `get_session()`, `get_readonly_session()` — used by bot handlers and scheduler jobs
- `get_db()` — FastAPI dependency, already exists but unused
- `connect_database()`, `disconnect_database()` — lifecycle hooks

### infrastructure/di.py (Reusable)

All 19 factory functions accept `AsyncSession` and return service instances. The API can call the same factories via `Depends(get_db)`.

### infrastructure/cache/ (Reusable)

| Module | Purpose | Reuse |
|--------|---------|-------|
| `client.py` | Redis connection pool + `CacheClient` wrapper | **Reusable** |
| `keys.py` | `CacheKeys` (key builders) + `CacheTTL` (TTL constants) | **Reusable** |

### infrastructure/queue/ (Reusable)

| Module | Purpose | Reuse |
|--------|---------|-------|
| `app.py` | Celery app configuration | **Reusable** |
| `tasks/broadcast_tasks.py` | Async broadcast worker | **Reusable** |
| `tasks/notification_tasks.py` | Notification worker | **Reusable** |
| `tasks/export_tasks.py` | Export worker (stub) | **Reusable** |
| `tasks/package_tasks.py` | Package follow-up worker | **Reusable** |

### infrastructure/monitoring/ (Reusable)

| Module | Purpose | Reuse |
|--------|---------|-------|
| `prometheus.py` | Metric definitions, `/health` + `/metrics` endpoints | **Reusable** — can mount into FastAPI |

### infrastructure/storage/ (Reusable)

| Module | Purpose | Reuse |
|--------|---------|-------|
| `adapter.py` | File storage (local/S3) | **Reusable** |

---

## shared/ (Fully Reusable)

Everything under `shared/` is framework-agnostic.

| Module | Purpose | Reuse |
|--------|---------|-------|
| `config/settings.py` | Pydantic Settings (all env vars) | **Reusable** |
| `constants/enums.py` | All business enums (single source of truth) | **Reusable** |
| `constants/catalog.py` | Catalog data constants | **Reusable** |
| `exceptions/base.py` | Domain exception classes | **Reusable** |
| `i18n/locales/uz/messages.py` | Uzbek translation strings | **Reusable** |
| `logging/setup.py` | Structured logging config | **Reusable** |
| `utils/phone.py` | Phone number parsing | **Reusable** |
| `utils/area_parser.py` | Area text parsing | **Reusable** |
| `utils/lead_scoring.py` | Follow-up scheduling helpers | **Reusable** |
| `utils/deal_probability.py` | Deal probability engine | **Reusable** |
| `utils/pagination.py` | Pagination helpers | **Reusable** |
| `utils/formatting.py` | Text formatting | **Reusable** |
| `utils/business_hours.py` | Business hours check | **Reusable** |
| `utils/telegram_send.py` | Telegram send helpers | Telegram-only |
| `utils/retry.py` | Retry decorator | **Reusable** |
| `knowledge/uz.md` | Product knowledge base | **Reusable** |
