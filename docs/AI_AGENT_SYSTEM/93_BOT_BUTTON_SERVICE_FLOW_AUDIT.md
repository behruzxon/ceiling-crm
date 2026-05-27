# Full Bot Button / Service / Flow Deep Audit

**Date**: 2026-05-27
**Branch**: feature/packages-update
**Type**: READ-ONLY audit (no code changes)

---

## A) Executive Summary

**Bot Score: 7.6/10**

| Area | Score |
|------|-------|
| Button structure | 8/10 |
| Menu UX | 8/10 |
| AI mode UX | 8/10 |
| Catalog flow | 6/10 |
| Price flow | 7/10 |
| Order flow | 7/10 |
| Operator handoff | 6/10 |
| CRM integration | 8/10 |
| Agent integration | 8/10 |
| Safety | 9/10 |
| Test coverage | 7/10 |
| Production readiness | 7/10 |

**Totals discovered:**
- 10 bot commands
- 9 main menu buttons + 6 AI mode buttons
- 50+ unique callback_data patterns across 13 namespaces
- 7 major FSM flows
- 25+ core services
- 13+ scheduler jobs
- 4,282+ tests across 168 files

**Strongest:** AI intelligence pipeline, CRM data persistence, admin notification system, safety defaults
**Weakest:** Catalog (no media), operator handoff UX, 5 handler flows untested

---

## B) Command Inventory

| Command | Description | Handler | FSM State | CRM Write |
|---------|-------------|---------|-----------|-----------|
| /start | Bot start + deep-link routing | support.py | Clears | Indirect |
| /menu | Show main menu | support.py | No change | None |
| /catalog | Catalog | catalog.py | CatalogStates | None |
| /price | Price calculator | pricing.py | PricingStates | Draft lead |
| /order | Order | lead_capture.py | LeadCaptureStates | Lead |
| /help | Help | support.py | Clears | None |
| /cancel | Cancel | support.py | Clears | None |
| /ai_off | Exit AI mode | ai_support.py | Clears | None |
| /ai_help | AI capabilities | ai_support.py | No change | None |
| /ai_reset | Clear AI memory | ai_support.py | Re-enters AI | Clears Redis |

Deep-link payloads: zakaz, price, katalog, paketlar, orders, operator, discounts, ai, about, share_phone

---

## C) Main Menu Button Inventory

| Button | Handler | FSM Entry | CRM Write | AI Signal |
|--------|---------|-----------|-----------|-----------|
| 🛒 Zakaz berish | order.py | OrderFlow | Lead + pipeline | No |
| 💰 Narx kalkulyator | pricing.py | PricingStates | Draft lead | No |
| 📂 Katalog | catalog.py | CatalogStates | None | No |
| 🎁 Tayyor paketlar | packages.py | None (inline) | Lead on order | No |
| 📦 Buyurtmalarim | my_orders.py | None | None (read) | No |
| ☎️ Operator | operator.py | OperatorFlow | Admin alert | No |
| 🎉 Chegirmalar | promotions.py | None (inline) | None | No |
| 🤖 AI yordam | ai_support.py | AiSupportStates | Conditional | Full pipeline |
| ⭐ Biz haqimizda | about.py | None (inline) | None | No |

## D) AI Mode Button Inventory

| Button | Handler | Action |
|--------|---------|--------|
| 💰 Narx | handle_ai_price_btn | Price input prompt |
| 📂 Katalog | handle_ai_catalog_btn | Catalog list |
| 👨‍💼 Operator | handle_ai_operator_btn | Operator handoff |
| 🔄 Reset | handle_ai_reset_btn | Clear AI memory |
| ❓ Yordam | handle_ai_help_btn | Help text |
| ⬅️ Menyu | handle_ai_exit | Exit AI mode |

---

## E) Callback Inventory (50+ patterns)

| Namespace | Patterns | File | Purpose |
|-----------|----------|------|---------|
| cta:* | 5 | cta_callbacks.py | Discount/order/pricing/operator/catalog CTA |
| kanban:* | 8 | kanban_callbacks.py | Admin kanban board navigation |
| lead:* | 3 | lead_callbacks.py | Lead view/assign/status |
| op:* | 3 | operator_callbacks.py | Operator suggestion scripts |
| pkg:admin:* | 8 | package_callbacks.py | Admin lead actions (hot/warm/cold/block) |
| pay:* | 2 | payment_callbacks.py | Payment approve/reject |
| pipeline:* | 8 | pipeline_callbacks.py | Stage advance/lost/timeline |
| closer:* | 6 | sales_closer_callbacks.py | Sales closer book/call/catalog/price |
| agentfu:* | 5 | agent_followup_callbacks.py | Follow-up CTA routing |
| agentesc:* | 2 | admin_escalation_callbacks.py | Admin escalation actions |
| agentexec:* | 3 | agent_execution_callbacks.py | Agent execution approve/reject |
| design:* | 1 | pricing.py | Design selection in calculator |
| bcast:* | 9 | broadcasts.py | Broadcast segment/payload/confirm |
| grpmenu:* | 9 | group/start.py | Group menu deep-links |
| gs:* | 2 | group/admin.py | Group settings toggle |
| stats:* | 1 | admin/stats.py | Stats period selector |

