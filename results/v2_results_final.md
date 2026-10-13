# Satya-Score Version 2: final held-out results (large test sample)

Test sample: 620 items from the locked test splits (results/v2_data_PROTOCOL.md, "Held-out test sample"), run once. v1 = the current system. v2 = v1 plus the LLM cross-check (gpt-oss-20b, the same open weights as on Groq, run locally with Ollama; symmetric rule); structured sources and fact-checks still decide first.

Final: v4a = v3 plus two safeguards against false alarms: a passage 'contradiction' alone never flags a claim (the LLM must say false), and a claim about to be flagged is first read against all 10 retrieved sources (if they state it, it is Uncertain). Chosen on the three burned samples (~510 items). Large test sample `testL`: 620 items, none used before; hiwiki_swap and the old gold set are used up, Mu-SHROOM Hindi has false items only.

## Decision (rule fixed before this run)

- caught >= 2x v1: FAIL (47% vs 25%)
- hallucinations marked Verified <= half of v1: PASS (6% vs 22%)
- false alarms <= v1 + 3 points: PASS (13% vs 11%)
- true claims Verified >= v1 - 5 points: PASS (57% vs 56%)

**v4a is NOT adopted under the pre-set rule.**

## Overall (all sets pooled)

| system | items | caught | hallucinations marked Verified | true claims Verified | false alarms |
|---|---|---|---|---|---|
| v1 | 620 | 25% | 22% | 56% | 11% |
| v4a | 620 | 47% | 6% | 57% | 13% |

## v1 by set

| set | lang | n_true | n_false | caught | false_verified | true_verified | false_alarm | uncertain |
|---|---|---|---|---|---|---|---|---|
| fever | en | 60 | 60 | 37% | 20% | 72% | 13% | 29% |
| hiwiki | hi | 38 | 38 | 3% | 13% | 95% | 0% | 45% |
| hiwiki_para | hi | 36 | 36 | 28% | 33% | 78% | 3% | 29% |
| mushroom | en | 52 | 60 | 13% | 23% | 40% | 15% | 54% |
| mushroom | hi | 0 | 60 | 7% | 38% | - | - | 55% |
| truthfulqa | en | 60 | 60 | 17% | 27% | 15% | 18% | 62% |
| xfact_hi | hi | 0 | 60 | 67% | 2% | - | - | 32% |

- Mu-SHROOM en (72 answers) mean IoU: claims 0.114, error spans 0.114, mark-all 0.307
- Mu-SHROOM hi (52 answers) mean IoU: claims 0.010, error spans 0.010, mark-all 0.318

## v4a by set

| set | lang | n_true | n_false | caught | false_verified | true_verified | false_alarm | uncertain |
|---|---|---|---|---|---|---|---|---|
| fever | en | 60 | 60 | 62% | 5% | 67% | 7% | 30% |
| hiwiki | hi | 38 | 38 | 39% | 5% | 87% | 0% | 34% |
| hiwiki_para | hi | 36 | 36 | 47% | 0% | 78% | 11% | 32% |
| mushroom | en | 52 | 60 | 20% | 15% | 40% | 15% | 55% |
| mushroom | hi | 0 | 60 | 45% | 5% | - | - | 50% |
| truthfulqa | en | 60 | 60 | 43% | 8% | 28% | 27% | 47% |
| xfact_hi | hi | 0 | 60 | 70% | 2% | - | - | 28% |

- Mu-SHROOM en (72 answers) mean IoU: claims 0.172, error spans 0.184, mark-all 0.307
- Mu-SHROOM hi (52 answers) mean IoU: claims 0.097, error spans 0.189, mark-all 0.318

X-FACT (Hindi rumours) without the fact-check source, v1: caught 5% (fact-check sites cover exactly these rumours, so both figures are shown).

## How to read this, and what to disclose

- caught = share of false items marked Hallucinated; false alarms = share of true items marked Hallucinated; items neither Verified nor Hallucinated are Uncertain.
- Up to 60 true and 60 false items per set, so each percentage moves by about 2-3 points per item.
- History, all disclosed: the first v2 failed on the first test sample (false alarms 17% vs v1 9%, results/v2_results.md). Its cause (the LLM calling claims false only because the passages did not mention them) was found on dev data and on that burned sample. The decision rule was changed to be relative to v1 (the first rule, an absolute 5%, was set when v1's own rate looked like 3-6%; on these sets v1 has 9-12%). The rule and the fix were both fixed before this sample was run.
- Cost of v2: fewer true claims are Verified (they become Uncertain), because Verified needs the passages and the LLM to agree.
- Mu-SHROOM Hindi has very few true claims; Hindi false alarms are better read from hiwiki and hiwiki_para.
- hiwiki = sentences copied from Hindi Wikipedia (easier, the system can find them); hiwiki_para = the same sentences reworded by an LLM (Qwen) and checked to keep meaning and numbers.
- Constructed false items (hiwiki, hiwiki_para, hiwiki_swap) change one number or one place name.
- Wikidata relations added in v2 decided ~1% of dev claims and are switched off; 'country' was dropped by the rule.
- The LLM is a second opinion: it can make a claim Verified only together with a supporting passage.
