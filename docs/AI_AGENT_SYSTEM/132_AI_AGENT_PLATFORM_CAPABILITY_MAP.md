> Status: AUDIT REPORT. Deploy: NO. VPS: NO. Flags: NOT ENABLED. Stage 1: NOT APPLIED.
> Live sender: NOT ENABLED. Campaign send: NOT ENABLED. Operator reply live send: NOT ENABLED.

# 132 — AI Agent Platform Capability Map

A precise answer to: *what can the agent see, decide, do, not do, and how do we safely let it
act inside the platform?* This doc is the contract between the agent system and the rest of the
codebase. Every level it describes is reachable today by flipping flags — but only the levels
listed under "current default" are active right now.

---

## 1. What the agent can see (inputs)

| Input | Where | Shape | Notes |
|---|---|---|---|
| Raw user text | aiogram update | str | Sanitized by `shared/utils/sanitize.sanitize_user_text_for_prompt` (max 300 chars). |
| FSM state | aiogram FSMContext | `StatesGroup.state` | Per-user, per-chat. |
| `AgentMemoryModel` | DB | row | area, district, phone_masked, interested_designs (≤10), lead_temperature, followup_count, stop_reason, estimated_price, last_event_*. |
| `AiConversationModel` | DB | row | last 8–12 messages, summary regenerated every 10 turns. |
| `AiMemoryModel` | Redis + DB | dict | last_intent, last_dimensions, location, turn_count. |
| Lead row | DB via `LeadService` | row | name, phone (raw — server-side only), district, score, lead_status, next_follow_up_at. |
| Deterministic signals | `core/services/lead_signal_service.py` | `LeadSignalResult` | intent, objection_type, urgency, area_m2, budget_amount, lead_score_delta, confidence_score. |
| Journey events | `core/services/journey_event_service.py` | list | order_form_started, price_calculated, phone_shared, operator_requested, package_viewed. |
| Deal probability | `shared/utils/deal_probability.py` | `DealProbability` | 0–100, expected deal value, recommended action, top reasons. |
| Buyer type | `core/services/lead_intelligence_service.py` | `BuyerProfile` | price_sensitive / quality_buyer / fast_buyer / research_buyer + confidence. |
| Revenue estimate | `core/services/revenue_predictor_service.py` | `RevenueEstimate` | min/max/best, addons, upsell tier. |
| Negotiation context | `core/services/negotiation_engine_service.py` | `NegotiationResult` | tactic + rationale. |
| Knowledge base | `shared/knowledge/uz.md` | embedded in prompt | Product facts; loaded once at import. |
| Closer suggestions | `apps/bot/handlers/private/sales_closer.py` | helper dataclass | When to attempt close + which closing message. |

What the agent **cannot** see today:

- CRM contact notes / tags (operator-only).
- Other users' data (correct, by design).
- Handoff queue state (`crm_operator_handoff_requests`).
- Operator workload / who's online.
- Web audit logs / login attempts.
- Past campaign sends per user.
- Order history (`my_orders` view).
- Payment statuses.
- Raw phone number (the agent only sees the masked form — by policy).

---

## 2. What the agent can decide (outputs)

| Decision | Producer | Possible values |
|---|---|---|
| `customer_state` | `agent_decision_engine.py` | new_visitor, browsing_catalog, price_checking, order_intent, phone_shared_hot, inactive_warm, inactive_cold, stopped, lost, closed, negotiating_price, operator_handoff (15 in total). |
| `action_type` | `agent_decision_engine.py` | wait, send_catalog_followup, suggest_price_calculator, request_area, send_price_followup, request_phone, send_order_followup, mark_hot_lead, disable_followup, escalate_to_admin, notify_admin (11). |
| `priority_score` | same | 0–100 |
| `confidence_score` | same | 0–100 |
| `lead_temperature` | `lead_signal_service` + LLM | hot / warm / cold |
| `policy_action` | `conversation_policy_service.py` | disable_agent, no_action, handoff_operator, escalate_admin, cancel_followups, store_only, reply_now, schedule_followup, wait_and_observe. |
| `channel` | same | none, internal_only, user_dm, admin_group |
| `risk_level` | same | none, low, medium, high |
| `orchestrator action` | `agent_response_orchestrator.py` | SEND_USER_REPLY, STORE_MEMORY_ONLY, SCHEDULE_FOLLOWUP, DISABLE_AGENT, HANDOFF_OPERATOR, SEND_ADMIN_ALERT, NO_ACTION, CANCEL_FOLLOWUPS. |
| `intent` (LLM) | `apps/bot/handlers/private/ai_openai.py` | greeting, price, catalog, operator, measurement, faq, objection, other. |
| `closing_confidence` (LLM) | same | 0.0–1.0 |

