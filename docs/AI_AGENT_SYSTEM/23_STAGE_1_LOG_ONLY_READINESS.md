# Stage 1 — LOG_ONLY Readiness

## What is Stage 1?

LOG_ONLY mode means the agent **observes only**:
- Extracts signals from user messages (intent, objection, urgency)
- Evaluates decisions, offers, policies
- Writes traces to memory_data
- Shows activity in Control Center dashboard
- **Does NOT** change user behavior
- **Does NOT** send any messages
- **Does NOT** schedule follow-ups
- **Does NOT** escalate to admin

## Flags to Enable (via LOG_ONLY preset)

```
AGENT_LEAD_SIGNAL_ENABLED=true
AGENT_LEAD_SCORING_ENABLED=true
AGENT_DECISION_ENGINE_ENABLED=true
AGENT_DYNAMIC_OFFER_ENABLED=true
AGENT_CONVERSATION_POLICY_ENABLED=true
AGENT_RESPONSE_ORCHESTRATOR_ENABLED=true
AGENT_RESPONSE_ORCHESTRATOR_LOG_ONLY=true
```

## Flags That MUST Be False

```
AGENT_FOLLOWUPS_ENABLED=false
AGENT_CATALOG_FOLLOWUP_ENABLED=false
AGENT_PRICE_FOLLOWUP_ENABLED=false
AGENT_ORDER_FOLLOWUP_ENABLED=false
AGENT_EXECUTION_LIVE_SENDER_ENABLED=false
AGENT_EXECUTION_AUTO_EXECUTE_APPROVED=false
AGENT_ADMIN_ESCALATION_ENABLED=false
```

## Preflight

Run: `python scripts/agent_stage1_readiness_check.py`

Expected: GREEN or YELLOW (no RED blockers)

## Manual Test Scenarios

1. Send "20 kv qancha" → bot replies normally, trace written
2. Send "qimmat ekan" → bot replies normally, trace written
3. Send "нархи қанча" → bot replies normally, Cyrillic detected in trace
4. Send "operator kerak" → bot replies normally, operator intent in trace
5. Send "kerak emas" → bot replies normally, stop signal in trace
6. Check `/agent` dashboard → activity visible, health green

## Monitoring (24h)

- Control Center `/agent` — stage LOG_ONLY, health green
- Metrics overview — events incrementing
- Safety panel — no blockers
- Audit log — preset apply logged

## Rollback

Apply OFF preset or see `25_STAGE_1_ROLLBACK_CARD.md`

## Pass/Fail

**PASS**: No user complaints, no unexpected DMs, traces written, dashboard green
**FAIL**: Any unexpected message, health red, token/phone leak, scheduler errors
