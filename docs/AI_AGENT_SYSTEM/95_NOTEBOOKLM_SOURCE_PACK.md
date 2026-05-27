# NotebookLM Source Pack — Vashpotolok AI Knowledge Review

## Project Overview

Vashpotolok is an enterprise Telegram bot CRM for a stretch ceiling business in Kashkadarya, Uzbekistan. The platform includes a Telegram bot (aiogram 3.7), web CRM dashboard (FastAPI), AI sales assistant (OpenAI GPT-4o), and an agent pipeline for automated lead management.

**Current status:** Development complete, NOT deployed, Stage 1 LOG_ONLY NOT applied, all safety flags OFF by default.

## Business Summary

- Company: Vashpotolok (natijnoy potolok / stretch ceilings)
- Location: Kashkadarya region, Uzbekistan
- Experience: 6+ years (since 2018), 1000+ completed projects
- Warranty: 15 years (formal document)
- Service: Free measurement, 1-2 day installation
- Hours: 09:00-20:00 daily
- Languages: Uzbek (primary), Russian (supported)

## Bot Commands (10 registered)

| Command | Description |
|---------|-------------|
| /start | Start bot / deep-link routing |
| /menu | Show main menu |
| /catalog | Ceiling design catalog |
| /price | Price calculator |
| /order | Place order |
| /help | Help |
| /cancel | Cancel current action |
| /ai_off | Exit AI mode |
| /ai_help | AI capabilities list |
| /ai_reset | Clear AI conversation memory |

## Main Menu Buttons (9)

| Button | Action |
|--------|--------|
| Zakaz berish | Start order flow (name -> phone -> district -> category -> area -> location) |
| Narx kalkulyator | Price calculator (length -> width -> design -> quote) |
| Katalog | Design catalog browser (10 types with Telegram channel links) |
| Tayyor paketlar | Ready packages (Standard/Premium/VIP with inline actions) |
| Buyurtmalarim | My orders (read-only, order history + status) |
| Operator | Operator contact (confirmation -> phone share -> admin alert) |
| Chegirmalar | Current promotions (inline CTA buttons) |
| AI yordam | AI sales assistant mode (Madina) |
| Biz haqimizda | About company (inline CTA buttons) |

## AI Mode Buttons (6)

| Button | Action |
|--------|--------|
| Narx | Prompt for room dimensions ("5x4 yoki 20 kv") |
| Katalog | Show catalog list keyboard |
| Operator | Operator handoff with phone request |
| Reset | Clear AI conversation memory |
| Yordam | Show AI capabilities and examples |
| Menyu | Exit AI mode, return to main menu |

## Catalog Flow

- 10 design types: Gulli, Odnotonniy, Mramor, Qora naqsh UF, Hi-tech, Kosmos, Osmon, Oshxona, Naqsh ramka, Naqsh oq
- Each type links to a Telegram channel post with photos
- No media sent directly from bot (URL buttons only)
- No CRM write on catalog view
- Journey event OPENED_CATALOG tracked

## Pricing Flow

Customer-facing prices (AI display):
- Adnatonniy/Matt: 80,000 UZS/m2
- Hi Tech / Mramor / Naqsh / Kosmos / Osmon: 120,000 UZS/m2
- Gulli: 130,000 UZS/m2
- Qora UF: 140,000 UZS/m2

Discount tiers:
- Over 20 m2: 5% automatic
- Over 40 m2: 10% automatic

Formula: Total = Area (m2) x Design Price - Discount

IMPORTANT: These are TAXMINIY (approximate) prices. Final price is confirmed only after measurement.

Internal quote prices are higher (120k-300k range) and used in admin-side calculations only.

## Order Flow (6 steps)

1. Name (2-128 chars, validated)
2. Phone (Uzbek format +998XX..., validated)
3. District (from 13 Kashkadarya districts)
4. Category (ceiling type selection via inline buttons)
5. Area (dimensions: "5x4" or "20 m2", can skip)
6. Location (Telegram location share, can skip)

