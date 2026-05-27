# AI Button Deep Audit

**Date**: 2026-05-27
**Branch**: feature/packages-update
**Type**: READ-ONLY audit (no code changes)

---

## A) Executive Summary

**AI Button Score: 7.8/10**

| Area | Score |
|------|-------|
| Entry UX | 7/10 |
| Conversation quality | 8/10 |
| Price understanding | 9/10 |
| Objection handling | 8/10 |
| CRM integration | 9/10 |
| Agent pipeline integration | 8/10 |
| Multilingual support | 7/10 |
| Safety | 9/10 |
| Operator handoff | 6/10 |
| Memory/context | 8/10 |
| Production readiness | 8/10 |

**Strongest parts:**
- Price calculation with area parsing (5x4 -> 20 m2) and design-specific pricing
- Comprehensive lead scoring (0-100) with 10+ signal types
- Multi-layer objection handling with negotiation engine
- Full CRM pipeline: lead -> score -> temperature -> admin notification
- Safety: injection firewall, output leak guard, phone redaction, rate limiting

**Weakest parts:**
- Operator handoff UX is basic (no queue, no status, no ETA)
- No photo/voice analysis
- No explicit AI mode indicator in chat
- Missing test coverage for entry flow and CRM logging path

**Go/No-Go for current AI button: GO (with monitoring)**
The AI button is production-ready for LOG_ONLY observation. User-facing replies work independently of agent mode. No sends, no follow-ups, no live actions in default state.

---

## B) AI Button Flow Map

```
User taps "AI yordam" button (or /start ai deep-link)
  |
  v
cmd_ai_start() [ai_support.py:149]
  |
  +-- Group chat? --> Show popup "faqat shaxsiy chatda", return
  |
  +-- Private chat:
      |
      +-- Load AI memory (Redis, 30-day TTL)
      |
      +-- Has name in memory?
      |   |
      |   +-- YES --> Set state: waiting_for_ai_question
      |   |           Send greeting with memory context
      |   |
      |   +-- NO  --> Set state: waiting_for_name
      |               Ask "Ismingiz nima?"
      |
      v
[waiting_for_ai_question] -- User sends text -->
  |
  +-- Fire async tasks (non-blocking):
  |   +-- _ai_stats_incr("messages_total")
  |   +-- _process_lead_signal(user_id, text)
  |   +-- _run_orchestrator(user_id, text)
  |
  +-- Intent short-circuit detection (before OpenAI):
  |   +-- Greeting? --> Return personalized greeting
  |   +-- Measurement request? --> Jump to measurement_lead flow (+25 score)
  |   +-- Catalog request? --> Show catalog + soft CTA (+5 score)
  |   +-- Stop signal? --> Disable followups, confirm stop
  |   +-- Confirmation? --> Neutral filler "Yaxshi"
  |   +-- Objection? --> Negotiation engine reply (+5/-10 score)
  |   +-- Price query? --> Parse area/design, show price (+15 score)
  |
  +-- Auto-reply check (_try_auto_reply):
  |   +-- Matched template? --> Send template, skip OpenAI
  |   +-- Need escalation? --> Alert admin, force OpenAI
  |
  +-- Rate limit check (100/day):
  |   +-- Over limit? --> "Kunlik limit tugadi", return
  |
  +-- OpenAI GPT call:
  |   +-- Build context (profile + history + summary)
  |   +-- Injection firewall (pre-flight)
  |   +-- Call GPT-4 (temperature=0.3, JSON response)
  |   +-- Parse: intent, reply, lead_temperature, closing_confidence
  |   +-- Leak guard (post-flight)
  |
  +-- Post-processing:
      +-- Send reply to user
      +-- Sales closer CTA (if score >= 40 or intent matches)
      +-- Persist exchange to DB (ai_conversations + ai_memory)
      +-- Update lead scoring in CRM (lead_temperature, closing_confidence)
      +-- Update Redis memory (30-day)
      +-- Log event
```

---

## C) Feature Inventory

