# 158 — CRM Conversation Inbox + Operator Send-from-Web

> **Status banner**
>
> - Deploy: NO · VPS: NO · Push: pending approval
> - DB / migrations: **none** (reuses `crm_contacts`, `crm_messages`, `crm_operator_outbound_audit`)
> - Send flag: `OPERATOR_WEB_SEND_ENABLED` — **default FALSE** → API rejects send (403), composer disabled, no Telegram send
> - No bulk · no group · no campaign · no AI/auto-send · one message to one known contact
> - Production token: NOT USED · Real OpenAI: NOT CALLED · No real Telegram send in tests

## 1. Purpose

Let an admin/operator open the web platform, **see the client↔bot conversation**,
and **reply to the client from inside the platform** — safely, gated, and audited.

## 2. What's included

- **Conversation Inbox** at `/crm/inbox`: left = conversation list (latest preview,
  temperature, status, search); right = message timeline (client / bot / operator)
  + a contact info bar; a link from the contact-detail page.
- **Operator Send-from-Web**: a composer that delivers ONE manual reply to the
  client via Telegram — only when `OPERATOR_WEB_SEND_ENABLED=true`, after explicit
  confirmation, with full validation + audit.
- **Conversation capture**: the bot now records client↔bot AI turns into
  `crm_messages` so the inbox has data (previously nothing wrote to it).

## 3. Data model (reused — no migration)

- `crm_contacts` — contact + raw `telegram_chat_id` (send target).
- `crm_messages` — `direction` (inbound/outbound), `sender_type` (user/bot/operator),
  `text` + auto-`redacted_text`, `telegram_message_id`, `created_at`.
- `crm_operator_outbound_audit` — one row per send attempt: `status`
  (blocked/sent/failed), `operator_id`, `message_hash`, `message_preview` (≤100),
  `blocked_reason`, `error_message`, `telegram_message_id`, timestamps.

## 4. Flags (BusinessSettings, default safe)

| Env var | Default | Meaning |
|---------|---------|---------|
| `OPERATOR_WEB_SEND_ENABLED` | **false** | Master send switch. Off → API 403 `sender_disabled`, composer disabled, no Telegram. |
| `OPERATOR_WEB_SEND_MAX_CHARS` | `1000` | Max reply length. |
| `OPERATOR_WEB_SEND_CONFIRM_REQUIRED` | `true` | Require explicit `confirm_send` to deliver. |

(Separate from `CRM_OPERATOR_REPLY_ENABLED`, which only gated the old preview.)

## 5. API (admin-only, `require_api_token`)

- `GET  /api/v1/admin/crm/conversations` — list (filters q/status, limit≤100, offset);
  returns name, masked phone, lead_status, temperature, latest preview + time.
- `GET  /api/v1/admin/crm/conversations/{contact_id}/messages` — chronological timeline.
- `POST /api/v1/admin/crm/conversations/{contact_id}/operator-reply` — body
  `{message, confirm_send}`. Status mapping: **403** `sender_disabled` (flag off),
  **422** validation blocked, **404** contact not found, **409** `confirm_required`,
  **200** `{status: sent|failed, telegram_message_id}`.

## 6. Send service — `core/services/operator_reply_service.py`

Order: **flag gate → validation → confirm gate → send → audit.**

- `sanitize_operator_reply` — mask phones, normalize whitespace.
- `validate_operator_reply` — block empty / too-long / **secret** (token/key/Bearer,
  checked on raw text) / contact-not-found / missing-chat-id / stopped-or-lost;
  warn on phone. Returns sanitized preview + hash.
- `resolve_chat_target` — `telegram_chat_id` else `telegram_user_id`.
- `block_when_disabled(enabled)` — the hard OFF gate.
- `_default_sender` — builds an aiogram `Bot` from the token **server-side**, sends
  one message, closes the session; **never raises**, **never logs the token**.
  Injectable — tests pass a fake sender (no real Telegram).
- `record_operator_reply` — writes the audit row; on `sent`, also records an
  `operator` `crm_messages` row so the reply appears in the timeline.
- `send_operator_reply` — orchestrates the above; never raises; returns a status dict.

## 7. Conversation capture (bot)

`apps/bot/handlers/private/ai_support.py` — `_capture_crm_turn` (fire-and-forget,
exception-isolated) upserts the contact and records the inbound + bot-outbound
messages. Wired at **3 AI turn points**: OpenAI-success in both handlers + the KB
match. A capture failure only logs `crm_conversation_capture_failed` — it can never
break a reply, and it does not touch Unknown-Questions capture.

**Deferred:** capturing deterministic-route replies (price/catalog/operator/
measurement) — V1 captures AI conversation turns + operator replies. The store and
inbox already support those rows; only the capture hooks are incremental.

## 8. Safety rules

- **Default OFF.** No Telegram send until `OPERATOR_WEB_SEND_ENABLED=true`; while off
  the composer shows a "send disabled" notice and the API returns 403.
- **One message, one known contact.** No bulk, no group, no campaign, no AI auto-send.
  The target chat id must already be on the contact.
- **Validated + sanitized + audited.** Secrets blocked, phones masked in stored
  previews, token never stored/logged; every attempt writes an audit row.
- **Explicit confirmation** required (JS confirm + `confirm_send=true`).
- **Failure-safe.** Send/record/capture never raise into the reply path.
- Output masks phones; raw chat id is not rendered in the UI.

## 9. Rollout plan

1. Merge with the flag **off** — inbox is read-only; capture begins populating
   `crm_messages` (additive, safe).
2. On a TEST bot, set `OPERATOR_WEB_SEND_ENABLED=true`, open a conversation, send one
   reply, confirm delivery + the audit row + the operator message in the timeline.
3. Enable in production via the env flag once satisfied. Keep `CONFIRM_REQUIRED=true`.

## 10. Rollback

Set `OPERATOR_WEB_SEND_ENABLED=false` (or remove it) and restart — instant no-send.
No data change, no migration. Conversation capture is additive; to stop it, revert
the capture hooks (separate from the send flag).

## 11. Not included (deferred)

- Bulk / group / campaign send · AI auto-send · production enablement.
- Deterministic-route conversation capture (price/catalog/etc.).
- Per-operator RBAC, send rate-limiting, real-time push (current inbox is request/poll).
- Encrypted-at-rest chat id (reuses the existing raw `telegram_chat_id`).

## 12. Tests

- `tests/unit/services/test_operator_reply_service.py` — validation, secret block,
  phone masking, flag-off blocks send, confirm gate, sent/failed audit, no token leak.
- `tests/unit/api/test_crm_conversation_api.py` — endpoints, filters, auth, status
  mapping (403/422/404/409/200), single send path, no bulk/campaign.
- `tests/unit/web/test_crm_conversation_inbox.py` — page/nav/list/timeline/composer;
  send disabled when flag off; confirmation; contact-detail link.
- `tests/unit/bot/test_conversation_message_capture.py` — inbound+bot recorded,
  failure swallowed, 3 turn points, Unknown-Questions/reaction/KB intact.

## 13. Files

- `shared/config/settings.py` — `OPERATOR_WEB_SEND_*` flags.
- `core/services/operator_reply_service.py` — send orchestration.
- `apps/api/routes/admin_crm_conversations.py` + registration in `apps/api/main.py`.
- `apps/bot/handlers/private/ai_support.py` — `_capture_crm_turn` + 3 hooks.
- `apps/web/main.py` (`/crm/inbox`) + `apps/web/templates/crm_conversations.html`
  + `base.html` (nav) + `crm_contact_detail.html` (link).
- Tests as listed in §12; this doc.
