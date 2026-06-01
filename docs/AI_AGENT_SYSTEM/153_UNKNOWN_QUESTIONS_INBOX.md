# 153 — Unknown Questions Inbox

> **Status banner**
>
> - Deploy: NO
> - VPS: NO
> - Flags: NOT ENABLED
> - Live sender: NOT ENABLED
> - Operator reply live send: NOT ENABLED
> - DB / migrations: **one additive migration added (not applied to any server)**
> - Production token: NOT USED · Real OpenAI: NOT CALLED · Telegram send: NONE
>
> This is the **first safe feedback loop** for improving the agent after deployment.
> It is **read-only** on the customer side: it captures and displays, it never sends,
> never auto-replies, and never edits knowledge / prices / catalog.

Recommended as the next sprint by the web-platform audit
([152_WEB_PLATFORM_AGENT_CONTROL_AUDIT.md](152_WEB_PLATFORM_AGENT_CONTROL_AUDIT.md)),
whose verdict was: *the biggest missing piece is that there is no feedback loop —
the agent cannot be measured or improved from the web.* This sprint builds the
**capture + visibility** half of that loop.

---

## 1. Why this exists

Before this sprint, when the bot failed a customer — an OpenAI error, a generic
failsafe reply, a safety block — the event was **lost to logs**. Nobody could:

- see which questions the bot could not answer well,
- see how often failures happen,
- decide which gaps deserve a new FAQ / knowledge entry later.

The Unknown Questions Inbox captures those moments into a queryable table and
shows them in a read-only admin page, so the business can finally *see where the
agent is losing customers*. It is the diagnostic layer that makes the **next**
sprint (Knowledge Base CRUD) targeted instead of guesswork.

---

## 2. What it captures

A row is captured when the bot likely failed or was uncertain. Capture **reasons**:

| Reason | Captured when |
|--------|---------------|
| `openai_error` | The OpenAI call raised, or returned an empty reply → failsafe text was shown. |
| `ai_fallback` | The message reached the LLM fallback branch (no deterministic route). |
| `generic_reply` | A generic "not enough info" reply was used. |
| `safety_block` | The pre-LLM deterministic safety gate refused the message. |
| `low_confidence` | A decision/answer was below the confidence threshold. |
| `no_catalog_match` | A catalog request could not be resolved to a design. |
| `unknown_design` | A design term was not recognised. |
| `unknown_price_question` | A price question could not be answered concretely. |
| `shadow_live_mismatch` | (future) SDM shadow route disagreed with the live route. |
| `operator_needed` | The conversation needs a human operator. |
| `manual_flag` | An admin flagged a message manually. |

**Wired in v1 (minimal, safest points only):**

- `openai_error` — both OpenAI-error `except` blocks in `ai_support.py`
  (`handle_ai_question` and `handle_ai_message`).
- `safety_block` — the pre-LLM `_maybe_block_stop_or_safety` refusal path.

**Added in v2 (see [155_UNKNOWN_QUESTIONS_CAPTURE_V2.md](155_UNKNOWN_QUESTIONS_CAPTURE_V2.md)):**

- `no_catalog_match` — a catalog/design ask that resolved to nothing specific
  (resolver `reason == "no_alias"`); generic catalog asks and ambiguous
  confirmations are excluded.
- `unknown_price_question` — a substantive (≥ 4-word) price question with no
  parseable area / design / district; short bare asks ("narx qancha") are not
  captured.

**Still deferred:** `generic_reply` (the only deterministic generic reply is for
confirmation words like "rahmat"/"ok", which are not failures), `unknown_design`
(near-misses are handled via confirmation prompts; folded into `no_catalog_match`
for now), `low_confidence` and `shadow_live_mismatch` (SDM is shadow-only / OFF —
needs a shadow→DB sprint). All remain supported by the model/service/API/UI.

**Not captured** (by design): normal price / catalog / measurement / operator
successes, and stop / "kerakmas" messages (those are honoured by the stop guard,
not treated as failures). Phone-number-only messages reduce to an empty preview
and are skipped.

---

## 3. Privacy rules (enforced in code, covered by tests)

`core/services/unknown_question_service.py::sanitize_unknown_question_text`:

1. **Phones masked** — `mask_phone_in_text` (`+998901234567` → `+998****67`),
   including spaced / local 9-digit forms.
2. **Secrets redacted before masking** — `sk-…` keys, Telegram bot tokens
   (`<digits>:<token>`), `Bearer …`, and `key=value` secrets (`api_key`, `token`,
   `secret`, `password`, `database_url`) → `[redacted]`. Redaction runs **before**
   phone masking so the phone regex cannot nibble a token's leading digits and
   leave its body behind (regression-tested).
