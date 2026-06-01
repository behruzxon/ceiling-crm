# 154 — Telegram Reaction Micro-UX

> **Status banner**
>
> - Deploy: NO · VPS: NO · Push: pending approval
> - Flag: `TELEGRAM_REACTIONS_ENABLED` — **default FALSE** (feature is a pure no-op until set true)
> - Production token: NOT USED · Real OpenAI: NOT CALLED · No extra text messages sent
> - No reply text / routing / Unknown-Questions-capture change

## 1. Purpose

Make the bot feel alive and modern (2026 style): when a user sends a message and
the bot has to do slow work (the AI path), the bot **reacts** to the user's
message (👀) so they feel acknowledged instead of ignored, then **clears** that
reaction (or changes it to ✅) once the real reply is sent. No extra "typing…"
text messages — just a subtle, native Telegram reaction.

## 2. UX behavior (V1)

Wired into the two private AI handlers (`handle_ai_question`, `handle_ai_message`)
around the **OpenAI processing path** — the slow path where the acknowledgement
matters most:

1. Just before the AI call → `maybe_react_processing` sets 👀 on the user's message.
2. After the reply is sent → `maybe_react_done`:
   - default (`reaction_clear_on_reply=true`) → **clears** the reaction;
   - else → changes it to ✅ (`reaction_done`).
3. On AI error / fallback (the `except` path) → `maybe_clear_reaction` removes 👀
   so a failed turn doesn't leave a stale reaction.

Every "set" is paired with a "clear/done" — no lingering reactions. Fast
deterministic replies (stop, safety, greeting, price, catalog, operator) are
**not** reacted to in V1: they're instant, so a reaction would be noise, and we
explicitly avoid reacting to stop/blocked/safety messages. Those can be added
later "after proof" (see §8).

## 3. Flags (env prefix `TELEGRAM_`)

| Env var | Default | Meaning |
|---------|---------|---------|
| `TELEGRAM_REACTIONS_ENABLED` | **false** | Master switch. Off → total no-op. |
| `TELEGRAM_REACTIONS_GROUPS_ENABLED` | **false** | Allow reactions in group/supergroup. Off → **private only**. |
| `TELEGRAM_REACTION_PROCESSING` | `👀` | Emoji shown while processing. |
| `TELEGRAM_REACTION_DONE` | `✅` | Emoji used after reply when clear-on-reply is off. |
| `TELEGRAM_REACTION_CLEAR_ON_REPLY` | **true** | Clear the reaction after the reply (safest); else switch to `TELEGRAM_REACTION_DONE`. |

Defined in `shared/config/settings.py::TelegramSettings`, exposed as
`get_settings().telegram`.

## 4. Safety

- **Default OFF** — no production behavior change unless the flag is set.
- **Private only** unless groups are explicitly enabled.
- **Never raises** — `apps/bot/utils/reactions.py` swallows `TelegramBadRequest`
  (e.g. an emoji the chat disallows → `REACTION_INVALID`), `TelegramForbiddenError`,
  flood/`TelegramRetryAfter`, and any generic error. A reaction problem can never
  break a customer reply.
- **`✅` caveat:** Telegram only accepts reactions from the chat's permitted set;
  `✅` may be rejected in some chats. Because the default **clears** (always valid),
  this is avoided by default; if you switch to `done` mode and the emoji is
  rejected, the failure is swallowed and the 👀 simply remains.
- **No extra messages** — only `setMessageReaction` is used; no "typing…" text.
- **No PII in logs** — structured events log **chat type + emoji + error type only**,
  never message text, user text, tokens, or secrets.

Structured log events: `telegram_reaction_set`, `telegram_reaction_clear`,
`telegram_reaction_failed` (all debug-level).

## 5. Why private-only for V1

Group reactions are noisier (many members, notification semantics differ) and the
business value is highest in 1:1 sales DMs. V1 is private-only; groups are a
flag-gated opt-in we can validate separately.

## 6. Tests

`tests/unit/bot/test_telegram_reaction_micro_ux.py` (71 tests):

- flag OFF → zero API calls; no-cfg object → no-op;
- private enabled → processing reaction set with chat/message ids;
- clear vs done modes, mode override, configured/empty-emoji fallback;
- group no-op by default, reacts only when groups enabled; channel no-op;
- malformed message (None / no chat / no message_id) → no-op;
- `TelegramBadRequest` / `TelegramForbiddenError` / `TelegramRetryAfter` / generic
  all swallowed (never raise);
- logs contain only `chat_type`/`emoji`/`error_type` — no text/secret;
- default-OFF contract pinned against real `TelegramSettings`;
- source-pin: handlers import the helper and place 2× processing / 2× done /
  2× clear around the `_call_ai` path; reply text, stop/safety guard, and
  Unknown-Questions capture are unchanged; no "typing…" text added.

## 7. Rollout instructions

1. Merge with the flag **off** — zero behavior change in production.
2. On a **TEST bot** only, set `TELEGRAM_REACTIONS_ENABLED=true`, recreate the bot
   container, confirm `getMe` is the test bot, send a free-text question, and
   verify: 👀 appears on the user's message → reply arrives → reaction clears
   (or → ✅ if clear-on-reply is off); no errors in logs.
3. If satisfied, enable in production by setting the env flag (no code deploy
   needed beyond shipping this code). Keep `clear_on_reply=true` for the safest UX.

## 8. Rollback

Set `TELEGRAM_REACTIONS_ENABLED=false` (or remove it) and restart — the helper
becomes a no-op immediately. No DB changes, no migration, nothing else to undo.
Code-level rollback is a plain revert of this feature branch.

## 9. Future (after proof)

- Extend to deterministic slow paths (catalog resolve, operator handoff) and to
  other private handlers.
- Optional group support (flag already present).
- Optional `is_big` celebratory reaction on a closed deal.

## 10. Files

- `shared/config/settings.py` — `TelegramSettings` group + `settings.telegram`.
- `apps/bot/utils/reactions.py` — helper (`maybe_react_processing` /
  `maybe_react_done` / `maybe_clear_reaction`) + `apps/bot/utils/__init__.py`.
- `apps/bot/handlers/private/ai_support.py` — import + 6 paired calls around the
  two AI handlers' OpenAI path.
- `tests/unit/bot/test_telegram_reaction_micro_ux.py` — 71 tests.
