# Security Rollback Card — Emergency

## Immediate Recovery Steps

If locked out or security features cause issues:

### 1. Disable Session Auth
```
ADMIN_SESSION_AUTH_ENABLED=false
```

### 2. Disable CSRF
```
ADMIN_CSRF_ENABLED=false
```

### 3. Disable DB RBAC (or enable fallback)
```
ADMIN_DB_RBAC_ENABLED=false
# OR keep enabled but ensure fallback:
ADMIN_DB_RBAC_FALLBACK_TO_ENV=true
```

### 4. Disable Security Actions
```
ADMIN_SECURITY_ACTIONS_ENABLED=false
```

### 5. Disable IP Enforcement
```
ADMIN_IP_BLOCK_ENFORCEMENT_ENABLED=false
```

### 6. Restart
Restart web/API application after changing env vars.

### 7. Verify
- Dashboard login works with HTTP Basic Auth
- Admin API token auth works
- No permission errors for existing workflows

## Owner Lockout Recovery

If owner cannot login:
1. Set ADMIN_DB_RBAC_ENABLED=false
2. Set ADMIN_SESSION_AUTH_ENABLED=false
3. Ensure ADMIN_OWNER_IDS contains the owner's Telegram ID
4. Restart application
5. Verify login with HTTP Basic Auth

## Prevention

- Always keep ADMIN_DB_RBAC_FALLBACK_TO_ENV=true when testing DB RBAC
- Never disable all owners simultaneously
- Run preflight before enabling any stage
