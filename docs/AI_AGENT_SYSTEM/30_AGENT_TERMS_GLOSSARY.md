# Agent Terms Glossary

Quick reference for terms used across the AI Agent system documentation.

| Term | Definition |
|------|-----------|
| **Lead** | A potential customer captured by the bot. Has a name, phone, area, district, and design preference. Moves through pipeline stages from NEW to COMPLETED or LOST. |
| **Hot Lead** | A lead with a high score (>=60) indicating strong purchase intent. Triggers admin alerts and prioritized follow-up. |
| **Warm Lead** | A lead with a moderate score (30-59). Shows interest but has not committed. Gets standard follow-up cadence. |
| **Cold Lead** | A lead with a low score (<30). Minimal engagement. No aggressive follow-up -- only light observation. |
| **Follow-up** | An automated message sent to a lead after a period of inactivity, designed to re-engage them. Subject to cooldown, daily caps (3/user/day), and lifetime caps (5 total). |
| **Orchestrator** | The central pipeline that processes every user message: extracts signals, evaluates decisions, selects offers, applies conversation policy, and produces a response trace. In LOG_ONLY mode it only observes; in higher stages it can propose or send actions. |
| **Policy** | A set of rules that determines how the agent should respond to a given situation. Examples: `reply_now`, `wait_and_observe`, `handoff_operator`, `disable_agent`. Policies prevent the agent from acting inappropriately. |
| **Offer** | A specific action the agent proposes: price calculation, design catalog, measurement booking, closing CTA, or cheaper alternative. Selected by the dynamic offer engine based on lead signals and buyer type. |
| **Sandbox** | The execution sandbox that validates proposed actions before they reach users. Checks for blocked content (phone numbers, banned phrases), daily/lifetime caps, canary restrictions, and stop signals. Actions that fail sandbox checks are blocked. |
| **Approval Queue** | A list of proposed agent actions waiting for admin review. Each proposal has a 30-minute TTL. Admins can approve or reject. Only approved actions proceed to sending (when live sender is enabled). |
| **Live Sender** | The component that actually sends Telegram messages to users. Only active at Stage 5 (LIVE SEND). When off, no agent-initiated messages reach users regardless of other settings. |
| **Rollout Stage** | The current operational mode of the agent, from OFF (0) through LOG_ONLY (1), DRY_RUN (2), CANARY (3), APPROVAL_REQUIRED (4), to LIVE SEND (5). Each stage progressively enables more agent capabilities. Stages must not be skipped. |
| **LOG_ONLY** | Stage 1. The agent observes all messages, extracts signals, and writes traces, but takes no action and sends no messages. The safest active stage for initial deployment and observation. |
| **Canary** | Stage 3. The agent sends real messages, but only to a predefined list of test users (typically admin accounts). All other users are unaffected. Used to verify message quality before wider rollout. |
| **Rollback** | Reverting the agent to a previous (safer) stage, typically OFF. Done by applying the OFF preset in the Control Center. Always safe to perform. When in doubt, rollback first. |
| **Preflight** | An automated check script (`agent_preflight_check.py`) that verifies all prerequisites are met before advancing to a new stage. Checks migrations, flags, test results, and configuration. Must pass before any stage change. |
| **Control Center** | The web dashboard at `/agent` where operators monitor agent status, review approvals, read health indicators, apply stage presets, and view audit logs. Read-only by default. |
