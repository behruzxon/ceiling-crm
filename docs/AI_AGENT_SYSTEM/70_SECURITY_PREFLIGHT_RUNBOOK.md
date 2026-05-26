# Security Preflight Runbook

## Running the Script

```bash
# Default: check current env settings
python scripts/security_enablement_preflight.py

# Check specific stage requirements
python scripts/security_enablement_preflight.py --stage S3

# JSON output for automation
python scripts/security_enablement_preflight.py --json
```

## Status Meanings

| Status | Meaning | Action |
|--------|---------|--------|
| [OK] GREEN | Check passed | Safe to proceed |
| [WARN] YELLOW | Non-critical issue | Review before proceeding |
| [FAIL] RED | Blocker found | Must fix before proceeding |

## Common Failures

1. **Session auth without secret key** — Set APP_SECRET_KEY in .env
2. **DB RBAC without owner** — Insert owner into admin_users or enable fallback
3. **CSRF without session auth** — Enable session auth first (S3 before S4)
4. **IP enforcement without fallback** — Enable ADMIN_DB_RBAC_FALLBACK_TO_ENV=true
5. **Secure cookie on dev** — Set ADMIN_SESSION_SECURE_COOKIE=false for local dev

## No Secrets Printed

The script never prints secret values, tokens, or passwords.
