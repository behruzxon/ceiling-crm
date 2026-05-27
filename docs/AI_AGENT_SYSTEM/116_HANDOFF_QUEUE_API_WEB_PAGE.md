# Step 2 — Handoff Queue API + Web Page

**Date**: 2026-05-27

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | /api/v1/admin/crm/handoffs/summary | Queue KPI summary |
| GET | /api/v1/admin/crm/handoffs/queue | List with status/priority filters |
| POST | /api/v1/admin/crm/handoffs/{id}/assign | Mark assigned |
| POST | /api/v1/admin/crm/handoffs/{id}/contacted | Mark contacted |
| POST | /api/v1/admin/crm/handoffs/{id}/resolve | Mark resolved |
| POST | /api/v1/admin/crm/handoffs/{id}/cancel | Mark cancelled |

## Web Page

- Route: /crm/handoffs
- Template: crm_handoffs.html
- Sidebar: "Handoffs" link under CRM section
- active_page: handoffs

## UI Sections

- 5 KPI cards: Open, Waiting phone, Assigned, Urgent, High
- Filter bar: status + priority dropdowns
- Queue table with priority/status badges, phone masked, actions
- Actions: Assign, Contacted, Resolve, Cancel (via fetch to API)
- Empty state: "Hozir operator so'rovlari yo'q"
- Mobile: columns hidden at 767px

## Safety

- Phone always masked in responses
- No Telegram sends from API
- No fake ETA in any UI text
- Auth required (existing dashboard auth)
- No token/session hash exposed
