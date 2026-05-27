# Stage 1 Environment / Flag Matrix

**Date**: 2026-05-27 | **Status**: NOT APPLIED

## Must Be ON

| Flag | Value | Reason |
|------|-------|--------|
| ADMIN_SESSION_AUTH_ENABLED | true | Web dashboard requires auth |
| CRM_OPERATOR_HANDOFF_QUEUE_ENABLED | true | Records queue entries (DB only, safe) |

## Must Be OFF

| Flag | Value | Reason |
|------|-------|--------|
| AGENT_EXECUTION_LIVE_SENDER_ENABLED | false | No automatic message sends |
| AGENT_FOLLOWUPS_ENABLED | false | No followup messages |
| AGENT_CATALOG_FOLLOWUP_ENABLED | false | No catalog followups |
| AGENT_PRICE_FOLLOWUP_ENABLED | false | No price followups |
| AGENT_ORDER_FOLLOWUP_ENABLED | false | No order followups |
| AGENT_EXECUTION_AUTO_EXECUTE_APPROVED | false | No auto-execution |
| CRM_CAMPAIGN_SEND_ENABLED | false | No campaign broadcasts |
| CRM_CAMPAIGN_CANARY_SEND_ENABLED | false | No canary sends |
| CRM_OPERATOR_REPLY_ENABLED | false | No live operator reply |
| CRM_DAILY_REPORT_DELIVERY_ENABLED | false | No report delivery |
| CRM_DAILY_REPORT_TELEGRAM_ENABLED | false | No Telegram reports |
| CRM_DAILY_REPORT_EMAIL_ENABLED | false | No email reports |
| ADMIN_SECURITY_ACTIONS_ENABLED | false | No security enforcement |
| ADMIN_IP_BLOCK_ENFORCEMENT_ENABLED | false | No IP blocking |
| CRM_OPERATOR_HANDOFF_ADMIN_NOTIFY_ENABLED | false | No auto admin notify |

## Must Be LOG_ONLY

| Flag | Value | Reason |
|------|-------|--------|
| AGENT_EXECUTION_MODE | log_only | Observation only, no sends |

## Optional / Safe to Leave Default

| Flag | Default | Notes |
|------|---------|-------|
| ADMIN_CSRF_ENABLED | false | Enable for extra web security (recommended P1) |
| ADMIN_RBAC_ENABLED | false | Role-based access (enable when multiple admins) |
| CRM_OPERATOR_HANDOFF_REQUIRE_PHONE | true | Asks phone if missing (safe) |
| CRM_OPERATOR_HANDOFF_DEDUP_MINUTES | 30 | Dedup window (safe) |

## Do Not Touch

| Flag | Reason |
|------|--------|
| AGENT_EXECUTION_SANDBOX_ENABLED | Not active in Stage 1 |
| AGENT_EXECUTION_QUEUE_ENABLED | Not needed for LOG_ONLY |
| AGENT_SETTINGS_MUTATION_ENABLED | Runtime settings locked |
| AGENT_SETTINGS_ALLOW_LIVE_FLAGS | No live flag changes |

## Required Environment Variables

| Variable | Required | Notes |
|----------|----------|-------|
| BOT_TOKEN | Yes | Valid Telegram bot token |
| OPENAI_API_KEY | Yes | Valid OpenAI key |
| POSTGRES_PASSWORD | Yes | Database password |
| BOT_ADMIN_GROUP_ID | Yes | Admin Telegram group chat ID |
| WEB_DASHBOARD_USERNAME | Yes (if auth on) | Dashboard login username |
| WEB_DASHBOARD_PASSWORD | Yes (if auth on) | Dashboard login password |