Result: Lead created in CRM, pipeline stage QUOTE, admin group notified.

## Operator Handoff Flow

- User clicks "Operator" -> bot asks confirmation
- User confirms -> bot asks for phone (contact share or manual)
- Phone shared -> admin receives alert with user info
- No queue system, no ETA, no automatic callback
- Bot says: "Operator bilan bog'lanishga yordam beraman. Telefon raqamingizni yuboring."
- No fake promise like "hozir qo'ng'iroq qiladi"

## Measurement Lead Flow (4 steps)

1. Name -> 2. Phone -> 3. Location/address -> 4. Preferred time
- Creates lead with source=DEEPLINK
- Admin notified with measurement request details
- AI scoring updated if available

## Payment Flow (2 steps)

1. Amount (positive integer)
2. Proof (photo or document)
- Payment created with status PENDING
- Admin receives approve/reject buttons
- No external payment gateway (manual process)

## CRM / Lead Scoring

Lead score: 0-100 (Redis-backed, 30-day TTL)
- Score >= 60: HOT
- Score >= 30: WARM
- Score < 30: COLD

Score signals:
- Phone captured: +40
- Measurement request: +25
- Price query: +15
- District provided: +10
- Catalog view: +5
- Delay objection: -10
- Angry objection: -5

CRM writes: lead_temperature, closing_confidence, next_follow_up_at, phone, area, district

## Safety Rules

1. Final price is approximate (taxminiy). Aniq narx faqat o'lchovdan keyin tasdiqlanadi.
2. No fake discounts. Discount tiers are automatic (5% >20m2, 10% >40m2).
3. No same-day promises ("bugun qilamiz" is forbidden unless explicitly configured).
4. No fake ETA for operator callback.
5. No "eng arzon narx bizda" claim.
6. Stop request ("kerak emas", "stop", "yozmang") immediately disables follow-ups.
7. Phone numbers masked in memory/traces.
8. Prompt injection blocked (14 regex patterns).
9. AI output leak guard (15 marker phrases checked).
10. Rate limit: 100 AI calls per user per day.

## Forbidden AI Claims

The AI (Madina) must NEVER say:
- "Yozib qo'ydim" (I wrote it down) — only FSM can record
- "Operator bog'lanadi" (Operator will contact you) — no automated callback
- "Usta boradi" (Master will visit) — only via measurement flow
- "100% kafolat beramiz" — warranty is 15 years, not 100%
- "Eng arzon narx" — price depends on design and area
- "Aniq narx aytaman" — only approximate until measurement
- "Bugun qilamiz" — no same-day guarantee

## Current Gaps

1. Bot button behaviors not described in AI system prompt
2. Package details (Standard/Premium/VIP) not in knowledge base
3. Order flow steps not explained in uz.md
4. No dynamic promotions in knowledge base
5. Catalog has no direct media (URL links only)
6. Operator handoff has no queue or status tracking
7. No photo/voice AI analysis

## Questions for NotebookLM Review

1. Are there inconsistencies between pricing in uz.md and system_prompt.py?
2. Are the 9 FAQ answers in uz.md sufficient for common customer objections?
3. Should the AI know about bot button behaviors to guide users better?
4. Is the operator handoff copy safe (no false promises)?
5. Are there missing objection types that Uzbek customers commonly raise?
6. Should package descriptions (Standard/Premium/VIP) be added to AI knowledge?
7. Is the discount explanation clear enough for customers?
8. Are there cultural or regional factors the AI should know about Kashkadarya?

## DO NOT UPLOAD TO NOTEBOOKLM

- .env files or any environment configuration
- Bot token (BOT_TOKEN)
- OpenAI API key (OPENAI_API_KEY)
- Database connection URLs
- Admin user IDs or group IDs
- Raw customer phone numbers or messages
- Production database exports
- Session secrets or CSRF tokens
- Redis connection strings