---

## F) FSM Flow Maps

### Order Flow (7 states)
```
waiting_for_name → waiting_for_phone → waiting_for_district
→ waiting_for_category → waiting_for_area → waiting_for_location
→ [Lead + Pipeline QUOTE + Admin notify]
```

### Pricing Flow (3 states)
```
waiting_for_length → waiting_for_width → choosing_design
→ [Quote breakdown] → Order CTA / Operator CTA / Restart
```

### AI Support Flow (7 states)
```
waiting_for_name → waiting_for_ai_question (main loop)
→ waiting_for_district → waiting_for_phone
→ waiting_photo → waiting_room → waiting_area_photo
```

### Operator Flow (2 states)
```
waiting_for_confirmation → waiting_for_contact → [Admin alert]
```

### Measurement Lead Flow (4 states)
```
waiting_for_name → waiting_for_phone → waiting_for_location
→ waiting_for_time → [Lead + Admin notify]
```

---

## G) Pricing Structure

**Customer-facing (AI):** 80k-140k UZS/m2
**Internal quote:** 100k-300k UZS/m2

| Design | AI Price | Quote Price |
|--------|----------|-------------|
| Adnatonniy | 80,000 | 120,000 |
| Hi Tech | 120,000 | 200,000 |
| Mramor | 120,000 | 220,000 |
| Gulli | 130,000 | 250,000 |
| Qora UF | 140,000 | 180,000 |
| Kosmos | 120,000 | 300,000 |

Discounts: >20m2 = 5%, >40m2 = 10%
Add-ons: LED strip 25k/m, cornice 15k/m, chandelier holes 50k each

---

## H) Service Inventory (25+ services)

| Service | Purpose | Bot | Web | Scheduler |
|---------|---------|-----|-----|-----------|
| PricingService | Quote calculation | Yes | Yes | No |
| LeadService | Lead CRUD + pipeline | Yes | Yes | No |
| CRMService | Pipeline transitions | No | Yes | No |
| PipelineService | Kanban view | No | Yes | No |
| LeadNotificationService | Admin alerts | Yes | No | No |
| FollowupService | Due followup processing | No | No | Yes |
| BroadcastService | Message queuing | No | No | Yes |
| PaymentService | Payment lifecycle | No | Yes | No |
| AIService | OpenAI integration | Yes | No | No |
| LeadSignalService | Intent extraction | Yes | No | No |
| AgentDecisionEngine | State machine | Yes | No | No |
| AgentResponseOrchestrator | Pipeline coordinator | Yes | No | No |
| DynamicOfferService | CTA selection | Yes | No | No |
| ConversationPolicyService | Safety limits | Yes | No | No |
| AutoSalesService | Auto-reply decisions | Yes | No | Yes |
| CRMContactService | Contact sync | No | Yes | No |
| CRMMessageService | Message history | Yes | Yes | No |
| ExportService | Data export | No | Yes | No |
| AnalyticsService | Daily metrics | No | No | Yes |
| JourneyEventService | Event tracking | Yes | No | No |

---

## I) CRM Integration Map

| Flow | Contact | Lead | Pipeline | Score | Temp | Timeline | Admin Notify |
|------|---------|------|----------|-------|------|----------|--------------|
| Order | Yes | Create | QUOTE | No | No | Yes | Yes |
| Pricing | No | Draft | No | No | No | No | No |
| Package order | Yes | Upsert | PKG_SELECTED | No | No | Yes | Yes |
| Measurement | Yes | Create | NEW | No | No | Yes | Yes |
| AI phone capture | Yes | Create | NEW | +40 | Yes | Yes | Yes |
| AI price query | No | No | No | +15 | No | No | No |
| AI objection | No | No | No | +/-5-10 | No | No | Conditional |
| Operator request | No | No | No | No | No | No | Yes |
| Payment | No | No | No | No | No | Yes | Yes |

---

## J) Safety / No-Send Audit

**All 20 dangerous flags default to FALSE.** Key gates:

| Gate | Default | Controls |
|------|---------|----------|
| agent_followups_enabled | False | Automated follow-ups |
| agent_execution_live_sender_enabled | False | Real message sending |
| crm_campaign_send_enabled | False | Campaign broadcasts |
| crm_operator_reply_enabled | False | Operator reply |
| admin_session_auth_enabled | False | Web auth |
| agent_execution_mode | log_only | Agent observation only |

**Real sends in current state:** NONE. Only bot replies to user messages.
**Admin group notifications:** fire-and-forget, non-blocking.
**Stop words:** 12+ patterns (kerak emas, stop, yozmang, etc.)
**Injection defense:** 14 regex patterns pre+post flight.