3. **URLs stripped** — `https://…` / `www.…` → `[link]` (no t.me invite links).
4. **Bounded** — whitespace collapsed, truncated to **300 chars**.
5. **No raw text stored** — only the sanitized preview. The full message is never
   persisted; a SHA-256 **hash** of the normalized text is stored for dedupe.
6. **Chat id hashed** — only `telegram_chat_id_hash` (SHA-256) is stored, never the
   raw chat id.

Never persisted: raw messages, phone numbers, `BOT_TOKEN`, OpenAI keys,
`DATABASE_URL`, `Bearer` tokens, `sk-` keys, URLs.

---

## 4. Data model

Table `agent_unknown_questions` (migration `p2q3r4s5t6u7`, on top of head
`4869f6eb9fbb`; ORM `infrastructure/database/models/agent_unknown_question.py`).

| Column | Type | Notes |
|--------|------|-------|
| `id` | BigInteger Identity PK | Matches repo convention (see note below). |
| `created_at` / `updated_at` | TIMESTAMP(tz) | `created_at` server-default now. |
| `source` | String(20) | telegram / web / simulation / manual. |
| `channel_user_id` | BigInteger? | Telegram user id (operator can match in CRM). |
| `crm_contact_id` | BigInteger? | Link to CRM contact when known. |
| `telegram_chat_id_hash` | String(64)? | SHA-256, never the raw id. |
| `original_text_preview` | Text | Sanitized, ≤300 chars. |
| `original_text_hash` | String(64) | SHA-256 of normalized text (dedupe). |
| `bot_reply_preview` | Text? | Sanitized intended/actual reply. |
| `reason` | String(40) | See §2. |
| `intent` / `live_route` | String(40)? | Live routing context. |
| `sdm_intent` / `sdm_next_action` | String(40)? | Shadow/SDM context (future). |
| `order_readiness_score` | Integer? | Buyer readiness 0–100. |
| `severity` | String(10) | low / medium / high / critical. |
| `status` | String(20) | new / reviewed / ignored / converted_to_faq / needs_operator. |
| `admin_note` | Text? | Triage note. |
| `reviewed_at` / `reviewed_by` | TIMESTAMP / String(50) | Set on review. |
| `metadata_json` | JSON? | Extensible. |

Indexes: `created_at`, `status`, `reason`, `severity`, `original_text_hash`,
`crm_contact_id`, and a composite `(original_text_hash, channel_user_id, reason,
created_at)` to support future DB-level dedupe.

**Convention note — PK type.** The sprint spec suggested a UUID primary key. Every
existing table in this repo uses `BigInteger` + `Identity()`, and there is no UUID
precedent, so this table follows the house convention for consistency and lower
migration risk. The API path `/{question_id}` works identically either way.

**Enum storage.** Reasons / severities / statuses are stored as `String` with
server defaults (mirroring `crm_operator_handoff_requests`), not PG enum types —
this avoids fragile `ALTER TYPE` migrations and keeps the vocabulary in one place
(`unknown_question_service.py`).

**Dedupe.** A pure decision (`maybe_record_unknown_question`) decides whether to
capture. True DB-level dedupe (same hash + user + reason within 24h) is **not yet**
implemented — documented as the next step (§9). The composite index is already in
place to make it cheap.

---

## 5. Capture service

`core/services/unknown_question_service.py` — pure-first, framework-light:

- `sanitize_unknown_question_text(text)` — privacy preview (§3).
- `hash_question_text(text)` / `hash_chat_id(id)` — stable SHA-256 digests.
- `classify_unknown_question_reason(**signals)` — pick the single most-informative
  reason from active signals (priority-ordered), or `None`.
- `severity_for_unknown_question(reason, order_readiness_score=)` — per-reason
  severity, bumped one tier for hot/ready buyers (readiness ≥ 70).
- `build_unknown_question_event(...)` — sanitized, ready-to-insert dict; coerces
  bad source/reason/severity into the known vocabularies.
- `maybe_record_unknown_question(...)` — pure orchestrator: returns the event dict
  or `None` (skip) — the single decision point shared by bot wiring and tests.
- `capture_unknown_question(...)` — async DB write. **Never raises**: all DB work
  is wrapped; on failure it logs a warning and returns `False`. Fired from the bot
  via `asyncio.create_task` through the `_schedule_unknown_capture` helper.

---

## 6. API (read-mostly, admin-only)

`apps/api/routes/admin_agent_unknown_questions.py`, all behind `require_api_token`:

- `GET /api/v1/admin/agent/unknown-questions` — list with filters `status`,
  `reason`, `severity`, `q` (preview search), `limit` (≤100), `offset`.
