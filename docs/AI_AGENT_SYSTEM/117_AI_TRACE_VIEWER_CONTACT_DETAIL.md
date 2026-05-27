# Step 3 — AI Trace Viewer in Contact Detail

**Date**: 2026-05-27

## Purpose

Show AI decision traces in the CRM contact detail sidebar so admins can understand what the AI detected and decided for each user.

## Data Source

Uses existing contact metadata (`ai_trace_summary` field from context):
- last_intent
- last_price_estimate
- handoff_requested
- last_objection
- safety_status
- area_m2
- design_type
- lead_score

This is a "derived trace view" from existing contact data. No new DB table needed.

## UI Design

Location: Contact detail sidebar, below Notes section.

Elements:
- vp-card with title "AI Trace Viewer"
- Subtitle explaining purpose
- Badge row: Intent (info), Price (success), Handoff (warning), Objection (hot), Safety (success/danger), Mode (neutral LOG_ONLY)
- Detail line: area, design, score
- Empty state when no trace data available

## Redaction Rules

- No bot token displayed
- No OpenAI key displayed
- No raw system prompt
- No raw phone (use masked)
- No raw JSON metadata dump
- Message preview truncated to safe length

## Empty State

"Hali AI trace yo'q. Stage 1 LOG_ONLY yoqilganda bu yerda AI qarorlari ko'rinadi."

## Limitations

- Currently shows summary only, not per-message trace timeline
- Data populated when Stage 1 LOG_ONLY is active
- No dedicated API endpoint yet (uses existing contact context)
