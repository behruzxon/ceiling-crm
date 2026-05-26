# Skill: Telegram Sales Flow UX

Design and review Telegram bot sales flows for CeilingCRM. These rules ensure high conversion, natural feel, and respectful user experience.

## Message Length

- Maximum 2-4 sentences per message
- If you need to convey more, split into multiple messages or use expandable sections
- Price breakdowns can be longer but must be well-formatted with line breaks
- Never send a wall of text

## CTA (Call-to-Action) Rules

- Every message must end with a clear CTA: either a button or a direct question
- CTA hierarchy (strongest to weakest):
  1. **Order** — "Buyurtma berish", "Zamov berish"
  2. **Operator** — "Operator bilan bog'lanish"
  3. **Catalog** — "Katalogni ko'rish"
  4. **Calculator** — "Narx hisoblash"
  5. **Info** — "Batafsil ma'lumot"
- Never end a message without guiding the user to a next step
- Primary CTA should be visually distinct (first button, or the only button in its row)

## Button-First UX

- Prefer inline keyboards over free-text input whenever possible
- Use ReplyKeyboard only for persistent actions (main menu, back)
- Inline button labels must be short (max 20 characters) and action-oriented
- Max 3 buttons per row for inline keyboards
- Max 8 buttons total per message (2-3 rows of 2-3)
- Every keyboard must include an escape route (back or cancel)

## Language Guidelines

- **Primary language**: Uzbek (Latin script)
- **Secondary**: Russian (for users who switch)
- Detect language from user's first message and persist in FSM/profile
- Use natural conversational Uzbek, not formal/literary
- Common phrases:
  - Greeting: "Assalomu alaykum!" (not "Salom")
  - Thanks: "Rahmat!"
  - Confirmation: "Ajoyib!" or "Zo'r!"
  - Apology: "Kechirasiz"
  - Farewell: "Hayrli kun!"

## Tone

- Friendly and professional — like a knowledgeable sales consultant
- Never robotic or template-like
- Never aggressive or pushy
- Show empathy for objections ("Tushunaman, narx muhim masala")
- Celebrate user decisions ("Ajoyib tanlov!")
- Be helpful even when the user is not buying ("Savollaringiz bo'lsa, yozing")

## Anti-Spam

- Never send more than 1 unsolicited message per interaction
- Respect explicit stop signals: "kerak emas", "rahmat, kerak emas", "stop", "yoq"
- Respect implicit signals: user not replying for 24h+ means reduce frequency
- Cooldown: minimum 1 hour between automated messages
- Maximum 5 automated messages per user total (across all follow-up types)
- When in doubt, don't send

## Escape Routes

- Every flow must have a way out:
  - Inline keyboard: include "Orqaga" (back) or "Bekor qilish" (cancel) button
  - FSM flow: handle /cancel command in every state
  - Main menu: always accessible via "Bosh sahifa" button
- Back button returns to previous step, not to main menu (unless it's step 1)
- Cancel button clears FSM state and returns to main menu

## Formatting Rules

### Emojis
- 1-2 per message, relevant to content
- Common usage: "shiftli potolok" (no emoji needed), price (💰), area (📐), phone (📞), hot lead (🔥), order (✅)
- Never use more than 3 emojis in one message
- Never use emojis in formal/serious contexts (errors, cancellations)

### Phone Numbers
- Always format as clickable: wrap in a message that includes the raw number
- Example: "📞 +998 90 123 45 67"
- Store in E.164 format internally: +998901234567

### Usernames
- Always format as clickable: @username
- Example: "Operator: @vashpotolok_operator"

### Prices
- Use thousands separator: "1,500,000 so'm" (not "1500000")
- Always include currency: "so'm" or "UZS"
- For ranges: "1,200,000 — 1,800,000 so'm"
- Round to nearest 1,000 (no decimals)

### Areas
- Always include unit: "25 m²" (not just "25")
- Use the actual squared symbol: m² (not m2)

## Flow Design Checklist

When designing or reviewing a sales flow:

1. Can the user complete the entire flow in under 2 minutes?
2. Is every step necessary? Remove any that don't add value
3. Does the user know where they are in the flow? (step indicators help)
4. Can the user go back to correct a mistake?
5. Can the user exit at any point?
6. Is the final CTA clear and compelling?
7. Does the flow capture the minimum data needed? (don't ask for info you won't use)
8. Is the confirmation step clear about what happens next?
9. Will the user receive a follow-up? Is that expectation set?
10. Does the flow feel like talking to a helpful person, not filling out a form?