| Feature | Exists? | File/Function | Quality | Notes |
|---------|---------|---------------|---------|-------|
| AI button in private keyboard | YES | keyboards/main_menu.py:42 | Good | "AI yordam" text, row 4 col 2 |
| AI deep-link from group | YES | keyboards/main_menu.py:84 | Good | URL button ?start=ai |
| Group callback handler | YES | handlers/group/start.py:90 | Good | DM-only alert popup |
| Name collection FSM | YES | ai_support.py:212 | Good | Validates with is_valid_name() |
| Greeting detection | YES | ai_support.py:807-811 | Good | Multi-language greetings |
| Price calculation | YES | ai_support.py:900-929 | Excellent | Area parsing (5x4), design prices, discounts |
| Objection detection | YES | ai_scoring.py:244-279 | Excellent | 130+ keywords, 5 types, severity scoring |
| Negotiation engine | YES | negotiation_engine_service.py | Good | 5 tactics, rotation, escalation |
| Lead scoring (Redis) | YES | ai_scoring.py | Excellent | 0-100, 10+ signal types |
| Conversation memory (Redis) | YES | ai_memory.py | Good | 30-day TTL, full context |
| Conversation history (DB) | YES | ai_openai.py | Good | Rolling 12 messages + summary |
| OpenAI GPT integration | YES | ai_openai.py:349-361 | Excellent | JSON response, 3 retries, failsafe |
| System prompt | YES | ai/system_prompt.py | Good | 196 lines, pricing table, guardrails |
| Knowledge base | YES | shared/knowledge/uz.md | Good | Company info, FAQ, warranty |
| Injection firewall | YES | shared/utils/sanitize.py | Excellent | 14 patterns, pre+post flight |
| Rate limiting | YES | ai_support_auto_reply.py:18 | Good | 100/day hard cap |
| Stop signal handling | YES | ai_support.py:876-887 | Good | Multi-language, disables followups |
| Auto-reply templates | YES | ai_support_auto_reply.py | Good | Intent-based, escalation-aware |
| Sales closer CTA | YES | sales_closer.py | Good | Score-based, 10-min cooldown |
| Admin notifications | YES | ai_notifications.py | Excellent | Phone, lead, interest alerts |
| CRM lead scoring | YES | ai_notifications.py | Good | temperature, confidence, next_followup |
| Agent orchestrator | YES | ai_support_agent.py | Good | Fire-and-forget, trace logging |
| Lead signal extraction | YES | lead_signal_service.py | Excellent | 87 tests, full coverage |
| Text normalization | YES | text_normalization_service.py | Good | Cyrillic->Latin, typo correction |
| Decision engine | YES | agent_decision_engine.py | Good | State machine, action selection |
| Dynamic offers | YES | dynamic_offer_service.py | Good | Contextual CTA selection |
| Conversation policy | YES | conversation_policy_service.py | Good | Safety limits, followup caps |
| Catalog request handling | YES | ai_support.py:849-872 | Good | Room+design detection, channel link |
| Measurement redirect | YES | ai_support.py:841-847 | Good | Jumps to measurement_lead flow |
| Phone collection | YES | ai_support.py:335-382 | Good | FSM-based, validates format |
| District collection | YES | ai_support.py:456-572 | Good | 14 districts + Cyrillic aliases |
| Photo analysis | NO | - | - | Not implemented |
| Voice transcription | NO | - | - | Not implemented |
| AI mode status indicator | NO | - | - | No visual "AI mode" badge |
| AI menu commands | NO | - | - | No /ai_help, /ai_reset, /ai_status |
| Admin AI control panel | PARTIAL | agent.html | Good | Web dashboard, not per-user control |
| AI usage analytics | PARTIAL | ai_memory.py stats | Basic | Daily counters, no dashboard |
| Operator handoff UX | BASIC | operator_router | Fair | Simple redirect, no queue/ETA |
| Fuzzy text matching | PARTIAL | text_normalization | Fair | Typo correction, but limited |
| Deal probability engine | YES | deal_probability.py | Good | Multi-signal, complementary to scoring |
| Buyer type analysis | YES | lead_intelligence_service.py | Good | 4 types, confidence scoring |
| Revenue prediction | YES | revenue_predictor_service.py | Good | Range estimate, upsell potential |

---

## D) Intelligence Evaluation

