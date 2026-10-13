# Satya-Score Version 2: held-out results

Test sample: 201 items from the locked test splits (results/v2_data_PROTOCOL.md, "Held-out test sample"), run once. v1 = the current system. v2 = v1 plus the LLM cross-check (gpt-oss-20b, the same open weights as on Groq, run locally with Ollama; symmetric rule); structured sources and fact-checks still decide first.

Provider check: on the 17 claims both answered, the local run (Ollama) and Groq gave the same verdict 82% of the time.

## Overall (all sets pooled)

| system | items | caught | hallucinations marked Verified | true claims Verified | false alarms |
|---|---|---|---|---|---|
| v1 | 201 | 20% | 31% | 56% | 9% |
| v2 | 201 | 58% | 8% | 41% | 17% |

## v1 by set

| set | lang | n_true | n_false | caught | false_verified | true_verified | false_alarm | uncertain |
|---|---|---|---|---|---|---|---|---|
| fever | en | 12 | 12 | 17% | 25% | 50% | 8% | 50% |
| hiwiki | hi | 12 | 12 | 8% | 25% | 83% | 0% | 42% |
| hiwiki_para | hi | 12 | 12 | 17% | 8% | 75% | 0% | 50% |
| hiwiki_swap | hi | 0 | 12 | 17% | 25% | - | - | 58% |
| mushroom | en | 12 | 12 | 8% | 42% | 42% | 0% | 54% |
| mushroom | hi | 11 | 12 | 8% | 33% | 45% | 36% | 39% |
| truthfulqa | en | 12 | 12 | 42% | 42% | 33% | 33% | 25% |
| v1gold | en | 12 | 8 | 0% | 88% | 58% | 0% | 30% |
| v1gold | hi | 12 | 2 | 0% | 100% | 58% | 0% | 36% |
| xfact_hi | hi | 0 | 12 | 58% | 0% | - | - | 42% |

- Mu-SHROOM en (20 answers) mean IoU: claims 0.086, error spans 0.086, mark-all 0.302
- Mu-SHROOM hi (19 answers) mean IoU: claims 0.045, error spans 0.045, mark-all 0.344

## v2 by set

| set | lang | n_true | n_false | caught | false_verified | true_verified | false_alarm | uncertain |
|---|---|---|---|---|---|---|---|---|
| fever | en | 12 | 12 | 75% | 0% | 33% | 17% | 38% |
| hiwiki | hi | 12 | 12 | 67% | 8% | 67% | 0% | 29% |
| hiwiki_para | hi | 12 | 12 | 83% | 0% | 50% | 17% | 25% |
| hiwiki_swap | hi | 0 | 12 | 58% | 0% | - | - | 42% |
| mushroom | en | 12 | 12 | 33% | 17% | 33% | 25% | 46% |
| mushroom | hi | 11 | 12 | 50% | 8% | 9% | 36% | 48% |
| truthfulqa | en | 12 | 12 | 50% | 0% | 25% | 25% | 50% |
| v1gold | en | 12 | 8 | 0% | 50% | 58% | 8% | 40% |
| v1gold | hi | 12 | 2 | 0% | 50% | 50% | 8% | 43% |
| xfact_hi | hi | 0 | 12 | 100% | 0% | - | - | 0% |

- Mu-SHROOM en (20 answers) mean IoU: claims 0.060, error spans 0.060, mark-all 0.302
- Mu-SHROOM hi (19 answers) mean IoU: claims 0.134, error spans 0.112, mark-all 0.344

X-FACT (Hindi rumours) without the fact-check source, v1: caught 17% (fact-check sites cover exactly these rumours, so both figures are shown).

## How to read this, and what to disclose

- caught = share of false items marked Hallucinated; false alarms = share of true items marked Hallucinated; items neither Verified nor Hallucinated are Uncertain.
- Small sample: about 12 true and 12 false items per set, so each percentage moves by about 8 points per item.
- v2 did NOT meet the pre-set dev rule on false alarms (7% on the dev sample, limit 5%); it is reported anyway.
- Cost of v2: fewer true claims are Verified (they become Uncertain), because Verified needs the passages and the LLM to agree.
- Mu-SHROOM Hindi has very few true claims; Hindi false alarms are better read from hiwiki and hiwiki_para.
- hiwiki = sentences copied from Hindi Wikipedia (easier, the system can find them); hiwiki_para = the same sentences reworded by an LLM (Qwen) and checked to keep meaning and numbers.
- Constructed false items (hiwiki, hiwiki_para, hiwiki_swap) change one number or one place name.
- Wikidata relations added in v2 decided ~1% of dev claims and are switched off; 'country' was dropped by the rule.
- The LLM is a second opinion: it can make a claim Verified only together with a supporting passage.
