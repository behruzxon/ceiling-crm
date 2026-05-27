# Step 4 — Missed Leads Dashboard

**Date**: 2026-05-27

## Purpose

Prevent client loss by surfacing leads that need immediate attention.

## Categories

| Category | Severity | Threshold |
|----------|----------|-----------|
| hot_unanswered | critical | >10 min |
| operator_waiting | critical | >5 min |
| phone_shared_no_followup | critical | >10 min |
| sla_critical | critical | immediate |
| price_interest_no_action | high | >15 min |
| handoff_waiting_phone | high | >30 min |
| stale_warm_lead | high | >24h |
| sla_overdue | high | immediate |
| catalog_no_next_step | medium | — |

## API Endpoints

- GET /api/v1/admin/crm/missed-leads/summary
- GET /api/v1/admin/crm/missed-leads (filtered list)
- GET /api/v1/admin/crm/missed-leads/recommendations

## Web Page

- Route: /crm/missed-leads
- Sidebar: "Missed Leads" under CRM
- KPI cards: Critical, High, Hot, Operator, Phone, Oldest
- Recommendations card with action items
- Filtered table with severity/reason badges
- Empty state: "Yo'qolayotgan leadlar yo'q"

## Safety

- No Telegram sends from dashboard
- Phone masked in all views
- No fake ETA
- Read-only data display