Output sanitization happens in `core/services/ai_message_composer_service.py` and
`shared/utils/sanitize.sanitize_ai_reply` (16 forbidden markers, no token leak, no PII leak,
no fake guarantee, max 500 chars).

---

## 3. What the agent can do (actions)

Action surface lives in `core/services/agent_execution_sandbox_service.py` +
`core/services/agent_execution_queue_service.py` + `core/services/approved_execution_sender_service.py`.

Sendable actions (today, when fully enabled):

- `send_user_reply` → `bot.send_message(chat_id=user_id, ...)`.
- `send_admin_alert` → `bot.send_message(chat_id=admin_group_id, ...)`.
- `handoff_operator` → user-facing DM + operator-side handoff record.

Non-sendable actions:

- `store_memory_only` → persist to memory.
- `schedule_followup` → schedule a delayed task in Celery / APScheduler.
- `cancel_followups` → mark pending follow-ups disabled.
- `disable_agent` → set `followup_enabled=false`, `stop_reason=<X>`.
- `no_action` → trace only.

Every sendable action passes through:

1. Sandbox validation (`agent_execution_sandbox_service.should_block`) — 11+ safety gates.
2. Queue persistence (`agent_execution_queue_service.create_record`) → DB row, status `PROPOSED`.
3. Admin approval (callback UI in `apps/bot/handlers/callbacks/agent_execution_callbacks.py` or
   API in `apps/api/routes/admin_agent_observation.py`).
4. Revalidation at send time (`approved_execution_sender_service._validate_send`).
5. `bot.send_message` only on `status == APPROVED` and `safe_to_execute == True`.
6. Result written back to DB (`mark_executed` / `mark_failed`).

---

## 4. What the agent cannot do (today, by design)