| Scenario | Expected Behavior | Current Behavior | Score | Gap |
|----------|-------------------|------------------|-------|-----|
| "20 kv qancha" | Parse area=20, show price | Parses "20" -> shows price table with design options | 9/10 | None |
| "qimmat ekan" | Detect price objection, negotiate | Detects "expensive" objection, negotiation engine selects tactic (cheaper_alt/value_reframe) | 8/10 | Could personalize with area context |
| "operator kerak" | Handoff to operator | Detects operator intent, shows operator contact | 6/10 | No queue, no ETA, no status tracking |
| "kerak emas" | Stop all AI, confirm | Detects stop, disables followups, cancels pending, confirms | 9/10 | None |
| "narxi qancha" (Cyrillic) | Normalize, treat as price query | TextNormalizationService converts Cyrillic->Latin, detects price intent | 8/10 | Some Cyrillic variants may miss |
| "katalog bormi" | Show catalog options | Detects catalog intent, shows design categories + channel link | 8/10 | No inline gallery, just link |
| "gulli potolok" | Recognize design, show info | Detects "gulli" design, includes in price calc context | 8/10 | Could show photo/sample |
| "telefon qoldirish" | Collect phone | Triggers phone collection FSM, validates format | 8/10 | None |
| "rasm yuborish" | Analyze room photo | NOT HANDLED | 2/10 | Photo analysis not implemented |
| "voice yuborish" | Transcribe + process | NOT HANDLED | 1/10 | Voice transcription not implemented |
| "5x4 mehmonxona hi tech" | Parse all, full price | Parses area=20, room=mehmonxona, design=Hi Tech, shows full price | 9/10 | None |
| "chegirma bormi" | Explain discount tiers | Detects "compare" objection, negotiation engine responds | 7/10 | Could show actual discount table |
| Russian "сколько стоит" | Understand, reply in Uzbek | Normalization catches "сколько", maps to price intent, replies in Uzbek | 7/10 | Russian->Uzbek mapping is keyword-based |

---

## E) CRM/Agent Integration

### Fully Integrated
- Lead score persisted to Redis (30-day) + LeadModel.score (DB)
- Lead temperature written to LeadModel.lead_temperature after each OpenAI call
- Closing confidence written to LeadModel.closing_confidence
- next_follow_up_at computed and written via update_ai_scoring()
- Phone captured -> LeadModel.phone + admin notification
- Area/district enrichment -> LeadModel.room_area, LeadModel.district
- Conversation history -> AiConversationModel (rolling 12 messages + summary)
- AI memory profile -> AiMemoryModel (extracted fields, turn count)
- Admin notifications: phone capture, new lead, warm interest, hot lead alerts
- Agent orchestrator trace -> AgentMemoryModel.memory_data
- Lead signal extraction -> intent/objection/urgency signals
- Decision engine -> customer state + recommended action
- Dynamic offer -> contextual CTA selection
- Conversation policy -> followup limits, escalation rules
- Sales closer -> proactive closing CTA with cooldown

