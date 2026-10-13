# Satya-Score Version 2, last round: held-out results (third test sample)

Test sample: 162 items from the locked test splits (results/v2_data_PROTOCOL.md, "Held-out test sample"), run once. v1 = the current system. v2 = v1 plus the LLM cross-check (gpt-oss-20b, the same open weights as on Groq, run locally with Ollama; symmetric rule); structured sources and fact-checks still decide first.

Last round: v3 = the fix round plus the second reading (for claims left Uncertain although one side leans true, the LLM reads all 10 retrieved passages, passages only; Verified if they state the claim). Chosen on the burned testS and testS2. Third test sample `testS3`, no item shared with the earlier two; hiwiki_swap is used up.

## Decision (rule fixed before this run)

- caught >= 2x v1: FAIL (37% vs 19%)
- hallucinations marked Verified <= half of v1: PASS (6% vs 17%)
- false alarms <= v1 + 3 points: FAIL (14% vs 5%)
- true claims Verified >= v1 - 5 points: PASS (64% vs 65%)

**v3 is NOT adopted under the pre-set rule.**

## Overall (all sets pooled)

| system | items | caught | hallucinations marked Verified | true claims Verified | false alarms |
|---|---|---|---|---|---|
| v1 | 162 | 19% | 17% | 65% | 5% |
| v3 | 162 | 37% | 6% | 64% | 14% |

## v1 by set

| set | lang | n_true | n_false | caught | false_verified | true_verified | false_alarm | uncertain |
|---|---|---|---|---|---|---|---|---|
| fever | en | 12 | 12 | 42% | 0% | 75% | 0% | 42% |
| hiwiki | hi | 12 | 12 | 0% | 33% | 92% | 0% | 38% |
| hiwiki_para | hi | 12 | 12 | 8% | 17% | 67% | 0% | 54% |
| mushroom | en | 12 | 12 | 8% | 25% | 67% | 17% | 42% |
| mushroom | hi | 0 | 12 | 0% | 33% | - | - | 67% |
| truthfulqa | en | 12 | 12 | 25% | 8% | 25% | 17% | 62% |
| v1gold | en | 9 | 0 | - | - | 67% | 0% | 33% |
| v1gold | hi | 9 | 0 | - | - | 67% | 0% | 33% |
| xfact_hi | hi | 0 | 12 | 50% | 0% | - | - | 50% |

- Mu-SHROOM en (20 answers) mean IoU: claims 0.104, error spans 0.104, mark-all 0.306
- Mu-SHROOM hi (12 answers) mean IoU: claims 0.000, error spans 0.000, mark-all 0.293

## v3 by set

| set | lang | n_true | n_false | caught | false_verified | true_verified | false_alarm | uncertain |
|---|---|---|---|---|---|---|---|---|
| fever | en | 12 | 12 | 67% | 0% | 67% | 17% | 25% |
| hiwiki | hi | 12 | 12 | 33% | 8% | 83% | 8% | 33% |
| hiwiki_para | hi | 12 | 12 | 42% | 8% | 50% | 8% | 46% |
| mushroom | en | 12 | 12 | 17% | 8% | 58% | 17% | 50% |
| mushroom | hi | 0 | 12 | 17% | 8% | - | - | 75% |
| truthfulqa | en | 12 | 12 | 25% | 8% | 33% | 33% | 50% |
| v1gold | en | 9 | 0 | - | - | 78% | 11% | 11% |
| v1gold | hi | 9 | 0 | - | - | 89% | 0% | 11% |
| xfact_hi | hi | 0 | 12 | 58% | 0% | - | - | 42% |

- Mu-SHROOM en (20 answers) mean IoU: claims 0.119, error spans 0.119, mark-all 0.306
- Mu-SHROOM hi (12 answers) mean IoU: claims 0.096, error spans 0.153, mark-all 0.293

X-FACT (Hindi rumours) without the fact-check source, v1: caught 25% (fact-check sites cover exactly these rumours, so both figures are shown).

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
