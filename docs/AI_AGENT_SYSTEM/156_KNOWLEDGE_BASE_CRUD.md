# 156 — Knowledge Base CRUD + Promote Unknown Question to FAQ

> **Status banner**
>
> - Deploy: NO · VPS: NO · Push: pending approval
> - DB / migrations: **one additive migration** (`q3r4s5t6u7v8`), not applied to any server by this sprint
> - Flags: none added · Production token: NOT USED · Real OpenAI: NOT CALLED · No Telegram send
> - **Bot behaviour unchanged** — the bot does NOT read these items yet (Option A). No reply text / routing change.

The web audit (doc 152) named "post-deploy knowledge upgrade" the biggest missing
piece. This sprint delivers the first **admin-editable knowledge layer** and wires
it to the Unknown Questions Inbox via a safe **Promote to FAQ** workflow.

## 1. Purpose

Let the business manage FAQ-style knowledge after deployment, and turn captured
failures into knowledge:

1. open `/agent/unknown-questions` → pick a question → **Promote to FAQ**
2. write/edit the answer → **save as draft or active**
3. manage all items at `/agent/knowledge` (create / edit / archive / filter)

The bot reading this knowledge is **the next sprint** — this one is the storage,
CRUD, and promotion foundation only.

## 2. DB model — `agent_knowledge_items`

Migration `q3r4s5t6u7v8` (down_revision `p2q3r4s5t6u7`); ORM
`infrastructure/database/models/agent_knowledge_item.py`. BigInteger Identity PK,
String enums (no PG enum types). Key columns:

| Column | Notes |
|--------|-------|
| `title` / `question` / `answer` | Text. `active` items require question + answer. |
| `category` | faq / price / catalog / warranty / objection / service_area / process / other |
| `language` | uz (default) / ru / en |
| `status` | draft / active / archived |
| `source` | manual / unknown_question / import |
| `source_unknown_question_id` | link back to `agent_unknown_questions.id` when promoted |
| `aliases_json` / `tags_json` | optional lists |
| `priority` | int (default 100; lower sorts first) |
| `created_by` / `updated_by` / `approved_by` / `approved_at` | audit-friendly metadata |
| `created_at` / `updated_at` / `metadata_json` | timestamps + extensible blob |

Indexes: status, category, language, source_unknown_question_id, created_at,
priority, and a composite (status, category, language). Additive; clean `downgrade()`.

## 3. Service — `core/services/agent_knowledge_service.py`

Pure-first, secret-safe:

