# AI Knowledge Update Plan — From NotebookLM Review

Template for tracking findings from NotebookLM review and deciding what to apply.

## How to Use

1. Run NotebookLM review prompts (doc 96)
2. For each finding, add a row below
3. Mark accepted/rejected with reason
4. Track implementation in Step CJ

## Findings Table

| # | Finding | Source Prompt | Accepted? | Reason | Target File | Risk | Tests Needed | Status |
|---|---------|-------------|-----------|--------|-------------|------|--------------|--------|
| 1 | (example) Missing FAQ about payment methods | B) FAQ Generation | Accepted | Common customer question | shared/knowledge/uz.md | LOW | test_uz_md_content | TODO |
| 2 | (example) Discount can be misunderstood | D) Pricing Safety | Accepted | Needs clearer wording | apps/bot/ai/system_prompt.py | LOW | test_prompt_discount | TODO |
| 3 | | | | | | | | |
| 4 | | | | | | | | |
| 5 | | | | | | | | |

## Decision Criteria

**Accept if:**
- Fixes a real knowledge gap customers encounter
- Improves safety (prevents false claims)
- Does not change existing bot behavior
- Can be tested
- Low risk

**Reject if:**
- Requires behavior change (save for separate step)
- Adds complexity without clear user benefit
- Contradicts existing business rules
- Requires external API or flag change
- Cannot be verified with tests

## Target Files for Updates

| File | What can be updated | What must NOT change |
|------|--------------------|--------------------|
| shared/knowledge/uz.md | FAQ entries, descriptions | Pricing numbers, company facts |
| apps/bot/ai/system_prompt.py | Response rules, examples | Core identity, safety rules |
| apps/bot/handlers/private/ai_states.py | Help text, prompts | Button texts, keyboard structure |
| apps/bot/handlers/private/ai_scoring.py | Objection replies | Score deltas, keywords |

## Risk Assessment

- LOW: Text/wording updates only
- MEDIUM: New detection keywords or response logic
- HIGH: Behavior changes, new features

## Implementation Tracking

After accepting findings:
1. Create branch or continue on feature/packages-update
2. Apply text changes to target files
3. Add/update tests
4. Run full regression
5. Update this plan with DONE status

## Notes

- This document does NOT claim any changes have been applied
- All findings are proposals until explicitly accepted and implemented
- Stage 1 LOG_ONLY is NOT applied
- Production is NOT deployed