- Send a message without sandbox validation.
- Send a message without admin approval (when `AGENT_EXECUTION_AUTO_EXECUTE_APPROVED=false`).
- Promise a fixed time ("bugun qilamiz" / today we'll do it) — blocked by output validator.
- Promise an exact price ("aniq narx") — blocked.
- Send a forbidden marker ("eng arzon", "100% kafolat", "yoshirin to'lov yo'q") — blocked.
- Send raw phone, token, or system-prompt content — blocked.
- Send more than `AGENT_EXECUTION_MAX_DAILY_ACTIONS_PER_USER` (default 3) per user per day.
- Send more than `agent_followups_lifetime_cap` (default 5) follow-ups per user, ever.
- Reply when `followup_enabled=false` or `stop_reason` is set.
- Escalate cold leads (correct, by policy).
- Send during admin escalation cooldown (default 60 min).
- Skip the sandbox (no code path bypasses `AgentExecutionSandboxService`).

---

## 5. Blind spots (what the agent does not know)

| Blind spot | Why it matters | Suggested fix |
|---|---|---|
| Handoff queue state | Cannot say "you're #3 in queue". | Read `crm_operator_handoff_requests` summary; pass into prompt as one line. |
| Operator online status | Cannot delay messages when no operator is available. | Add `OperatorPresenceService`; pass a single boolean. |
| Past campaign sends to this user | Cannot avoid duplicate messaging. | Pass `last_campaign_at` from `crm_campaign_send_attempts`. |
| CRM notes / tags | Operator context is invisible. | Add a `read_only_context` payload to memory; include latest 3 notes by length cap. |
| Order/payment history | Cannot mention prior orders. | Pass a 1-line digest (`prior_orders=2, last=2026-04`). |
| Audit log | Cannot understand "this user already reported you to admin". | Pass an escalation summary flag. |
| Web admin viewing this contact right now | Could prevent crossed conversations. | Add a Redis presence key updated by the web detail page. |

---

## 6. Levels 0–5: action maturity

A pragmatic ladder from "answers only" to "autonomous live actions". Each level adds *one* layer
of capability. The platform is wired for all 6; the default is Level 0–1.

### Level 0 — Answers only (default ON; LOG_ONLY)

- The agent reads, classifies, scores, stores memory and traces.
- It produces a *proposed* `orchestrator action`.
- It does **not** send anything.
- Configuration: `AGENT_RESPONSE_ORCHESTRATOR_LOG_ONLY=true`, `AGENT_EXECUTION_MODE=log_only`.

Missing pieces: none. This level is fully usable today.

Safety gates: every send path is short-circuited; only memory + trace writes happen.

Risk: very low. The only way to leak something at this level is if a trace embeds an unsanitized
user string — `sanitize.py` blocks that.

Readiness: ✅ READY.

### Level 1 — Read CRM/contact context (default ON; LOG_ONLY)

- Adds: read of `AgentMemoryModel`, journey events, deterministic signals, deal probability,
  buyer type, revenue estimate.
- Still does not send.

Missing pieces: none.

Risk: low — pure reads with masked phone.

Readiness: ✅ READY.

### Level 2 — Propose actions (default ON; LOG_ONLY)

- Adds: `agent_execution_queue_service.create_record` with status `PROPOSED`.
- Each proposal is visible on `/agent` web page (when `AGENT_EXECUTION_API_APPROVAL_ENABLED=true`)
  and in the admin Telegram group (when `AGENT_EXECUTION_APPROVAL_ADMIN_NOTIFY=true`).
- Still does not send.

Missing pieces:
- Admin UI: today uses browser `confirm()`. Replace with a typed-modal showing the actual
  message.
- A "propose-only mode" toggle on the agent page.

Safety gates: sandbox validation runs before insertion; no row reaches DB without passing
`should_block`.

Risk: low (proposals never leak to the user).

Readiness: ✅ READY (UI polish wanted).

### Level 3 — Write internal CRM records (NOT YET ENABLED)

- Adds: agent can create/update CRM tasks, notes, tags, scoring rows.
- Audit log every mutation (`agent_id, action, before, after, reason`).
- No user-facing side effects.

Missing pieces:
- A `CRMAgentMutationService` that wraps existing CRM repos with a write audit log.
- A dedicated `agent_mutations` table.
- An admin filter in the web CRM to surface "the last 50 things the agent did".
- A "revert" affordance on each mutation.

Safety gates needed: must not mutate user-facing fields (lead_status, lead_temperature) without
admin approval at the start.

Risk: medium — bad mutations are harder to see than bad messages.

Readiness: ⚠ NOT READY — design + 2 migrations away.

### Level 4 — Send messages with approval (NOT YET ENABLED)

- Adds: live `approved_execution_sender_service` actually calls `bot.send_message`.
- Requires `AGENT_EXECUTION_LIVE_SENDER_ENABLED=true` AND `AGENT_SETTINGS_ALLOW_LIVE_FLAGS=true`.
- Auto-execute remains OFF; every send is preceded by admin tap (or API approve call).

Missing pieces:
- Admin UI modal that shows the exact text + the safety verdict.
- Per-send audit log row (separate from the queue row) so analytics can see real sends.
- Per-user-per-day counter exposed on `/admin/security`.
- One-button kill switch (`agent_response_orchestrator_enabled=false`) wired to a Slack/Telegram
  command.

Safety gates needed: ensure `revalidate=true` always wins over operator hurry.

Risk: medium-high — the first time the agent sends a real message to a real customer.

Readiness: ⚠ NOT READY — gating UI polish + one full Stage 1 observation pass away.

### Level 5 — Autonomous live actions (NOT YET ENABLED)

- Adds: `AGENT_EXECUTION_AUTO_EXECUTE_APPROVED=true` — proposals auto-mark as approved if
  confidence ≥ threshold AND risk ≤ low AND last 100 sends were clean.
- This is the danger zone.

Missing pieces:
- A 24-hour rolling "agent reputation" score.
- A circuit breaker that drops back to Level 4 on any safety-flag spike.
- An owner-only "burst limit" override.
- Real-time monitoring of agent sends visible to the owner.

Safety gates needed: dual sign-off in settings; no Level-5 toggle without the owner's session.

Risk: high.

Readiness: ❌ NOT READY — needs Levels 3 and 4 production-proven first, plus monitoring.

---

## 7. How to safely let the agent act inside the platform

A practical sequence (do not skip steps):

1. **Stage 0 (today, default)**: Level 0 + Level 1. LOG_ONLY everywhere. Observe traces.
2. **Stage 1**: enable `AGENT_DECISION_ENGINE_ENABLED=true` with
   `AGENT_DECISION_LOG_ONLY=true`. Observe for ≥30 minutes; record decision rate and
   safety-flag distribution.
3. **Stage 2**: enable Level 2 (`AGENT_EXECUTION_QUEUE_ENABLED=true`,
   `AGENT_EXECUTION_API_APPROVAL_ENABLED=true`). Proposals appear on the agent page. No sends.
4. **Stage 3**: enable Level 3 (CRM writes) with a strict per-action allowlist. Audit every row.
5. **Stage 4**: enable Level 4 (`AGENT_EXECUTION_LIVE_SENDER_ENABLED=true` +
   `AGENT_SETTINGS_ALLOW_LIVE_FLAGS=true`). Manual approval only. Start with 1 canary user.
6. **Stage 5**: enable `AGENT_EXECUTION_AUTO_EXECUTE_APPROVED=true` only when the prior 30 days
   show zero safety-flag spikes and a positive operator NPS.

Each stage corresponds to one of the `stage1_observation_report_service.py` …
`stage5_live_send_readiness_service.py` files already in the codebase. Use them to gate
transitions, not to summarize results.

---

## 8. Next 20 agent upgrades

1. Add `handoff_queue_size`, `operator_online`, `prior_orders` to memory context.
2. Add per-decision audit log row exposed on `/agent` page.
3. Replace web `confirm()` for approve/reject with typed-modal showing the message.
4. Add `agent_mutations` table + service for Level 3.
5. Add a 24h rolling "agent reputation" score.
6. Add a circuit breaker that drops modes on safety-flag spikes.
7. Add a "kill switch" Telegram command (admin only).
8. Add a structured-output validation step that asserts every LLM reply parses to a schema.
9. Add a redaction unit test that fuzzes prompt-injection patterns into the inputs.
10. Add a per-user-per-day send counter on `/admin/security`.
11. Add an explicit "why this decision" trace on the contact-detail page.
12. Add owner-only "burst override" with a forced reason field.
13. Move every CRM tag/note write into a single auditable mutation service.
14. Add a regression test asserting `DEFAULT_BASE_PRICES` is never referenced by any
    apps/bot/handlers/private/*.py file.
15. Add a unit test asserting `sanitize_ai_reply` rejects every known forbidden marker.
16. Add a memory-TTL job that prunes `AiMemoryModel` rows older than 60 days.
17. Add a `last_seen_admin_user_id` field on contact to detect operator-vs-agent crossfire.
18. Add a "shadow mode" where Level 4 runs but writes to a parallel `shadow_sends` table
    instead of Telegram — for backtesting.
19. Add an in-app dashboard tile counting executions by mode in the last 24h.
20. Add a doc per agent mutation type (what, why, who can approve).

---

## 9. Where the agent could act inside the platform (today, fully scoped)

Every place the agent could mutate state, as of this audit:

| Path | What | Gate |
|---|---|---|
| `AgentMemoryModel.update_*` | always | none — internal only |
| `AgentMemoryModel.update_lead_temperature` | always | none |
| `AiConversationModel.last_messages.append` | always | none |
| `AiConversationModel.summary` | every 10 turns | LLM call gated by `agent_ai_composer_enabled` |
| `AgentExecutionRecordModel.create_record` | when orchestrator runs | sandbox gate |
| `AgentExecutionRecordModel.mark_executed` | sender job | revalidation gate |
| `LeadModel.update_ai_scoring` | on AI exchange + measurement | none (internal) |
| `LeadModel.update_lead_status` | admin status callback only | admin RBAC |
| `LeadModel.update_last_action` | various | none (internal) |
| `crm_operator_handoff_requests` | service path only | dedup + RBAC |
| Telegram `send_message` | sender job only | sandbox + queue + revalidation + flag |

Nothing else (orders, payments, prices, packages) is written by the agent today.

---

## 10. Agent capability score

| Sub-axis | Score |
|---|---|
| Inputs available | 8.0/10 |
| Decisions produced | 8.0/10 |
| Actions wired | 8.0/10 |
| Default safety | 9.0/10 |
| Action surface UX | 6.0/10 |
| Audit/observability | 6.5/10 |
| Live-send readiness | 5.0/10 |
| **Agent-inside-platform** | **7.4/10** |

The agent is *smart*. The biggest gap is not intelligence — it is the operator UI for
"approve this proposal" and the audit trail for "what did the agent do today." Close those, and
Level 4 is reachable.
