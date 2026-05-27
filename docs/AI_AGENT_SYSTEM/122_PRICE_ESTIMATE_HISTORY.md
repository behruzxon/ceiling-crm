# 122 — Price Estimate History

## Purpose

Price Estimate History gives operators and admins a complete view of all price estimates calculated for a customer. This helps understand what the customer was quoted, which designs they explored, and whether a handoff or operator request followed the estimate.

## Data Sources

- **AI traces**: `ai_trace_summary` with `last_price_estimate`, `area_m2`, `design_type`
- **Conversation replay events**: `price_estimate` event type from replay builder
- **Memory payload**: FSM memory `last_price_total`, `last_price_area_m2`, `last_price_design`
- **Contact metadata**: `metadata.last_price_estimate`, `metadata.area_m2`

No new database table required. History is built from existing available data.

## Fields

| Field | Type | Description |
|-------|------|-------------|
| `estimate_id` | str | Unique hash for dedup |
| `contact_id` | int | CRM contact ID |
| `timestamp` | str | When estimate was calculated |
| `source` | str | ai_trace / replay / price_calculator / unknown |
| `area_m2` | float | Room area |
| `design_key` | str | Design slug (adnatonniy, gulli, hi-tech...) |
| `design_title` | str | Human-readable design name |
| `rate_uzs_per_m2` | int | Rate per square meter |
| `subtotal_uzs` | int | Before discount |
| `discount_percent` | float | Discount percentage |
| `discount_amount_uzs` | int | Discount amount |
| `total_uzs` | int | Final estimate amount |
| `is_estimate` | bool | Always true (taxminiy) |
| `warning` | str | Taxminiy disclaimer |
| `handoff_after_estimate` | bool | Whether operator was requested after |
| `metadata_summary` | str | Sanitized metadata (safe keys only) |

## UI

Sidebar card in contact detail, above AI Trace Viewer:
- Latest estimate highlight (green accent)
- Summary badges (total count, price range, handoff count)
- Compact item list (area, design, rate, total, taxminiy badge)
- Discount badge if applicable
- Handoff indicator arrow
- Empty state: "Hali narx hisoblari yo'q."
- Taxminiy warning footer

## API Endpoint

```
GET /api/v1/admin/crm/contacts/{contact_id}/price-estimates
```

Requires: `require_api_token` (admin auth)

Returns:
```json
{
  "contact_id": 123,
  "summary": {
    "total_estimates": 3,
    "latest_total_uzs": 2400000,
    "min_total_uzs": 1600000,
    "max_total_uzs": 2800000,
    "most_requested_design": "gulli",
    "total_area_m2": 55.0,
    "handoff_after_estimate_count": 1,
    "has_recent_estimate": true
  },
  "items": [...]
}
```

## Safety

- All estimates marked `is_estimate: true` with taxminiy warning
- Customer-facing prices only (DESIGN_PRICES_CUSTOMER)
- No internal quote prices exposed
- Tokens, API keys, DB URLs redacted
- Phone numbers not shown in estimate data
- No raw JSON metadata dump
- No final price guarantee
- No fake discount

## Limitations

- History depth depends on available traces/replay data
- If only `last_price_estimate` exists in contact metadata, shows single-item history
- No real-time updates (page refresh required)
- Discount detection from traces may be incomplete (only total available, not breakdown)

## Tests

- `tests/unit/services/test_step_7_price_estimate_history_service.py` — 55+ service tests
- `tests/unit/api/test_step_7_price_estimate_history_api.py` — 25+ API tests
- `tests/unit/web/test_step_7_price_estimate_history_web.py` — 35+ template tests
- `tests/integration/agent/test_step_7_price_estimate_history_flow.py` — 15+ flow tests

## Next Step

Step 8 — Operator Assignment UI
