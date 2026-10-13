# Version 2 evaluation data: protocol (fixed 2026-10-12, before any v2 system result is computed)

Replaces the manual relabelling planned in `relabel/PROTOCOL.md`. The team decided not to do new manual
annotation, and the calibration round had returned copied sheets, so independent labels were not
available. All labels below either come from public, human-labelled datasets or are true by construction.
Builder: `v2data/build_eval_sets.py`. Every set has a **dev** part (tuning, model selection, thresholds) and
a **locked test** part (run once, for the final v1-against-v2 comparison).

## 1. Mu-SHROOM (SemEval-2025 Task 3), Hindi and English. CC BY 4.0
- Answers: validation (50 HI, 50 EN) = dev; test (150 HI, 154 EN) = test.
- **Claim labels by a fixed mapping:** each answer is split with the current extractor.
  - A claim is **Hallucinated** if its character span overlaps a gold hard-label span by at least
    **3 characters**.
  - A claim is **true** if it overlaps no gold span at all.
  - Claims with 1–2 overlapping characters are dropped as ambiguous.
- The span-level task measures (IoU, Spearman) stay as reported in `public_benchmarks.md`.

## 2. FEVER paper_dev. CC BY-SA 3.0
- Test = the v1 sample (150 SUPPORTS + 150 REFUTES, seed 20261010).
- Dev = a new 150 + 150 sample with seed 20261013, **disjoint** from the test sample.
- SUPPORTS = true, REFUTES = false; NOT ENOUGH INFO is excluded.
- Caveat: the labels refer to Wikipedia of 2017.

## 3. X-FACT, Hindi part (utahnlp/x-fact). MIT
- dev split (112) = dev; test split (170) = test. Every item is false, mostly false, or partly
  true/misleading, so all are counted as **not true**.
- **Measures detection only** (there are no true items).
- These are published fact-checked rumours, so the fact-check source can look them up directly. Results
  are reported **with and without** the fact-check source; the without-figure is the main one.

## 4. Hindi Wikipedia, constructed (true by construction)
- **Sampling:** random Hindi Wikipedia articles (MediaWiki random API, main namespace) that are not among
  the indexed articles. Take the first sentence of the lead that contains a 3–4 digit year or a number,
  and is 6–40 words long.
- **True item:** that sentence as written.
- **False item:** the same sentence with one number changed by a fixed rule. A year moves by ±(3–30)
  years; another number is multiplied by a factor in [1.5, 3] or [0.3, 0.7]. The direction is drawn with
  seed 20261012.
- **Split:** by article, 50% dev / 50% test. Target: 150 articles, giving 300 items.
- **Caveat:** the text comes from Wikipedia, which the system can retrieve, so true items are easier than
  real chatbot claims. Reported as such.
