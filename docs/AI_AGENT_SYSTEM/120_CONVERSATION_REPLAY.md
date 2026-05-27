# 120 — Conversation Replay

## Purpose

Conversation Replay provides a chronological, business-friendly timeline of all significant events in a customer's CRM journey. Operators and admins can quickly understand what happened — messages, AI intent detection, price estimates, objections, handoff requests, and stop signals — without reading raw chat logs.

## Data Sources

- **Messages**: Chat message records (direction, sender_type, text, created_at)
- **AI Traces**: AI processing traces (intent, price_estimate, objection_type, area_m2)
- **Handoffs**: Operator handoff queue records (status, reason, created_at)
- **Contact metadata**: Phone, lead_status, created_at

## Event Types

| Type | Actor | Icon | Description |
|------|-------|------|-------------|
| `user_message` | user | user | Customer sent a message |
| `bot_reply` | bot | bot | Bot auto-reply |
| `ai_detected_intent` | ai | brain | AI classified user intent |
| `price_estimate` | bot | calculator | Price was calculated |
| `objection_detected` | user | alert-triangle | Customer raised an objection |
| `handoff_requested` | system | phone-forwarded | Operator handoff requested |
| `handoff_status_changed` | system | refresh | Handoff status updated |
| `phone_shared` | user | phone | Customer shared phone number |
| `order_started` | user | shopping-cart | Order flow started |
| `measurement_requested` | user | ruler | Measurement requested |
| `catalog_viewed` | user | image | Catalog browsed |
| `stop_requested` | user | x-circle | Customer requested stop |
| `operator_reply` | operator | headphones | Operator replied |
| `system_event` | system | settings | System event |

## Replay UI

The replay panel is a vertical timeline in the main column of the contact detail page, above the raw chat history. Each event shows:

- Actor-colored icon (user=blue, bot=green, ai=purple, operator=indigo, system=gray)
- Title and description
- Truncated, sanitized message preview
- Timestamp
- Severity/status badges
- Intent badge (if detected)

Summary bar shows: total events, user messages, bot replies, price events, objections, handoffs, stop events, and a recommended next action.

Empty state: "Hali replay uchun yetarli voqea yo'q."

## Privacy / Redaction

- Phone numbers masked with `****` pattern
- Bot tokens removed (`bot12345:AAA...` → `[REDACTED]`)
- OpenAI API keys removed (`sk-...` → `[REDACTED]`)
- Bearer tokens removed
- Database URLs removed (`postgresql://...` → `[REDACTED]`)
- HTML escaped in previews
- Message previews truncated to 200 chars
- Metadata filtered to safe keys only (intent, area, district, etc.)
- No raw JSON dump in responses

## API Endpoint

```
GET /api/v1/admin/crm/contacts/{contact_id}/conversation-replay
```

Requires: `require_api_token` (admin auth)

Returns:
```json
{
  "contact_id": 123,
  "summary": {
    "total_events": 12,
    "user_messages": 5,
    "bot_replies": 4,
    "price_events": 1,
    "handoff_events": 1,
    "objections": 1,
    "stop_events": 0,
    "first_seen_at": "2025-01-15T10:30",
    "last_event_at": "2025-01-15T11:45",
    "recommended_next_action": "Narx hisoblangan — o'lchov taklif qiling"
  },
  "events": [...]
}
```

## Tests

- `tests/unit/services/test_step_6_conversation_replay_service.py` — 55+ service tests
- `tests/unit/web/test_step_6_conversation_replay_web.py` — 40+ template tests
- `tests/integration/agent/test_step_6_conversation_replay_flow.py` — 15+ flow tests

## Limitations

- Replay is built on-demand from available data; if messages/traces are missing, the timeline is incomplete
- No real-time updates (page refresh required)
- Currently read-only via API — no write operations
- Phone masking uses regex pattern, not a formal parser
- AI intent detection uses keyword matching, not LLM

## Next Step

Step 7 — Price Estimate History