### Partial
- Buyer type: computed in notification path, not real-time in AI handler
- Dynamic offer: generated by orchestrator but not directly rendered to user
- Conversation policy: evaluated but advisory (doesn't block user-facing reply)
- Execution sandbox: schema exists, not wired into active AI flow yet

### Missing
- AI messages NOT written to lead_actions table (stored in ai_conversations instead)
- operator_needed is not a direct DB flag (derived from agent memory state)
- No real-time CRM timeline entry per AI message (only via notifications)
- No CRM contact auto-creation from AI flow (requires phone capture first)

---

## F) Safety Audit

| Area | Status | Details |
|------|--------|---------|
| No-send behavior | SAFE | AI replies always reach user regardless of agent mode. LOG_ONLY only affects backend traces. No sends, no followups in default state. |
| Stop behavior | SAFE | "kerak emas", "stop", "yozmang" + 10 variants detected. Disables followups, cancels pending, confirms to user. Works in both active and passive AI modes. |
| Fake claim guard | PARTIAL | Blocks "100% kafolat", "eng arzon narx", "aniq narx aytaman", "bugun qilamiz". System prompt advises honesty. Gap: no explicit guard against invented discounts from OpenAI. |
| Secrets redaction | SAFE | Phones masked in memory as phone_masked. Traces redact full numbers and API tokens before logging. No secrets in templates. |
| Rate limit | SAFE | 100 calls/user/day hard cap. Consecutive auto-reply tracking. 10-min sales closer cooldown. 5-min objection dedup. |
| Fallback behavior | SAFE | OpenAI fail -> 3 retries with backoff -> failsafe message + operator link. User message saved regardless. Prometheus error counter. |
| Injection defense | SAFE | Pre-flight: 14 regex patterns block jailbreaks (EN/RU/UZ). Post-flight: leak guard checks for system prompt markers in reply. |
| Double-reply prevention | SAFE | Auto-reply returns True/False; caller returns early on True. Orchestrator is fire-and-forget (doesn't send replies). |
| LOG_ONLY safety | SAFE | User experience unchanged. Orchestrator writes traces only. No hidden side effects. |

---

## G) Test Coverage

### Current Tests (211 functions across AI-related files)

| File | Tests | Coverage |
|------|-------|----------|
| test_step_l_lead_signal_service.py | 87 | Excellent - intent, objection, urgency, area, budget, stop |
| test_step_o_agent_response_orchestrator.py | 41 | Excellent - full pipeline, safety, trace redaction |
| test_step_i_ai_composer.py | 26 | Good - validation, false claims, injection |
| test_ai_orchestrator_service.py | 23 | Good - priority, risk, revenue, strategy |
| test_step_bn_ai_support_refactor_imports.py | 15 | Good - module structure, imports |
| test_ai_auto_closer_service.py | 11 | Good - strategy, confidence |
| test_ai_sales_brain_service.py | 8 | Good - priority, risk, follow-up caps |
| integration/agent/ (4 files) | ~20 | Good - campaign flow, safety checks |
| simulation/agent/ | ~10 | Basic - agent simulation framework |

### Missing Tests (Recommended)

| Gap | Priority | Risk | Recommended Test |
|-----|----------|------|------------------|
| AI button entry flow (cmd_ai_start) | HIGH | FSM state mismatch | Test button press -> state transition -> greeting |
| Objection handler behavior (_handle_objection) | HIGH | Wrong reply, score error | Test each objection type -> verify reply + score delta |
| CRM logging from AI path | HIGH | Leads not tracked | Mock CRM calls, verify logging in success+error |
| Stop flow end-to-end | HIGH | Followups continue | Test stop -> verify disable + cancel + no followup |
| Auto-reply vs orchestrator conflict | MEDIUM | Double reply | Test parallel auto-reply + orchestrator don't conflict |
| Sales closer integration | MEDIUM | Conflicting CTA | Test closer params match AI state |
| Passive handler (default_state) | MEDIUM | Incorrect routing | Test free-text DM without AI button |
| Lead scoring progression | MEDIUM | Score plateau | Test sequential messages -> verify score increments |
| Redis failure recovery | LOW | Silent degradation | Test Redis down -> verify graceful fallback |
| OpenAI JSON parse error | LOW | Unhandled exception | Test malformed JSON -> verify failsafe |

---

## H) Top 20 Improvements

| # | Improvement | Priority | Risk | Impact | Suggested Step |
|---|-------------|----------|------|--------|----------------|
| 1 | Add AI button entry flow tests | HIGH | LOW | HIGH | Step CF |
| 2 | Add objection handler unit tests | HIGH | LOW | HIGH | Step CF |
| 3 | Add CRM logging path tests | HIGH | LOW | HIGH | Step CF |
| 4 | Add end-to-end stop flow test | HIGH | LOW | HIGH | Step CF |
| 5 | Operator handoff UX (queue + ETA) | HIGH | MEDIUM | HIGH | Step CE |
| 6 | AI mode status indicator in chat | MEDIUM | LOW | MEDIUM | Step CE |
| 7 | /ai_help, /ai_reset, /ai_status commands | MEDIUM | LOW | MEDIUM | Step CE |
| 8 | Price calculator inline integration | MEDIUM | LOW | HIGH | Step CG |
| 9 | Catalog inline gallery (not just link) | MEDIUM | LOW | HIGH | Step CH |
| 10 | Discount table display on "chegirma" | MEDIUM | LOW | MEDIUM | Step CG |
| 11 | Photo room analysis (GPT-4 Vision) | MEDIUM | MEDIUM | HIGH | Step CI |
| 12 | Voice message transcription | MEDIUM | MEDIUM | MEDIUM | Step CI |
| 13 | AI usage analytics dashboard | LOW | LOW | MEDIUM | Step CJ |
| 14 | Per-user AI control (admin) | LOW | LOW | MEDIUM | Step CJ |
| 15 | Discount-claim post-processing guard | LOW | LOW | LOW | Step CE |
| 16 | Smarter question flow (guided funnel) | MEDIUM | LOW | HIGH | Step CE |
| 17 | Sales closer integration tests | MEDIUM | LOW | MEDIUM | Step CF |
| 18 | Redis failure mode tests | LOW | LOW | LOW | Step CF |
| 19 | Controlled live reply upgrade | HIGH | HIGH | HIGH | Step CK |
| 20 | Multi-turn negotiation memory | LOW | LOW | MEDIUM | Step CE |

---

## I) Recommended Roadmap

### Step CE -- AI Button UX + Menu Polish
- Add AI mode status indicator ("AI rejimdasiz" badge)
- Add /ai_help, /ai_reset, /ai_status commands
- Improve operator handoff UX (queue notification, ETA estimate)
- Add discount-claim guard to sanitize_ai_reply()
- Smarter guided question flow (area -> design -> district -> price)
- Multi-turn negotiation memory improvements
- Risk: LOW, Impact: MEDIUM

### Step CF -- AI Button Intelligence Test Pack
- 50+ tests: entry flow, objection handler, CRM logging, stop flow
- Auto-reply vs orchestrator conflict tests
- Sales closer integration tests
- Redis failure recovery tests
- Score progression tests
- Risk: LOW, Impact: HIGH

### Step CG -- Price Calculator Integration
- Inline price calculator (user selects design + enters area)
- Discount table display on "chegirma bormi"
- Package comparison view
- Addon pricing integration
- Risk: LOW, Impact: HIGH

### Step CH -- Catalog/Portfolio Integration
- Inline photo gallery (not just channel link)
- Design-specific sample images
- Room-type based recommendations
- Before/after portfolio display
- Risk: LOW, Impact: HIGH

### Step CI -- Photo/Voice AI Integration
- GPT-4 Vision for room photo analysis
- Voice message transcription (Whisper API)
- Room measurement estimation from photo
- Design suggestion from room photo
- Risk: MEDIUM, Impact: HIGH

### Step CJ -- AI Button Analytics Dashboard
- AI usage metrics (daily/weekly/monthly)
- Conversion funnel (AI -> price -> phone -> measurement)
- Per-user AI interaction history
- Objection type distribution
- Score progression analytics
- Risk: LOW, Impact: MEDIUM

### Step CK -- Controlled Live Reply Upgrade
- Requires Stage 2+ (DRY_RUN minimum)
- Enable orchestrator-driven replies (not just traces)
- Canary testing with selected users
- Admin approval queue for AI-generated messages
- Risk: HIGH, Impact: HIGH

---

## J) Final Recommendation

### What to do next
1. **Apply Stage 1 LOG_ONLY** -- AI button is safe, user-facing behavior unchanged
2. **Step CF first** -- Add missing test coverage (entry flow, objection handler, CRM logging, stop flow)
3. **Step CE second** -- Polish AI UX (status indicator, menu commands, operator handoff)
4. **Step CG/CH third** -- Price calculator and catalog integration for stronger engagement

### What NOT to enable yet
- Do NOT enable live sender
- Do NOT enable auto-execute
- Do NOT enable followups
- Do NOT skip Stage 1 observation (30 min active + 24h passive)
- Do NOT enable orchestrator-driven replies until Stage 2+ testing
- Do NOT add photo/voice without proper cost estimation (GPT-4V/Whisper API costs)

### Current AI Button Verdict
**PRODUCTION-READY for observation mode.** The AI button provides genuine value to users (pricing, catalog, objection handling) without any automated sends. All safety gates verified. Missing features (photo, voice, analytics) are enhancements, not blockers.
