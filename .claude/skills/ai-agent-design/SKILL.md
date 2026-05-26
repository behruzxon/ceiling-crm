# Skill: AI Agent Design

Design and implement AI agent components for the CeilingCRM bot. Follow these principles and patterns.

## Event-Driven Architecture

- Agents react to events, never poll or initiate unprompted conversations
- Events originate from: user messages, callback button presses, scheduler triggers, admin actions
- Every agent action must trace back to a triggering event
- Use the existing event bus (`core/events/`) for domain events (LeadCreated, StageChanged, etc.)
- New events should extend the existing event types, not create parallel systems

## Journey State Machine Design

- Define journey states as Python enums, not magic strings
- Each state must have: entry conditions, valid transitions, exit actions
- Every state machine must have a terminal state (completed, cancelled, or escalated)
- Store journey state in Redis (ephemeral) or DB (persistent), never in-memory only
- Validate transitions: reject invalid state moves with clear error messages
- Design for recovery: if the bot restarts, the journey must resume from the last persisted state

## Memory Schema Design

Store in agent memory (Redis FSM data or dedicated table):
- User's name, language preference
- Last mentioned design/style
- Last price inquiry details (area, type, addons)
- Last objection type and response
- Conversation turn count
- Lead score and temperature

Do NOT store in agent memory:
- Full message history (use summary instead)
- Phone numbers (store in lead record only)
- Payment information
- Internal system state or debug info

## Follow-Up Engine Rules

- Triggers: catalog viewed, price calculated, order started but not finished, phone captured, measurement booked
- Delays: 10 min (immediate intent), 15 min (phone capture), 24h (soft reminder), 72h (final attempt)
- Cooldowns: min 1 hour between any two follow-ups to same user
- Max follow-ups: 5 per user total across all event types
- Stop conditions: user replied, user ordered, user said "kerak emas"/"stop", operator requested, bot blocked
- Dedup: Redis NX key `followup:{user_id}:{event_type}` with TTL = cooldown period

## Anti-Spam Requirements

- Max 5 automated messages per user per day (across all types)
- Max 2 follow-ups per hour per user
- Cooldown between closing attempts: 10 minutes minimum
- Never send follow-up if user has an active conversation (last message < 5 min ago)
- Track message counts in Redis with daily expiry keys
- Hard stop: if user sends "kerak emas", "stop", "yoq", set permanent opt-out flag

## Admin Escalation Criteria

Escalate to admin when:
- Lead score >= 60 (hot lead)
- User explicitly requests operator/manager
- 2 consecutive follow-ups unanswered
- User provides phone number
- High-value lead (area > 50 m2 or premium package)
- Objection not resolved after 2 attempts

## Message Composition Guidelines

- Max 2-4 sentences per message
- Always end with a CTA (button or question)
- Use Uzbek as primary language, with Russian option
- 1-2 relevant emojis per message (not more)
- Personalize with user's name when available
- Reference specific details from conversation (area, design, price)
- Never use generic sales phrases

## Integration with Existing Services

When creating a new agent service:
1. Create the service in `core/services/` with naming convention `agent_*.py` or descriptive name (e.g., `followup_service.py`)
2. Define abstract repository in `core/repositories/` if new DB access is needed
3. Implement concrete repository in `infrastructure/database/repositories/`
4. Add DI factory function in `infrastructure/di.py`
5. Wire into handlers or scheduler as appropriate
6. Add unit tests in `tests/unit/services/`

### File Naming Convention

- Services: `core/services/{feature}_service.py` (e.g., `negotiation_engine_service.py`)
- Repositories (abstract): `core/repositories/{feature}_repo.py`
- Repositories (concrete): `infrastructure/database/repositories/{feature}_repo.py`
- Handlers: `apps/bot/handlers/{scope}/{feature}.py`
- Callbacks: `apps/bot/handlers/callbacks/{feature}_callbacks.py`
- States: `apps/bot/states/{feature}.py`
- Keyboards: `apps/bot/keyboards/{feature}.py`
- Scheduler jobs: `apps/scheduler/jobs/{feature}_jobs.py`
- Celery tasks: `infrastructure/queue/tasks/{feature}_tasks.py`

## Testing Requirements

- Every new service must have unit tests in `tests/unit/services/`
- Mock all repository dependencies with `AsyncMock`
- Mock Redis/cache operations
- Test all state transitions (valid and invalid)
- Test all cooldown/anti-spam rules with mock time
- Test edge cases: empty input, None values, concurrent access
- Test stop conditions: verify agent stops when it should
