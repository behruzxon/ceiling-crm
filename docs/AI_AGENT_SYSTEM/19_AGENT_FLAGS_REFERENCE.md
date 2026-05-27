# Agent Feature Flags Reference

All agent-related environment variables, their defaults, rollout stage, risk level, and rollback value.

## Signal & Decision Flags

| Flag | Default | Stage | Risk | Effect | Rollback |
|------|---------|-------|------|--------|----------|
| AGENT_LEAD_SIGNAL_ENABLED | false | 1 | none | Extract intent/objection from text | false |
| AGENT_LEAD_SCORING_ENABLED | false | 1 | none | Compute lead score from signals | false |
| AGENT_TEXT_NORMALIZATION_ENABLED | true | 1 | none | Uzbek Cyrillic + typo normalization | true |
| AGENT_FUZZY_INTENT_ENABLED | true | 1 | none | Fuzzy keyword matching | true |
| AGENT_FUZZY_MAX_DISTANCE | 1 | 1 | low | Max Levenshtein distance | 1 |
| AGENT_DECISION_ENGINE_ENABLED | false | 1 | none | Agent decision evaluation | false |
| AGENT_DECISION_LOG_ONLY | true | 1 | none | Log decisions only | true |
| AGENT_DECISION_MIN_CONFIDENCE | 60 | 1 | none | Min confidence for actions | 60 |

## Offer & Policy Flags

| Flag | Default | Stage | Risk | Effect | Rollback |
|------|---------|-------|------|--------|----------|
| AGENT_DYNAMIC_OFFER_ENABLED | false | 1 | none | Rule-based offer selection | false |
| AGENT_DYNAMIC_OFFER_MIN_CONFIDENCE | 60 | 1 | none | Min confidence to persist | 60 |
| AGENT_DYNAMIC_OFFER_LOG_ONLY | true | 1 | none | Store in memory only | true |
| AGENT_CONVERSATION_POLICY_ENABLED | false | 1 | none | Conversation policy engine | false |
| AGENT_CONVERSATION_POLICY_LOG_ONLY | true | 1 | none | Store in memory only | true |
| AGENT_CONVERSATION_POLICY_MIN_CONFIDENCE | 60 | 1 | none | Min confidence | 60 |

## Orchestrator Flags

| Flag | Default | Stage | Risk | Effect | Rollback |
|------|---------|-------|------|--------|----------|
| AGENT_RESPONSE_ORCHESTRATOR_ENABLED | false | 1 | none | Full pipeline orchestrator | false |
| AGENT_RESPONSE_ORCHESTRATOR_LOG_ONLY | true | 1 | none | Trace only, no takeover | true |
| AGENT_RESPONSE_ORCHESTRATOR_MIN_CONFIDENCE | 60 | 1 | none | Min confidence | 60 |
| AGENT_RESPONSE_ORCHESTRATOR_TRACE_ENABLED | true | 1 | none | Store pipeline trace | true |

## Follow-up Flags

| Flag | Default | Stage | Risk | Effect | Rollback |
|------|---------|-------|------|--------|----------|
| AGENT_FOLLOWUPS_ENABLED | false | 3 | medium | Master follow-up switch | false |
| AGENT_CATALOG_FOLLOWUP_ENABLED | false | 3 | medium | 10-min catalog follow-up | false |
| AGENT_PRICE_FOLLOWUP_ENABLED | false | 3 | medium | 10-min price follow-up | false |
| AGENT_ORDER_FOLLOWUP_ENABLED | false | 3 | medium | 10-min order follow-up | false |
| AGENT_CATALOG_FOLLOWUP_DELAY_MINUTES | 10 | 3 | low | Delay before send | 10 |
| AGENT_PRICE_FOLLOWUP_DELAY_MINUTES | 10 | 3 | low | Delay before send | 10 |
| AGENT_ORDER_FOLLOWUP_DELAY_MINUTES | 10 | 3 | low | Delay before send | 10 |

## Admin Escalation Flags

| Flag | Default | Stage | Risk | Effect | Rollback |
|------|---------|-------|------|--------|----------|
| AGENT_ADMIN_ESCALATION_ENABLED | false | 3 | low | Send admin alerts | false |
| AGENT_ADMIN_ESCALATION_AFTER_FOLLOWUPS | 2 | 3 | low | Escalate after N followups | 2 |
| AGENT_ADMIN_ESCALATION_COOLDOWN_MINUTES | 60 | 3 | low | Min gap between alerts | 60 |

## AI Composer Flags

| Flag | Default | Stage | Risk | Effect | Rollback |
|------|---------|-------|------|--------|----------|
| AGENT_AI_COMPOSER_ENABLED | false | 4 | medium | AI-personalized messages | false |
| AGENT_AI_COMPOSER_MODEL | gpt-4o-mini | 4 | low | Model for composing | gpt-4o-mini |
| AGENT_AI_COMPOSER_TIMEOUT_SECONDS | 8 | 4 | low | Max wait for AI | 8 |
| AGENT_AI_COMPOSER_MAX_TOKENS | 180 | 4 | low | Max output tokens | 180 |

## Execution Sandbox Flags

| Flag | Default | Stage | Risk | Effect | Rollback |
|------|---------|-------|------|--------|----------|
| AGENT_EXECUTION_SANDBOX_ENABLED | false | 2 | none | Sandbox validation | false |
| AGENT_EXECUTION_MODE | log_only | 2 | varies | log_only/dry_run/canary/approval/live | log_only |
| AGENT_EXECUTION_CANARY_USER_IDS | (empty) | 3 | low | Comma-separated canary IDs | (empty) |
| AGENT_EXECUTION_REQUIRE_APPROVAL_FOR_USER_DM | true | 4 | low | Require admin approval | true |
| AGENT_EXECUTION_REQUIRE_APPROVAL_FOR_ADMIN_ALERT | false | 4 | none | Admin alerts skip approval | false |
| AGENT_EXECUTION_MAX_DAILY_ACTIONS_PER_USER | 3 | 3 | low | Daily DM cap | 3 |
| AGENT_EXECUTION_TRACE_ENABLED | true | 2 | none | Store execution trace | true |

## Execution Queue & Sender Flags

| Flag | Default | Stage | Risk | Effect | Rollback |
|------|---------|-------|------|--------|----------|
| AGENT_EXECUTION_QUEUE_ENABLED | false | 4 | low | Persistent approval queue | false |
| AGENT_EXECUTION_APPROVAL_TTL_MINUTES | 30 | 4 | none | Proposal expiration | 30 |
| AGENT_EXECUTION_APPROVAL_ADMIN_NOTIFY | false | 4 | low | Send approval to admin group | false |
| AGENT_EXECUTION_AUTO_EXECUTE_APPROVED | false | 5 | high | Auto-send approved payloads | false |
| AGENT_EXECUTION_LIVE_SENDER_ENABLED | false | 5 | high | Real Telegram send | false |
| AGENT_EXECUTION_LIVE_SENDER_BATCH_LIMIT | 10 | 5 | low | Max per scheduler tick | 10 |
| AGENT_EXECUTION_LIVE_SENDER_REVALIDATE | true | 5 | none | Safety check before send | true |
| AGENT_EXECUTION_LIVE_SENDER_MARK_FAILED_ON_ERROR | true | 5 | none | Mark failed on error | true |

## Emergency Rollback

Set ALL agent flags to their rollback values (rightmost column) and restart bot + scheduler.
