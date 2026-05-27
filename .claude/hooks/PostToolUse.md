# Post-Tool-Use Reporting Format

After each code change, provide a structured report in this format.

## Report Template

```
## Changes Made
- [file_path]: description of change

## Test Commands
- pytest tests/unit/path/to/test.py
- ruff check changed_file.py

## Risk Assessment
- [Low/Medium/High]: reason

## Next Step
- What should be done next

## Rollback
- How to undo this change
```

## Guidelines

### Changes Made
- List every file that was created, modified, or deleted
- Use absolute file paths
- Describe what changed in each file (not just "updated")
- If a migration was created, note the revision ID

### Test Commands
- Include the specific pytest command to test the changed code
- Include `ruff check` for every modified Python file
- Include the smoke test if handler registration changed: `python -c "from apps.bot.main import build_dispatcher"`
- If a migration was created: `alembic upgrade head`

### Risk Assessment
- **Low**: cosmetic changes, new tests, documentation, isolated utility functions
- **Medium**: new handlers, new services, new DB columns, new scheduler jobs
- **High**: changes to existing handlers, migration changes, DI wiring changes, auth/RBAC changes, pricing logic changes

Include specific risks:
- Could this break existing user flows?
- Could this cause data loss?
- Could this send unintended messages to users?
- Could this expose sensitive information?

### Next Step
- What the developer should do after this change
- What tests to run manually
- What to verify in the Telegram bot
- Whether a migration needs to be applied

### Rollback
- Specific git command to undo (e.g., `git revert <commit>`)
- If a migration was applied: the downgrade command
- If Redis keys were added: whether they expire naturally or need manual cleanup
- If scheduler jobs were added: how to unregister them
