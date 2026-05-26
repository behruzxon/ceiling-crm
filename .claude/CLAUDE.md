# Claude Code Workspace Rules — CeilingCRM

> This file complements the root `CLAUDE.md`. Root CLAUDE.md covers codebase conventions, architecture, and commands. This file covers **how Claude should work** in this project.

## Development Protocol

Follow this sequence for every task:

1. **Read existing code** — Before changing anything, read the files you plan to modify. Understand the current implementation, not just the interface.
2. **Understand context** — Trace the call chain: handler -> service -> repository -> model. Check DI wiring in `infrastructure/di.py`. Check router registration in `apps/bot/main.py`.
3. **Plan changes** — For anything beyond a trivial fix, write a brief plan: which files change, what the new behavior is, what could break.
4. **Implement minimal safe changes** — Change the fewest files possible. Prefer extending over rewriting. Never refactor unrelated code in the same change.
5. **Test** — Run `pytest tests/unit/` for unit tests. Run `ruff check .` for linting. Run `python -c "from apps.bot.main import build_dispatcher"` as a smoke test.
6. **Report** — After each step, provide: changed files list, test commands, risk assessment, next step, rollback plan.

## Rules for This Project

### Never do these things
- Never make large changes without a written plan
- Never skip reading existing code before editing
- Never modify existing Alembic migrations (create new ones instead)
- Never hardcode prices (use `pricing_service.py` or `shared/constants/pricing.py`)
- Never log tokens, phone numbers, or API keys
- Never use bare `except:` — always catch specific exceptions
- Never create a global SQLAlchemy engine in Celery tasks (create local engine + dispose in finally)
- Never register a router without checking `apps/bot/main.py` registration order

### Always do these things
- Always write tests before big refactors
- Always check `CacheKeys` in `infrastructure/cache/keys.py` before adding Redis keys
- Always use `values_callable=lambda x: [e.value for e in x]` on SQLAlchemy Enum columns
- Always sanitize user input before passing to AI prompts
- Always validate callback data patterns before registering new callback handlers
- Always check for callback pattern conflicts with existing handlers

## Bot Core Mission

The bot exists to:
1. **Capture leads** — collect name, phone, area, district, design preference
2. **Provide pricing** — instant calculator with ceiling type, area, addons
3. **Show catalog** — design galleries with inline browsing
4. **Process orders** — measurement booking, package selection
5. **Follow up** — automated reminders at configured intervals
6. **Notify admins** — new lead cards, hot lead alerts, status updates in admin group

## AI Agent Rules

- **Event-driven**: React to user actions, never initiate unsolicited conversations
- **No spam**: Respect cooldowns (min 1h between follow-ups, max 5 per user total)
- **Stop on signal**: Honor "kerak emas", "rahmat", "stop", operator request, bot block
- **Cooldown first**: Always check Redis cooldown key before sending any automated message
- **Dedup**: Use Redis NX keys to prevent duplicate messages for the same event
- **Escalate**: After 2 unanswered follow-ups, notify admin instead of sending more

## Security Checklist

- Never log or print `.env` contents, bot tokens, or user phone numbers
- Sanitize all user text before embedding in AI prompts (see `shared/utils/sanitize.py`)
- Validate all callback data against expected patterns
- Use RBAC checks (`RoleFilter`) for all admin operations
- Rate limit all user-facing endpoints

## Architecture Decision Records

Reference `docs/AI_AGENT_SYSTEM/` for detailed architecture decisions about the AI agent system, journey engine, and follow-up mechanics.

## Quick Reference

| What | Where |
|------|-------|
| Codebase conventions | Root `CLAUDE.md` |
| Architecture layers | Root `CLAUDE.md` > Architecture |
| Dev commands | Root `CLAUDE.md` > Development Commands |
| Enums (single source) | `shared/constants/enums.py` |
| DI wiring | `infrastructure/di.py` |
| Router order | `apps/bot/main.py` > `build_dispatcher()` |
| Cache keys | `infrastructure/cache/keys.py` |
| AI system prompt | `apps/bot/ai/system_prompt.py` |
| Pricing constants | `shared/constants/pricing.py` |
| Knowledge base | `shared/knowledge/uz.md` |
