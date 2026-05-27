# Skill: Bot Audit

Perform a comprehensive audit of the CeilingCRM Telegram bot. Follow each section below and produce a findings table.

## 1. Handler Audit

For each handler file in `apps/bot/handlers/`:
- Read the file and trace the user flow from entry to exit
- Check: does every flow have a clear end state?
- Check: are there dead-end states where the user gets stuck?
- Check: does the handler properly inject `db_session`, `db_user`, `user_role` from middleware?
- Check: is the handler registered in `apps/bot/main.py`?
- Check: is the registration order correct? (ai_support_router must be LAST in private_router)

## 2. Service Audit

For each service in `core/services/`:
- Check for stub methods or `NotImplementedError` that should be implemented
- Verify DI wiring exists in `infrastructure/di.py`
- Verify the service only depends on abstractions (repos from `core/repositories/`), never on concrete implementations
- Check that async methods properly await all async calls
- Check that services do not create their own DB sessions (except fire-and-forget services like `LeadNotificationService`)

## 3. FSM State Audit

For each `StatesGroup` in `apps/bot/states/`:
- Map all states and transitions
- Check: can the user go back from every state?
- Check: can the user cancel from every state?
- Check: is `await state.clear()` called at flow completion?
- Check: are there orphan states no handler references?

## 4. Keyboard Audit

For all keyboard definitions in `apps/bot/keyboards/`:
- Check: is the button layout clear? (max 3 buttons per row for inline)
- Check: does every flow have a clear primary CTA?
- Check: are there escape routes (back/cancel) on every keyboard?
- Check: do callback_data patterns match the handlers that receive them?
- Check: are button labels action-oriented and clear in Uzbek?

## 5. Database Audit

For all models in `infrastructure/database/models/`:
- Check: does every model have proper indexes for query patterns?
- Check: are foreign keys set with correct `ondelete` behavior?
- Check: do all `sa.Enum` columns use `values_callable=lambda x: [e.value for e in x]`?
- Check: is the migration chain linear? (`alembic heads` should show exactly 1)
- Check: are there models without corresponding repository implementations?

## 6. Scheduler Audit

For all jobs in `apps/scheduler/`:
- Check: is every job registered in the scheduler main?
- Check: are job intervals appropriate? (not too frequent, not too rare)
- Check: do jobs handle errors gracefully? (log + continue, not crash)
- Check: are jobs idempotent? (safe to run if triggered twice)
- Check: do Celery tasks create local engines? (never use global engine)

## 7. Admin Flow Audit

For admin notifications and escalations:
- Check: are new leads notified to admin group?
- Check: are hot leads escalated with proper context?
- Check: can admins update lead status from the notification card?
- Check: are status updates reflected in the database?
- Check: is the admin group ID configurable (not hardcoded)?

## 8. Security Audit

- Check: are bot tokens, API keys, or phone numbers ever logged?
- Check: is user input sanitized before AI prompt injection? (see `shared/utils/sanitize.py`)
- Check: are callback data patterns validated against expected formats?
- Check: is RBAC enforced on all admin-only handlers?
- Check: are rate limits applied to user-facing operations?
- Check: is the `.env` file in `.gitignore`?

## Output Format

For each finding, produce a row in this table:

| File | Purpose | Issue | Recommendation | Risk |
|------|---------|-------|----------------|------|
| path/to/file.py | What it does | What's wrong | How to fix | Low/Medium/High/Critical |

At the end, provide:
- **Total findings**: count by risk level
- **Top 3 priorities**: the most impactful issues to fix first
- **Clean areas**: sections that passed with no issues
