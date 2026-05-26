# Security Staging Test Script

## Manual Test Scenarios

### S1 — Env RBAC
1. Owner login — verify full access
2. Admin login — verify no admin.users/permissions
3. Operator login — verify CRM view + reply, no export_sensitive
4. Analyst login — verify CRM view + export, no reply
5. Viewer login — verify read-only

### S2 — DB RBAC
1. Create owner in admin_users DB
2. Verify DB role takes priority over env
3. Disable DB user, verify env fallback works
4. Test permission override JSON

### S3 — Session Auth
1. Navigate to /login page
2. Login with valid credentials
3. Verify session cookie set (HttpOnly, Secure, SameSite)
4. Access dashboard pages
5. Logout — verify cookie cleared
6. Verify expired session redirects to login
7. Verify old HTTP Basic Auth still works when session auth OFF

### S4 — CSRF
1. POST form without CSRF token — verify 403/error
2. POST form with valid CSRF token — verify success
3. GET/HEAD/OPTIONS — verify no CSRF required

### S5 — Security Actions
1. Revoke a test session — verify status changes
2. Disable a non-owner admin — verify blocked
3. Verify self-lockout blocked
4. Verify last-owner disable blocked
5. Create IP watch rule

### S6 — IP Watch
1. Create watch rule for test IP
2. Login from that IP — verify advisory only (not blocked)
3. Check audit log for watch entries

### S7 — IP Enforcement
1. Create block rule for test IP
2. Login from that IP — verify blocked
3. Login from allowed IP — verify success
4. Verify owner fallback prevents total lockout

### Rollback Test
1. Set ADMIN_SESSION_AUTH_ENABLED=false
2. Restart
3. Verify HTTP Basic Auth login works
4. Verify no session cookie required
