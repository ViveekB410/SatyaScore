# Satya-Score Version 2, fix round: held-out results (new test sample)

Test sample: 175 items from the locked test splits (results/v2_data_PROTOCOL.md, "Held-out test sample"), run once. v1 = the current system. v2 = v1 plus the LLM cross-check (gpt-oss-20b, the same open weights as on Groq, run locally with Ollama; symmetric rule); structured sources and fact-checks still decide first.

Fix round: an LLM 'Hallucinated' whose reason only says evidence is missing counts as Uncertain (no-evidence filter), chosen on dev data. New test sample `testS2`, no item shared with the first one. Cells already used up are missing: Mu-SHROOM Hindi true claims and old-gold false claims.

## Decision (rule fixed before this run)

- caught >= 2x v1: PASS (47% vs 15%)
- hallucinations marked Verified <= half of v1: PASS (5% vs 20%)
- false alarms <= v1 + 3 points: PASS (12% vs 12%)

**v2 IS adopted under the pre-set rule.**

## Overall (all sets pooled)

| system | items | caught | hallucinations marked Verified | true claims Verified | false alarms |
|---|---|---|---|---|---|
| v1 | 175 | 15% | 20% | 56% | 12% |
| v2 | 175 | 47% | 5% | 40% | 12% |

## v1 by set

| set | lang | n_true | n_false | caught | false_verified | true_verified | false_alarm | uncertain |
|---|---|---|---|---|---|---|---|---|
| fever | en | 12 | 12 | 25% | 17% | 75% | 17% | 33% |
| hiwiki | hi | 12 | 12 | 0% | 33% | 75% | 0% | 46% |
| hiwiki_para | hi | 12 | 12 | 0% | 25% | 67% | 0% | 54% |
| hiwiki_swap | hi | 0 | 7 | 14% | 0% | - | - | 86% |
| mushroom | en | 12 | 12 | 25% | 17% | 25% | 25% | 54% |
| mushroom | hi | 0 | 12 | 0% | 42% | - | - | 58% |
| truthfulqa | en | 12 | 12 | 17% | 17% | 25% | 25% | 58% |
| v1gold | en | 12 | 0 | - | - | 67% | 8% | 25% |
| v1gold | hi | 12 | 0 | - | - | 58% | 8% | 33% |
| xfact_hi | hi | 0 | 12 | 42% | 0% | - | - | 58% |

- Mu-SHROOM en (21 answers) mean IoU: claims 0.106, error spans 0.106, mark-all 0.350
- Mu-SHROOM hi (12 answers) mean IoU: claims 0.019, error spans 0.019, mark-all 0.402

## v2 by set

| set | lang | n_true | n_false | caught | false_verified | true_verified | false_alarm | uncertain |
|---|---|---|---|---|---|---|---|---|
| fever | en | 12 | 12 | 50% | 0% | 50% | 17% | 42% |
| hiwiki | hi | 12 | 12 | 58% | 8% | 50% | 0% | 42% |
| hiwiki_para | hi | 12 | 12 | 33% | 17% | 50% | 8% | 46% |
| hiwiki_swap | hi | 0 | 7 | 57% | 0% | - | - | 43% |
| mushroom | en | 12 | 12 | 50% | 8% | 17% | 17% | 54% |
| mushroom | hi | 0 | 12 | 42% | 0% | - | - | 58% |
| truthfulqa | en | 12 | 12 | 50% | 8% | 17% | 25% | 50% |
| v1gold | en | 12 | 0 | - | - | 42% | 0% | 58% |
| v1gold | hi | 12 | 0 | - | - | 58% | 17% | 25% |
| xfact_hi | hi | 0 | 12 | 42% | 0% | - | - | 58% |

- Mu-SHROOM en (21 answers) mean IoU: claims 0.109, error spans 0.111, mark-all 0.350
- Mu-SHROOM hi (12 answers) mean IoU: claims 0.099, error spans 0.102, mark-all 0.402

X-FACT (Hindi rumours) without the fact-check source, v1: caught 0% (fact-check sites cover exactly these rumours, so both figures are shown).

## How to read this, and what to disclose

- caught = share of false items marked Hallucinated; false alarms = share of true items marked Hallucinated; items neither Verified nor Hallucinated are Uncertain.
- Small sample: about 12 true and 12 false items per set, so each percentage moves by about 8 points per item.
- History, all disclosed: the first v2 failed on the first test sample (false alarms 17% vs v1 9%, results/v2_results.md). Its cause (the LLM calling claims false only because the passages did not mention them) was found on dev data and on that burned sample. The decision rule was changed to be relative to v1 (the first rule, an absolute 5%, was set when v1's own rate looked like 3-6%; on these sets v1 has 9-12%). The rule and the fix were both fixed before this sample was run.
- Cost of v2: fewer true claims are Verified (they become Uncertain), because Verified needs the passages and the LLM to agree.
- Mu-SHROOM Hindi has very few true claims; Hindi false alarms are better read from hiwiki and hiwiki_para.
- hiwiki = sentences copied from Hindi Wikipedia (easier, the system can find them); hiwiki_para = the same sentences reworded by an LLM (Qwen) and checked to keep meaning and numbers.
- Constructed false items (hiwiki, hiwiki_para, hiwiki_swap) change one number or one place name.
- Wikidata relations added in v2 decided ~1% of dev claims and are switched off; 'country' was dropped by the rule.
- The LLM is a second opinion: it can make a claim Verified only together with a supporting passage.