- **Revision (2026-10-12, after inspecting the constructed items, before ANY system result).** The first
  build produced unfair or trivially false items: impossible dates ("74 सितंबर"), future years ("अप्रैल
  2043"), subject-less sentences ("इन्होंने …"), and changes inside brackets that the extractor removes.
  The rule is now:
  - only the **first** lead sentence, with bracketed asides removed;
  - a year (1000–2026) is preferred, moved by 3–30 years and kept ≤ 2026;
  - days of the month are never changed;
  - a number inside a word or code ("गग०I") is never changed.

  The first build was discarded.

## 4b. Additions (2026-10-12, before any v1 or v2 result on these sets was looked at)
**Hindi Wikipedia, paraphrased (`hiwiki_para`).**
- Each true sentence of set 4 is reworded by `qwen/qwen3.8-27b` (Groq) so that the text no longer matches
  Wikipedia word for word.
- A paraphrase is kept only if:
  - (a) the multilingual NLI model gives entailment ≥ 0.80 in **both** directions; and
  - (b) it contains exactly the same numbers (digits) as the original.
- The false item is the kept paraphrase with one number changed by the set-4 rule.
- Results are reported for the verbatim and the paraphrased conditions separately. If Qwen is later chosen
  as the LLM judge, this is reported as a bias.

**Hindi place-name swaps (`hiwiki_swap`).** For true sentences of set 4 that name an Indian state or union
territory, or a country (fixed Hindi name lists in `v2data/build_eval_sets.py`), a false item is made by
replacing that name with another one from the same list (seed 20261012). These are added as false items,
alongside set 4's true items, in the same dev/test split by article.

**TruthfulQA (`truthfulqa`), English. Apache-2.0.**
- Misconception-style statements written by people. From the generation split, take `best_answer` (true)
  and the first `incorrect_answers` entry (false), keeping only answers that are full sentences on their own
  (`is_well_formed_claim`), are not refusals ("I have no comment"), and are 4–40 words long.
- Split by question, 50% dev / 50% test, seed 20261012.

**Automatic label checks** (reported):
- every constructed false item differs from its true item exactly where intended (one number or one name);
- every kept paraphrase passed (a) and (b).

## 5. v1 gold (456 claims)
Existing labels and splits (`gold_train_clean.csv` as dev, `gold_test_clean.csv` as test). Known
caveats: one reviewer per claim with the AI suggestion visible, and extractions from the old extractor.
Secondary results only.

## Rules
- Model selection (LLM bake-off), thresholds and relation choice use **dev sets only**.
- Each test set is run once per final configuration (v1 and v2).
- Optional label audit: one author checks 50 random items from sets 1 and 4 (true/false as constructed or
  mapped) and reports the disagreement rate. Nothing is changed on the basis of the audit.

## LLM bake-off (Phase 2.2), fixed before any model was tried
- **Sample** (`v2data/llm_bakeoff.py --sample`, seed 20261012):
  - From the finished v1 dev run, take up to 12 true and 12 false items per (set, language).
  - Only items that no structured source or fact-check decided are eligible.
- **Prompt:** every model gets the same "open" prompt (passages + own knowledge) and the same top-5
  passages (600 characters each), at temperature 0.
- **Candidates:**
  - Groq: `openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b`.
  - Gemini, Mistral and OpenRouter free models, only if the project owner sets their keys.
- **Choice:** the model with the highest balanced accuracy (mean of caught and true-verified) under the
  cross-check rule on the sample. Its false-alarm rate must be ≤ 5%.
  - Ties within 2 points go to the model with fewer false alarms, then to the cheaper model.
  - Models that answer fewer than 90% of the sample are excluded.
  - Qwen wrote the `hiwiki_para` paraphrases. If Qwen wins, its `hiwiki_para` score is reported separately.
- The winner is then run on all dev items. The cross-check rule is adopted only if the decision rule of the
  plan holds on dev:
  - caught ≥ 2× v1;
  - hallucinations marked Verified halved;
  - false alarms ≤ 5%.

## Wikidata relations (Phase 3), fixed before any dev result with them was looked at
- **Choice of relations:** a keyword tally of the FEVER and Mu-SHROOM dev claims that no source decided
  (2026-10-12) gave these candidates:
  - nationality (P27);
  - country of origin (P495);
  - country (P17);
  - year of a work (P577);
  - director (P57);
  - cast member (P161, support only);
  - performer (P175);
  - occupation (P106, support only).

  Hindi: country and nationality patterns.
- **Safety rules:**
  - A claim is Verified by the knowledge graph only if every fact word in it was checked and supported.
  - One contradicted fact is enough to make it Hallucinated.
  - Negated or hedged claims ("not", "never", "only", "no longer", "at least") are never decided.
  - Namesakes: any match supports, and a contradiction needs every namesake with a value to disagree.
- **Keep or drop:** each relation is kept only if its decisions on the dev sets are ≥ 90% correct.
  - A relation whose contradictions are below 90% correct becomes support-only.
  - The counts are reported.

## Rule change, 2026-10-12 (dev only, before any test run)
After the bake-off sample showed that 7 of 11 cross-check false alarms (gpt-oss-20b) came from a passage
"contradiction" overriding an LLM that said the claim is true, the project owner chose the **symmetric**
cross-check: an on-topic passage contradiction makes a claim Hallucinated only if the LLM does not say it is
true. Sample effect (gpt-oss-20b): false alarms 11% → 7%, caught 60% → 59%. The rule as first chosen stays
available (`symmetric=False`, `score.py --first-rule`) and both are reported.

## Held-out test sample (2026-10-12, fixed before any test item was run)
Running the LLM on every test item needs about 2M tokens, which the free quotas cannot provide in time.
So both systems are compared once on a fixed **test sample** with the same design as the dev sample:
- **Sample** (`v2data/make_test_sample.py`, `v2data/sets/*_testS.csv`):
  - Up to 12 true and 12 false items per (set, language), each cell shuffled with its own seed (20261012).
  - Mu-SHROOM: labelled claims.
  - Unlike the dev sample, every item is eligible, including those a source decides, so the sample stands for
    the whole test split.
- **Frozen v2 configuration:** `openai/gpt-oss-20b` (Groq), the bake-off prompt (`open`), the symmetric
  cross-check rule, and the v1 sources first. The tuned `crosscheck` prompt was not finished and is not used.
  The Wikidata relations are off (they decided ~1% of dev claims).
- **Disclosure:** on the dev sample, v2 did NOT meet the pre-set false-alarm limit (7% > 5%). The test result
  is reported as is, with that disclosure.
- **One run each:** v1 and v2 are each run once on this sample. Nothing is changed after seeing it.
- **Provider fallback** (added 2026-10-12, 23:58, before any v2 test result was seen): Groq's free quota allows
  about one claim per 7–10 minutes, too slow for the deadline. So the same open weights (`gpt-oss:20b`) are run
  locally with Ollama, same prompt and passages, and these answers are used for v2. The Groq answers keep
  coming in parallel. On claims both answered, the agreement is reported as a check that the provider
  doesn't matter.

## Fix round (2026-10-13), tuned on dev only; fixed before the new test sample was run
- **First held-out result:** v2 (first version) on the test sample caught 58% vs v1 20%, but had 17% false
  alarms vs 9% (`results/v2_results.md`). It failed. That sample is not used again.
- **Changes, chosen on the dev sample:**
  - the `crosscheck` prompt: "no evidence" is not a reason for Hallucinated, and vague claims that depend on
    missing context are Uncertain;
  - the symmetric rule is kept;
  - the model is gpt-oss:20b, run locally (Ollama).
- **New test sample `testS2`** (`v2data/make_test_sample.py --name testS2`): the same design, excluding every
  `testS` item, with seeds `20261012-test2-…`. v1 and v2 are each run once on it.
- **Decision rule (changed and disclosed):**
  - Why: the first rule (false alarms ≤ 5%) was set when v1's own rate on its gold set was 3–6%; on the new
    public sets v1 itself has 8–9%.
  - The rule is now relative to v1 on the same items. v2 is adopted only if all three hold:
    - caught ≥ 2× v1;
    - hallucinations marked Verified ≤ half of v1's;
    - false alarms ≤ v1's + 3 points.
- **`testS` is now development data** (2026-10-13, 02:10): its false alarms are inspected to find the cause.
  The fix is then judged only on `testS2`, which has not been run.
- **Chosen fix (2026-10-13, 02:20, before `testS2` was run):** keep the bake-off prompt (`open`). Add a
  no-evidence filter: an LLM "Hallucinated" whose reason only says the evidence is missing ("no evidence",
  "not supported", "not mentioned", …) counts as Uncertain (`member3_backend/crosscheck.py`, `NO_EVIDENCE`).
  Keep the symmetric rule.
  - On the dev sample: false alarms 7% → 5%, caught 59% → 37% (Groq answers).
  - On the burned `testS`: false alarms 17% → 8%, caught 59% → 44%.
  - The tuned `crosscheck` prompt is not used (no gain on dev).
- **Run:** v2 is now run once on `testS2` with this configuration, with the gpt-oss:20b answers made locally.

## Last round (2026-10-13, 03:05): the second reading; fixed before `testS3` was run
- **Goal (set by the project owner):** more true claims Verified, without giving back v2's gains.
- **Development data:** the burned `testS` and `testS2`, both with local gpt-oss:20b answers.
- **Method (`v2data/second_reading.py`):**
  - Which claims: those that v2 leaves Uncertain although one side leans true. That is, the LLM says true while
    the passage score is not > 0.65, or the passages support the claim (> 0.65) while the LLM is unsure.
    Excluded: claims the LLM calls false (after the no-evidence filter) and claims with a number missing from
    the evidence.
  - What happens: the LLM reads all 10 retrieved passages in "grounded" mode (passages only, no outside
    knowledge). If it says Verified, the claim is Verified.
- **Effect on the development data:**
  - `testS`: true claims Verified 41% → 55%; hallucinations marked Verified 9% → 11%; caught and false alarms
    unchanged.
  - `testS2`: true claims Verified 41% → 55%; hallucinations marked Verified 5% → 7%; caught and false alarms
    unchanged.
- **Test sample `testS3`:** the same design, excluding every `testS` and `testS2` item. 162 items; hiwiki_swap is
  fully used. v1 and v3 are each run once.
- **Decision rule.** v3 is adopted only if all four hold, against v1 on the same items:
  - caught ≥ 2× v1;
  - hallucinations marked Verified ≤ half of v1's;
  - false alarms ≤ v1's + 3 points;
  - true claims Verified ≥ v1's − 5 points.

## Large final test (2026-10-13, ~09:40): fixed before any v2 answer on `testL` was scored
- **Why:** with ~80 true items per sample, false alarms swung 12% → 14% between samples. The final check uses a
  larger sample.
- **`testL`** (`make_test_sample.py --name testL`): up to 60 true + 60 false items per (set, language), from test
  items no earlier sample used. 620 items. hiwiki_swap and v1gold are used up, and Mu-SHROOM Hindi has false
  items only.
- **Development data:** `testS`, `testS2` and `testS3` (~510 items), all burned.
- **Chosen version, v4a:**
  - Hallucinated only if the LLM says false (after the no-evidence filter), no passage supports the claim, and a
    second reading of all 10 sources does not state it. A passage "contradiction" alone no longer flags a claim.
  - Verified only if the passages support the claim and the LLM agrees, or the second reading confirms a claim
    that leans true.
  - Structured sources and fact-checks still decide first.
- **Effect on the development data:**

  | | false alarms | caught | marked Verified | true Verified |
  |---|---|---|---|---|
  | v1 | 9.0% | 18% | 23% | 59% |
  | v3 | 11.3% | 43% | 8% | 58% |
  | v4a | 7.8% | 40% | 8% | 58% |
- **Decision rule.** The same four conditions as the last round, against v1 on `testL`:
  - caught ≥ 2× v1;
  - hallucinations marked Verified ≤ half of v1's;
  - false alarms ≤ v1's + 3 points;
  - true claims Verified ≥ v1's − 5 points.
- **Run once.** The result is final; there is no further tuning on test data.
- **Result (2026-10-13, 11:30; `results/v2_results_final.md`):** on `testL` (620 items), v4a vs v1:

  | | v4a | v1 | condition |
  |---|---|---|---|
  | caught | 47% | 25% | **FAIL** (1.85× = 176/95, needed 2×) |
  | marked Verified | 6% | 22% | pass |
  | false alarms | 13% | 11% | pass |
  | true claims Verified | 57% | 56% | pass |

  So v4a is **not adopted** under the pre-set rule. The test splits are now used up, so no further tuning can be
  checked honestly.
- **Correction (2026-10-13, afternoon):** the ratio was first written as 1.88× from rounded percentages; the exact
  ratio is 176/95 = 1.85×. The decision is unchanged.
- **Exploratory analyses after the result** (`deliverables/paper_v2_src/ablate.py`, cached answers, no new runs):
  McNemar v4a vs v1, caught 92 vs 11 discordant (p < 0.001), false-Verified 7 vs 67 (p < 0.001), false alarms 21 vs
  17 (p = 0.63), true Verified 20 vs 18 (p = 0.87); caught ratio bootstrap 95% CI 1.61–2.19; false-alarm difference
  95% CI −3.2 to +6.6 points. Ablation (caught / false alarms): LLM alone 86% / 28%; agreement rule only 68% / 22%;
  + no-evidence filter 49% / 16%; + second reading 49% / 16% (true Verified 47% → 57%); v4a 47% / 13%.
- **Paper (2026-10-13):** at the project owner's request the IEEE paper was rewritten around v4a
  (`deliverables/SatyaScore_IEEE_Paper_v2.*`), reporting it as meeting 3 of the 4 pre-set criteria, not as adopted.
