# NotebookLM Review Prompts — Vashpotolok AI

Use these prompts in NotebookLM after uploading the source pack.

---

## A) Knowledge Gap Analysis

```
Analyze the Vashpotolok AI knowledge base. Identify:
1. What information is missing that a stretch ceiling customer in Uzbekistan would commonly ask?
2. Are there any inconsistencies between the pricing tables and FAQ answers?
3. What objection types are not covered?
4. What regional or cultural context about Kashkadarya is missing?
List each gap with severity (critical/medium/low) and a suggested fix.
```

## B) FAQ Generation

```
Based on the Vashpotolok business knowledge, generate 15 additional FAQ questions and answers in Uzbek that a typical customer might ask about:
- Installation process
- Material quality and safety
- Pricing and payment options
- Warranty claims
- Seasonal considerations
- Comparison with other ceiling types
Format: Q: [question in Uzbek] / A: [answer in Uzbek, 2-3 sentences max]
```

## C) Bot Button Behavior Validation

```
Review the bot button map (9 main menu + 6 AI mode buttons). For each button:
1. Is the user flow clear and complete?
2. Are there dead-end states where the user gets stuck?
3. Is the fallback behavior safe (no crash, no raw error)?
4. Does the AI know what each button does so it can guide users?
Create a table: Button | Flow complete? | Dead-end risk? | AI knows about it?
```

## D) Pricing Safety Review

```
Review the pricing rules in the knowledge base:
1. Is it clear that prices are approximate (taxminiy)?
2. Can the AI accidentally promise a final price?
3. Are discount tiers clearly explained without making false claims?
4. Is there a risk of the AI inventing discounts beyond 5%/10% tiers?
5. Are add-on prices (LED, cornice, spots) safely communicated?
Rate each area: SAFE / NEEDS_FIX / CRITICAL
```

## E) Operator Handoff Safety Review

```
Review the operator handoff flow:
1. Does the bot make any promise about when the operator will call?
2. Is there any fake ETA or "darhol" (immediately) claim?
3. What happens if no operator is available?
4. Is the phone collection process safe and clear?
5. What should the AI say if the user asks "qachon qo'ng'iroq qilasiz?"
Suggest safe Uzbek response templates for each scenario.
```

## F) Catalog / Order Flow Clarity

```
Review the catalog and order flows:
1. Is the catalog browsing experience clear to users?
2. Are design type names consistent across pricing, catalog, and AI prompts?
3. Is the order flow (6 steps) well-explained to users?
4. What happens if a user skips optional steps?
5. Are there confusing transitions between flows (e.g., catalog -> price -> order)?
Suggest improvements that don't change existing behavior.
```

## G) Uzbek / Russian Response Quality

```
Review the AI response templates and knowledge base text:
1. Is the Uzbek language natural and conversational (not robotic)?
2. Are there any grammar or spelling issues in the Uzbek text?
3. Does the AI handle Cyrillic Uzbek input correctly?
4. Are Russian customer messages handled appropriately?
5. Is the response length appropriate (3-5 sentences)?
Provide 5 example improved responses for common scenarios.
```

## H) Final AI Teaching Summary

```
Based on your full review, create a concise AI training summary:
1. Top 5 knowledge gaps to fill
2. Top 5 safety rules to reinforce
3. Top 5 response improvements
4. Top 3 new FAQ entries needed
5. Top 3 flow improvements
Format as a checklist that can be directly applied to the AI system prompt.
```
