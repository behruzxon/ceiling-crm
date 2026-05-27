# Security Enablement Plan — Staged Rollout

## Stages

| Stage | Description | Key Flags |
|-------|-------------|-----------|
| S0 | Legacy Safe Mode | All OFF — current default |
| S1 | Env RBAC Observe | ADMIN_RBAC_ENABLED=true |
| S2 | DB RBAC Observe | ADMIN_DB_RBAC_ENABLED=true, fallback ON |
| S3 | Session Auth Staging | ADMIN_SESSION_AUTH_ENABLED=true |
| S4 | CSRF Staging | ADMIN_CSRF_ENABLED=true |
| S5 | Security Actions Staging | ADMIN_SECURITY_ACTIONS_ENABLED=true |
| S6 | IP Watch Mode | IP rules ON, enforcement OFF |
| S7 | IP Enforcement Limited | ADMIN_IP_BLOCK_ENFORCEMENT_ENABLED=true |

## Prerequisites Per Stage

- S1: Verify admin IDs in ADMIN_OWNER_IDS env var
- S2: At least one owner in admin_users DB table, OR fallback_to_env=true
- S3: APP_SECRET_KEY set, secure cookie config verified
- S4: Session auth must be ON first
- S5: Audit logging enabled
- S6: Watch rules created, no broad block-all
- S7: Allowlist verified, owner fallback tested

## Do Not Enable

- CSRF without session auth
- DB RBAC without owner AND without fallback
- IP enforcement without owner fallback
- All features at once (use stages)

## Validation

Run preflight before each stage:
```
python scripts/security_enablement_preflight.py --stage S3
```

## Rollback

Each stage can roll back to previous by disabling the stage flag and restarting.
See 71_SECURITY_ROLLBACK_CARD.md for emergency procedures.
