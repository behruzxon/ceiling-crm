# Step CG — AI Button UX + Menu Polish

**Date**: 2026-05-27
**Branch**: feature/packages-update

## New Commands

| Command | Description | Handler |
|---------|-------------|---------|
| /ai_help | Show AI capabilities and examples | cmd_ai_help |
| /ai_reset | Clear AI conversation memory | cmd_ai_reset |

## New Quick Buttons (AI Keyboard)

| Button | Text | Action |
|--------|------|--------|
| Narx | "💰 Narx" | Prompt for area input |
| Katalog | "📂 Katalog" | Show catalog list |
| Operator | "👨‍💼 Operator" | Operator handoff prompt |
| Reset | "🔄 Reset" | Clear AI memory |
| Yordam | "❓ Yordam" | Show help text |
| Menyu | "⬅️ Menyu" | Exit AI mode |

Keyboard layout: 3 rows x 2 columns.

## UX Copy

### AI Mode Entry (returning user)
Personalized greeting with enhanced keyboard (6 buttons).

### AI Help (/ai_help or "Yordam" button)
Lists 5 capabilities: narx, dizayn, katalog, operator, xotira.
Shows 4 examples. Warns: "Aniq narx o'lchovdan keyin tasdiqlanadi."

### AI Reset (/ai_reset or "Reset" button)
Clears conversation history (ai_conversations table).
Clears FSM state, re-enters AI mode.
Does NOT delete CRM contact/messages/audit data.
Success: "AI suhbat xotirasi tozalandi."

### Operator Handoff
Asks for phone. No fake ETA. No "hozir qo'ng'iroq qiladi" promise.
Copy: "Operator bilan bog'lanishga yordam beraman..."

### Rate Limit
Friendly text: "Kunlik AI so'rovlar limiti tugadi. Ertaga yana urinib ko'ring..."

## Safety Preserved

- No-send behavior: unchanged
- Stop handling: unchanged
- Double reply prevention: unchanged
- Rate limit: unchanged (100/day)
- Injection firewall: unchanged
- Phone redaction: unchanged
- All flags: NOT ENABLED
- Stage 1 LOG_ONLY: NOT APPLIED
- Quick buttons handled BEFORE general AI question handler (no double-reply)

## Next Step

Step CH — Price Calculator Integration
