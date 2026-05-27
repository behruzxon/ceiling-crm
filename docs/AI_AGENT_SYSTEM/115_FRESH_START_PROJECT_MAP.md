# Fresh Start Project Map

**Date**: 2026-05-27 | **Commit**: ae299f9 | **Deploy**: NO | **Stage 1**: NOT APPLIED

## 1. What Currently Exists

### Telegram Bot
- 10 commands (/start, /menu, /catalog, /price, /order, /help, /cancel, /ai_off, /ai_help, /ai_reset)
- 9 main menu buttons + 6 AI mode buttons
- 50+ callback patterns across 13 namespaces
- 7 FSM flows (order, pricing, operator, catalog, measurement, payment, AI)
- Group support with deep-link URL buttons
- Admin commands (dashboard, pipeline, analytics, broadcasts, etc.)

### AI Assistant (Madina)
- OpenAI GPT-4o integration with JSON response format
- Deterministic price calculator (PriceCalculatorService)
- 130+ objection keywords (5 types + fuzzy regex + severity)
- Lead scoring 0-100 (Redis-backed, 10+ signals)
- Conversation memory (Redis 30-day + DB 12-message rolling)
- Prompt injection firewall (14 patterns) + output leak guard
- Sales closer with 10-min cooldown
- Negotiation engine with tactic rotation
- 6 quick buttons (/ai_help, /ai_reset, Narx, Katalog, Operator, Reset)

### Price Calculator
- PriceCalculatorService with DESIGN_PRICES_CUSTOMER source of truth
- Area parser (5x4, 20kv, 20m2, decimals, 1-500m2 bounds)
- Design parser (20 aliases -> 9 canonical designs)
- Automatic discounts (5% >20m2, 10% >40m2)
- Wired into bot AI price path (deterministic, no OpenAI for complete input)
- "Taxminiy" warning in every response

### Operator Handoff
- CRMOperatorHandoffService with queue model
- ETA-safe messages (no fake time promises)
- Priority scoring (urgent/high/normal/low)
- Phone masking, token redaction, 30-min dedup
- Migration ready (crm_operator_handoff_requests table)
- Wired into AI operator button

### CRM Web Platform
- 10 routes: login, dashboard, pipeline, leads, analytics, CRM inbox, contact detail, campaigns, agent, security
- Design system (vp-* classes) across all pages
- CRM inbox with KPI cards, live polling, keyboard shortcuts
- Contact detail with responsive grid and timeline
- Agent control center with rollout presets
- Campaign drafts with send-OFF banner
- Security audit dashboard

### Agent Pipeline
- LeadSignalService, TextNormalizationService, AgentDecisionEngine
- DynamicOfferService, ConversationPolicyService, AgentResponseOrchestrator
- ExecutionSandbox, Agent queue, 6-stage rollout (OFF->LOG_ONLY->DRY_RUN->CANARY->APPROVAL->LIVE)
- Quality simulator with 70+ scenarios

### Tests & Docs
- 5625 tests (5051 unit + 574 integration/simulation)
- 60+ docs in AI_AGENT_SYSTEM/
- Readiness scripts, preflight checks, rollback procedures

### Database
- 43+ migrations, PostgreSQL + Redis
- Models: users, leads, pipeline_stages, payments, broadcasts, AI conversations, agent memory, handoff requests

## 2. What Is Strong

| Area | Score | Why |
|------|-------|-----|
| Price Calculator | 9/10 | Deterministic, source-of-truth, tested |
| Safety/No-send | 9.5/10 | 20 flags OFF, injection firewall, forbidden claims |
| AI Objection Handling | 8/10 | 130+ keywords, fuzzy regex, severity |
| Lead Scoring | 9/10 | Multi-signal, Redis-backed, auto-classify |
| Config/Flags | 9/10 | Safe defaults, documented |
| Test Coverage | 8.5/10 | 5625 tests, strong service coverage |
| Architecture | 8.5/10 | Clean layers, centralized constants |
| AI Button UX | 8.5/10 | 6 buttons, help, reset, deterministic price |
| Knowledge Base | 8/10 | Hardened, room recs, forbidden claims |

## 3. What Is Still Missing

| Missing Feature | Impact | Complexity |
|----------------|--------|------------|
| Handoff queue web view | HIGH | MEDIUM |
| AI trace viewer in CRM | HIGH | MEDIUM |
| Missed leads dashboard | HIGH | MEDIUM |
| Price estimate history | MEDIUM | LOW |
| Analytics charts | MEDIUM | MEDIUM |
| Conversation replay in contact detail | HIGH | MEDIUM |
| Operator assignment UI | MEDIUM | MEDIUM |
| Handoff queue API endpoints | MEDIUM | LOW |
| Handoff auto-expire scheduler job | LOW | LOW |
| Photo/voice AI analysis | MEDIUM | HIGH |
| Stage 1 real observation data | CRITICAL | LOW (just apply) |
| Catalog media (photos) | MEDIUM | MEDIUM |

## 4. Next 10 Steps (Practical, Ordered)

| # | Step | What | Why |
|---|------|------|-----|
| 1 | Handoff Queue API | REST endpoints for queue/assign/resolve | Web needs data source |
| 2 | CRM Handoff Queue Web Page | Show operator queue in web | Operators need visibility |
| 3 | AI Trace Viewer | Show agent traces in contact timeline | Admin needs insight |
| 4 | Missed Leads Dashboard | Highlight unanswered/lost leads | Prevent client loss |
| 5 | Analytics Charts | Add chart.js to analytics page | Visual insights |
| 6 | Conversation Replay | Full message history in contact detail | Operator context |
| 7 | Price Estimate History | Show past estimates in contact profile | Sales context |
| 8 | Operator Assignment UI | Assign operators to handoff requests | Workflow management |
| 9 | Handoff Auto-Expire Job | Scheduler job for stale requests | Queue hygiene |
| 10 | Stage 1 LOG_ONLY Apply | Real observation with live traffic | Validate everything |

## 5. Do NOT Touch Yet

- Live sender (AGENT_EXECUTION_LIVE_SENDER_ENABLED)
- Campaign send (CRM_CAMPAIGN_SEND_ENABLED)
- Operator live reply (CRM_OPERATOR_REPLY_ENABLED)
- Followups (AGENT_FOLLOWUPS_ENABLED)
- Auto execute (AGENT_EXECUTION_AUTO_EXECUTE_APPROVED)
- Stage 2 DRY_RUN (needs Stage 1 data first)
- Production flags (all must stay OFF)
- Catalog behavior (stable, no changes needed)
- Pricing constants (verified source of truth)

## 6. Recommendation

**Build the Handoff Queue API + Web Page next.**

Why: It's the highest-impact web improvement that uses the already-built CRMOperatorHandoffService. Operators get immediate visibility into customer requests. Low risk, medium complexity, no migration needed.