---

## K) Test Coverage Map

| Area | Tests | Level | Gap |
|------|-------|-------|-----|
| AI support (button/flow/scoring) | 617 | HIGH | Handler mocking |
| Agent pipeline services | 2,532 | VERY HIGH | None |
| Web UI | 685 | HIGH | None |
| Integration/agent | 380 | MEDIUM-HIGH | None |
| Simulation | 125 | MEDIUM | None |
| **catalog.py** | **0** | **NONE** | **CRITICAL** |
| **packages.py** | **0** | **NONE** | **CRITICAL** |
| **order.py** | **0** | **NONE** | **CRITICAL** |
| **lead_capture.py** | **0** | **NONE** | **CRITICAL** |
| **measurement_lead.py** | **0** | **NONE** | **CRITICAL** |
| **payment.py** | **0** | **NONE** | **CRITICAL** |
| pricing.py | 2 refs | LOW | HIGH |
| operator.py | 4 refs | LOW | MEDIUM |

---

## L) AI Knowledge / Training Map

### What AI knows:
- Company: 6 years, 15-year warranty, free measurement
- Pricing: 8 design types, 80k-140k UZS/m2, discount tiers
- Service area: Kashkadarya districts (14)
- Hours: 09:00-20:00 daily
- Lead scoring: hot/warm/cold classification
- Objection handling: 5 types with negotiation tactics

### What AI should learn:
- Exact button behavior (what each menu button does)
- Catalog structure (which designs available, photos)
- Order flow steps (what user needs to provide)
- Operator availability (not hardcoded promises)
- Package details (premium/standard/econom)
- Seasonal promotions (dynamic)

### Safety rules embedded:
- No exact final price without measurement
- No fake discounts
- No "bugun qilamiz" promises
- Stop on "kerak emas"
- Phone redaction in traces

---

## M) Top 25 Improvements

| # | Improvement | Priority | Risk | Impact |
|---|-------------|----------|------|--------|
| 1 | Test catalog/packages/order/lead_capture handlers | HIGH | LOW | HIGH |
| 2 | Test pricing.py with edge cases | HIGH | LOW | HIGH |
| 3 | Catalog media integration (photos per design) | HIGH | LOW | HIGH |
| 4 | Price calculator inline service | MEDIUM | LOW | HIGH |
| 5 | Operator handoff queue + safe ETA | MEDIUM | MEDIUM | HIGH |
| 6 | Order flow step-by-step polish | MEDIUM | LOW | MEDIUM |
| 7 | Photo/voice AI analysis | MEDIUM | MEDIUM | HIGH |
| 8 | AI knowledge base update (button behaviors) | MEDIUM | LOW | MEDIUM |
| 9 | Button analytics (track clicks) | LOW | LOW | MEDIUM |
| 10 | Admin per-user AI control | LOW | LOW | MEDIUM |
| 11 | Measurement lead flow polish | MEDIUM | LOW | MEDIUM |
| 12 | Package comparison view | MEDIUM | LOW | MEDIUM |
| 13 | Dynamic pricing from DB | MEDIUM | MEDIUM | HIGH |
| 14 | Payment flow testing | HIGH | LOW | MEDIUM |
| 15 | E2E bot flow simulation tests | MEDIUM | LOW | HIGH |
| 16 | AI response quality simulator | LOW | LOW | MEDIUM |
| 17 | Campaign send staging tests | MEDIUM | LOW | MEDIUM |
| 18 | Enable ADMIN_SESSION_AUTH in production | HIGH | LOW | HIGH |
| 19 | Enable ADMIN_CSRF in production | HIGH | LOW | HIGH |
| 20 | Controlled live reply upgrade | HIGH | HIGH | HIGH |
| 21 | Group moderation analytics | LOW | LOW | LOW |
| 22 | Multi-language response mode | MEDIUM | LOW | MEDIUM |
| 23 | Warranty claim flow | LOW | LOW | LOW |
| 24 | Referral/promotion tracking | LOW | LOW | MEDIUM |
| 25 | Load test CRM inbox polling | LOW | LOW | LOW |

---

## N) Recommended Next Steps

### Immediate (Step CH)
Test the 6 untested critical handler flows (catalog, packages, order, lead_capture, measurement_lead, payment) with 60+ tests.

### Short-term (Steps CI-CK)
- CI: Catalog media integration (design photos)
- CJ: Price calculator inline polish
- CK: Operator handoff UX improvement

### Medium-term (Steps CL-CN)
- CL: Photo/voice AI funnel
- CM: AI knowledge base enrichment
- CN: Button analytics dashboard

### Before production
- Enable ADMIN_SESSION_AUTH and ADMIN_CSRF
- Apply Stage 1 LOG_ONLY with monitoring
- Complete 30min active + 24h passive observation

**Code changed in this audit: NONE (read-only)**
