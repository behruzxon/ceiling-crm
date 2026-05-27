# AI Support Handler Refactor

## Problem

`apps/bot/handlers/private/ai_support.py` grew to 1,356 lines — the largest production file. Mixed concerns: agent pipeline, auto-reply logic, rate limiting, handler functions, and callbacks.

## New Structure

| File | Lines | Responsibility |
|------|-------|----------------|
| `ai_support.py` | ~1,035 | Router + handlers (thin orchestration) |
| `ai_support_agent.py` | ~100 | `_run_orchestrator`, `_process_lead_signal` |
| `ai_support_auto_reply.py` | ~230 | `_try_auto_reply`, `_detect_simple_intent`, rate limiting |
| `ai_states.py` | | FSM states, keyboards, text constants |
| `ai_detection.py` | | Intent/trigger detection, text parsing |
| `ai_memory.py` | | Redis AI memory + stats |
| `ai_scoring.py` | | Lead scoring + objection detection |
| `ai_openai.py` | | OpenAI integration + conversation DB |
| `ai_notifications.py` | | Admin notification orchestration |
| `ai_followups.py` | | Async delayed follow-up tasks |
| `ai_pricing_helpers.py` | | Price display helpers |

## Behavior Preserved

- All router handlers unchanged
- Same fire-and-forget patterns
- Same error handling (try/except with pass/log.debug)
- Same CRM logging failure isolation
- Same agent orchestrator pipeline
- Same public symbols importable from `ai_support`

## Import Compatibility

All external imports remain valid:
- `from apps.bot.handlers.private.ai_support import router` (main.py)
- `from apps.bot.handlers.private.ai_support import AiSupportStates` (sales_closer_callbacks)
- `from apps.bot.handlers.private.ai_support import _load_ai_memory` (operator_callbacks)
- `from apps.bot.handlers.private.ai_support import _get_lead_score` (operator_callbacks)
- `from apps.bot.handlers.private.ai_support import _add_lead_score` (sales_closer_callbacks)
- `from apps.bot.handlers.private.ai_support import clear_ai_conversation` (support.py)
- `from apps.bot.handlers.private.ai_support import cmd_ai_start` (support.py)

## Future Maintenance

When adding new agent/CRM features:
- Agent pipeline logic → `ai_support_agent.py`
- Auto-reply/template logic → `ai_support_auto_reply.py`
- Handler registration → `ai_support.py` (router file)
