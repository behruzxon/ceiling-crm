# 123 — Operator Assignment UI

## Purpose

Enhanced operator assignment workflow in the CRM web UI so admins can clearly assign handoff requests, take ownership, view operator workload, and manage the queue efficiently.

## Assignment Workflow

1. **New handoff arrives** → status `open` or `waiting_phone`, unassigned
2. **Take** → operator clicks "Olish" → status `assigned`, `assigned_to_admin_id` set
3. **Assign** → admin clicks "Tayinlash" → status `assigned`, `assigned_to_admin_id` set
4. **Contacted** → operator marks "Bog'landim" → status `contacted`
5. **Resolve** → operator marks "Hal qildim" → status `resolved`
6. **Unassign** → admin clicks "Chiqarish" → clears assignment, status reverts to `open`/`waiting_phone`
7. **Cancel** → admin clicks "Bekor" → status `cancelled`

## API Changes

| Endpoint | Method | Description |
|----------|--------|-------------|
| `POST /handoffs/{id}/take` | New | Take ownership (self-assign) |
| `POST /handoffs/{id}/unassign` | New | Remove assignment, revert status |
| `GET /handoffs/operators/summary` | New | Operator workload dashboard |
| `POST /handoffs/{id}/assign` | Existing | Assign to specific admin |
| `POST /handoffs/{id}/contacted` | Existing | Mark as contacted |
| `POST /handoffs/{id}/resolve` | Existing | Mark as resolved |
| `POST /handoffs/{id}/cancel` | Existing | Cancel handoff |

### Operator Summary Response

```json
{
  "operators": [
    {
      "operator_id": "admin_123",
      "assigned_open": 5,
      "contacted": 2,
      "resolved_today": 3,
      "urgent_assigned": 1,
      "oldest_assigned_minutes": 45
    }
  ]
}
```

## UI Changes

1. **Assignment column** in queue table — shows assigned admin or "Tayinlanmagan" badge
2. **Assignment filter** — All / Unassigned / Assigned
3. **Take button** ("Olish") — self-assign for open/unassigned items
4. **Unassign button** ("Chiqarish") — remove assignment
5. **Operator workload card** — live stats per operator
6. **Action success/error banner** — replaces browser alerts
7. **Mobile responsive** — actions stack vertically on small screens

## Permissions

- All endpoints require `require_api_token` (admin auth)
- No additional role gating beyond existing auth pattern
- No token/session hash exposed

## No-Send Safety

- No Telegram messages sent
- No OpenAI API calls
- No real-time push to operators
- Internal CRM workflow only
- Phone numbers remain masked
- No fake ETA promises

## Limitations

- "Take" uses `admin_id: "current"` fallback when no auth identity available
- No real-time WebSocket updates (page refresh after action)
- Operator identity derived from `assigned_to_admin_id` field, not user table
- `confirm()` dialogs not used — documented as intentional (no destructive confirm debt)

## Tests

- `tests/unit/api/test_step_8_operator_assignment_api.py` — 35+ API tests
- `tests/unit/web/test_step_8_operator_assignment_ui.py` — 45+ UI tests
- `tests/unit/services/test_step_8_operator_assignment_service.py` — 30+ service tests
- `tests/integration/agent/test_step_8_operator_assignment_flow.py` — 15+ flow tests

## Next Step

Step 9 — Handoff Auto-Expire Job