- `sanitize_knowledge_text` — mask phones, normalize whitespace, truncate.
- `contains_forbidden_secret` / `_reject_secrets` — detect & **block** bot tokens,
  `sk-` keys, `Bearer`, `DATABASE_URL`/`postgres://`, `key=value` secrets.
  Checked on **raw** text first (sanitization can mangle a token's digits).
- `validate_knowledge_item` — vocab + length limits; `active` requires question +
  answer; `draft` may be incomplete.
- `build_knowledge_payload` — coerce vocab, sanitize, validate, stamp `created_by`.
- `create_knowledge_item` / `update_knowledge_item` / `archive_knowledge_item` /
  `list_knowledge_items` / `get_knowledge_item` — async DB ops; activating stamps
  `approved_by`/`approved_at`.
- `promote_unknown_question_to_faq` — in one session: create a knowledge item
  (source=unknown_question, linked id), pre-fill the question from the captured
  preview when not supplied, then set the unknown question
  `status = converted_to_faq`. Raises `LookupError` if the question is missing,
  `KnowledgeValidationError` on invalid/secret content.

Length limits: title 200, question 1000, answer 4000.

## 4. API (admin-only, `require_api_token`)

- `GET    /api/v1/admin/agent/knowledge` — filters: status, category, language, q, limit≤100, offset
- `GET    /api/v1/admin/agent/knowledge/summary` — active/draft/archived counts + categories
- `GET    /api/v1/admin/agent/knowledge/{id}`
- `POST   /api/v1/admin/agent/knowledge` — create (422 on validation/secret error)
- `PATCH  /api/v1/admin/agent/knowledge/{id}` — update (422 / 404)
- `POST   /api/v1/admin/agent/knowledge/{id}/archive`
- `POST   /api/v1/admin/agent/unknown-questions/{id}/promote-to-faq` — body: title,
  question, answer, category (default faq), status (default draft), aliases, tags

No send, no model call, no public access, no bot behaviour change.

## 5. Web UI

- **`/agent/knowledge`** — KPI cards (active/draft/archived/categories), filters
  (status/category/language/search), table (title, question, category, status,
  source, updated_at), create/edit modal (title, question, answer, category,
  status, aliases, tags), archive action, empty state, nav link under **AI**.
- **`/agent/unknown-questions`** — a **Promote to FAQ** button on rows with status
  `new`/`reviewed`, opening a modal pre-filled with the captured question; admin
  writes the answer and saves (draft by default). After promotion the row becomes
  `converted_to_faq`. No send button, no auto-reply.

## 6. Promote-to-FAQ workflow (end to end)

```
Unknown Questions Inbox row (new/reviewed)
   │  click "FAQ ga o'tkazish"
   ▼
Promote modal (question prefilled) → write answer → Save (draft|active)
   │  POST .../{id}/promote-to-faq
   ▼
agent_knowledge_items row created (source=unknown_question, linked id)
   +  unknown question status → converted_to_faq
   ▼
Manage later at /agent/knowledge (edit / activate / archive)
```

## 7. Safety / what does NOT happen yet

- **Bot does not read DB knowledge** (Option A). Proven by tests: no
  knowledge-service import / model query / lookup flag in the live handlers, and
  the file-based KB load (`apps/bot/ai/system_prompt.py`) is unchanged.
- No flag added (no `AGENT_KNOWLEDGE_DB_LOOKUP_ENABLED` this sprint).
- No web send, no auto-reply, no system-prompt / KB-markdown mutation.
- Secrets are blocked at save (422), not silently stored. Phones masked.
- Migration is additive and not applied to any server here.

## 8. Tests

- `tests/unit/services/test_agent_knowledge_service.py` — 85 (validation, secret
  rejection for all types, sanitize, build_payload coercion, create/update/archive/
  list/get, promote + converted_to_faq, length limits, draft vs active).
- `tests/unit/api/test_agent_knowledge_api.py` — endpoints, filters, auth, 422/404
  mapping, promote, no send/model/public surface.
- `tests/unit/web/test_agent_knowledge_page.py` — page/nav/KPIs/filters/modal/
  archive + promote button & modal on unknown-questions; no send/auto-reply.
- `tests/unit/bot/test_knowledge_bot_unchanged.py` — bot behaviour unchanged pins.

## 9. Next sprint

1. **Bot Knowledge Retrieval from DB** (gated): `AGENT_KNOWLEDGE_DB_LOOKUP_ENABLED`
   default OFF; when ON, search **active** FAQ items (exact/keyword) before the
   OpenAI fallback. Tests must pin default OFF + no behaviour change.
2. **Knowledge versioning + approval workflow** (draft → review → live, rollback).
3. **Price Settings UI** and **Catalog Link / Alias Manager** (the other two
   post-deploy gaps from doc 152).
4. Consolidate the divergent `apps/bot/ai/knowledge/uz.md` vs `shared/knowledge/uz.md`.

## 10. Files

- `infrastructure/database/migrations/versions/20260602_0000_q3r4s5t6u7v8_add_agent_knowledge_items.py`
- `infrastructure/database/models/agent_knowledge_item.py` (+ `migrations/env.py` import)
- `core/services/agent_knowledge_service.py`
- `apps/api/routes/admin_agent_knowledge.py` (+ registration in `apps/api/main.py`)
- `apps/api/routes/admin_agent_unknown_questions.py` (promote endpoint)
- `apps/web/main.py` (route) + `apps/web/templates/agent_knowledge.html`
  + `apps/web/templates/agent_unknown_questions.html` (promote UI)
  + `apps/web/templates/base.html` (nav + title)
- Tests as listed in §8; this doc + pointers added to docs 153 and 155.
