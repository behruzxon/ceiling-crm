# Step CL — Operator Handoff Queue / ETA-Safe Flow

**Date**: 2026-05-27
**Branch**: feature/packages-update

## Purpose

Build a safe operator handoff queue that records structured requests in the DB without fake ETA promises, enabling future operator dashboard and workflow management.

## User Flow

1. User says/presses "operator kerak"
2. Bot creates structured handoff request in DB
3. If phone missing and config requires it: asks for phone
4. Shows safe response without fake ETA
5. Duplicate requests within 30 min are deduped
6. Admin notification only if flag enabled (default OFF)

## DB Model

Table: `crm_operator_handoff_requests`

Key fields: id, contact_id, telegram_user_id, status (open/waiting_phone/assigned/contacted/resolved/cancelled/expired), priority (low/normal/high/urgent), source, reason, phone_masked, district, area_m2

## Priority Rules

- **urgent**: lead_score >= 80, complaint, angry objection, repeated request + high score
- **high**: phone + price question, measurement request, phone + score >= 40
- **normal**: standard operator request (default)
- **low**: weak/unclear request

## Dedup Rules

- If open/waiting_phone handoff exists within 30 min → update existing, don't create new
- Returns is_duplicate=True in result

## No-ETA Safety

User messages contain NO time promises:
- "Operator xabaringizni ko'rib chiqadi" (will review)
- Never "hozir qo'ng'iroq qiladi" (will call now)
- Never "bugun keladi" (will come today)
- Never exact minutes/hours

## Config Flags

| Flag | Default | Purpose |
|------|---------|---------|
| CRM_OPERATOR_HANDOFF_QUEUE_ENABLED | true | Enable queue recording (safe, DB only) |
| CRM_OPERATOR_HANDOFF_REQUIRE_PHONE | true | Ask phone if missing |
| CRM_OPERATOR_HANDOFF_DEDUP_MINUTES | 30 | Dedup window |
| CRM_OPERATOR_HANDOFF_EXPIRE_HOURS | 24 | Auto-expire stale requests |
| CRM_OPERATOR_HANDOFF_ADMIN_NOTIFY_ENABLED | false | Admin notification (OFF by default) |
| CRM_OPERATOR_HANDOFF_DEFAULT_PRIORITY | normal | Default priority |
| CRM_OPERATOR_HANDOFF_URGENT_SCORE_THRESHOLD | 80 | Score for urgent priority |

## Safety

- No fake ETA in any user-facing message
- Phone masked in DB (phone_masked field)
- Token/secret patterns redacted in message previews
- Admin notify OFF by default
- No live sender, no auto-reply to user from queue
- Existing operator handler behavior preserved as fallback