- `GET /api/v1/admin/agent/unknown-questions/summary` — `total_new`,
  `high_severity`, `today_count`, `top_reasons`, `top_reason`. `bot_failure_rate`
  is a deliberate `None` placeholder (an exact rate needs a reliable denominator —
  handled-conversation count in the window — which this table does not hold; the
  note field says so explicitly rather than showing a misleading number).
- `POST /api/v1/admin/agent/unknown-questions/{id}/review` — triage only: set
  `status` (validated) + optional `admin_note`; stamps `reviewed_at` / `reviewed_by`.

No send, no FAQ creation, no content mutation, no model/Telegram call.

---

## 7. Web UI (read-only triage)

`apps/web/templates/agent_unknown_questions.html`, route `/agent/unknown-questions`
in `apps/web/main.py`, nav link under the **AI** section in `base.html`.

- Read-only banner stating it never sends / edits content.
- KPI cards: New, High-severity, Today, Top reason; plus a reasons breakdown.
- Filters: status, reason, severity, free-text search; refresh.
- Table: created_at, sanitized preview, reason, severity badge, status,
  intent/live_route/SDM action, contact link (when known), and a **Review** button.
- Review modal: set status (reviewed / needs_operator / ignored / converted_to_faq)
  + note, POSTed to the review API (same pattern as the handoff queue).
- Empty state + mobile-responsive.

---

## 8. What this sprint does NOT do (yet)

- **No knowledge editing.** It does not create or edit FAQ / knowledge / prompts.
- **No price or catalog editing.**
- **No send-from-web.** No customer messaging, no auto-reply.
- **No live behaviour change.** The only production-path touch is two
  `asyncio.create_task` capture calls, wrapped so they can never break a reply.
- **No flags enabled.** Capture is always-on but purely additive and safe.
- **No DB-level dedupe** yet (pure decision only; index is ready).
- `bot_failure_rate` is a placeholder, not a real rate.

---

## 9. Safety & rollout

- **Cannot break the bot.** `capture_unknown_question` and `_schedule_unknown_capture`
  both swallow all errors; a capture problem only logs a warning.
- **Privacy by construction** (§3), covered by service + bot tests asserting no raw
  phone / token / chat-id survives persistence.
- **Migration is additive** (new table only) and has a clean `downgrade()`. It has
  **not** been applied to any server in this sprint.
- **Rollout:** apply the migration during the next normal deploy; capture begins
  immediately (no flag). The inbox is read-only, so there is nothing dangerous to
  enable. Rollback = `alembic downgrade -1` (drops the table); the bot keeps working
  because capture failures are non-fatal.

**Follow-up PRs (in order):**

1. Wire remaining reasons (`generic_reply`, `no_catalog_match`, `unknown_design`,
   `low_confidence`) at their detectors.
2. DB-level dedupe (same hash + user + reason within 24h) using the composite index.
3. Persist SDM shadow decisions → enable `shadow_live_mismatch` capture + parity view.
4. A real `bot_failure_rate` once a handled-conversation denominator exists.

> **Update:** the promote-to-FAQ loop opened here is now implemented — see
> [156_KNOWLEDGE_BASE_CRUD.md](156_KNOWLEDGE_BASE_CRUD.md). Promoting a question
> creates a knowledge item and sets the question's status to `converted_to_faq`.

## 10. Next sprint: Knowledge Base CRUD

With the inbox showing *what* the bot fails on, the next sprint makes knowledge
**editable from the web** (DB-backed knowledge + loader + CRUD + versioning +
approval + rollback), and adds a **promote-unknown-question → FAQ** action that
closes the loop opened here. See doc 152 §5 (Agent upgrade system roadmap).

---

## 11. Files in this sprint

- `infrastructure/database/migrations/versions/20260601_0000_p2q3r4s5t6u7_add_agent_unknown_questions.py`
- `infrastructure/database/models/agent_unknown_question.py`
- `infrastructure/database/migrations/env.py` (model import for autogenerate)
- `core/services/unknown_question_service.py`
- `apps/api/routes/admin_agent_unknown_questions.py` + registration in `apps/api/main.py`
- `apps/web/main.py` (route) + `apps/web/templates/agent_unknown_questions.html`
  + `apps/web/templates/base.html` (nav + title)
- `apps/bot/handlers/private/ai_support.py` (import + `_schedule_unknown_capture` + 3 capture calls)
- Tests: `tests/unit/services/test_unknown_question_service.py`,
  `tests/unit/api/test_agent_unknown_questions_api.py`,
  `tests/unit/web/test_agent_unknown_questions_page.py`,
  `tests/unit/bot/test_unknown_question_capture.py`
