# Version 2 gold data: protocol (fixed 2026-10-12, before any answer is generated or label collected)

## Why
The v1 labels (456 claims) were made on claims from an older extractor (about 31 of the 45 training
"hallucinations" were extractor artefacts), with the AI verdict visible to a single reviewer per claim,
and contain only 9 Hindi hallucinations. Version 2 relabels from scratch.

## Claims
1. **Original answers:** the 100 Llama 3.3 (70B) answers in `raw_responses.json`, re-extracted with the
   current extractor (`relabel/make_v2_claims.py`, after the 2026-10-12 extractor fix for
   "**Label**: description" lines, Devanagari list numbers and spacing) → `relabel/claims_v2_original.csv`.
2. **New Hindi answers:** 50 new Hindi questions (`relabel/questions_hi_new.json`, 10 per domain,
   written before generation), one answer each from Groq:
   - questions with an even index → `openai/gpt-oss-20b`;
   - questions with an odd index → `qwen/qwen3.8-27b`.

   Llama 3.3 is no longer available to the key. Generation uses `dataset_pipeline.response_collector.
   OpenAICompatibleGenerator` with its unchanged prompt ("Answer factually and concisely. उत्तर हिंदी में
   दें।"), temperature 0.7, and checkpointing → `relabel/raw_responses_hi_new.json` →
   `relabel/claims_v2_new_hi.csv`.
   - **Known bias:** if a gpt-oss or Qwen model is later chosen as the LLM judge, its results on the
     answers from the same family are reported separately.
3. Claims flagged `needs_context` (a leading pronoun the extractor cannot resolve) stay in the set.
   Annotators see the full answer.

## Annotation (blind, 2 annotators per claim)
- **Annotators:** the four authors, A–D. Every claim is labelled by two of them, in rotating pairs
  (AB, CD, AC, BD, AD, BC), balanced by language. No AI or system verdict is shown.
- **Calibration first:** 20 shared claims (10 EN, 10 HI), labelled by all four and discussed against
  `ANNOTATION_GUIDELINE.md`. They are not part of the evaluation.
- **Labels:**
  - **Verified:** every fact in the claim is correct;
  - **Hallucinated:** at least one fact is wrong;
  - **Uncertain:** the annotator cannot establish it;
  - **Not a claim:** malformed, or nothing checkable.

  Each label comes with an evidence URL and an optional note.
- **Adjudication:** one meeting resolves every pair disagreement. The record keeps both original labels
  and the resolution.
- **Reported:** Cohen's κ per pair and overall (binary "hallucinated or not" and 3-class), before
  adjudication.

## Split
- Grouped by source question (`StratifiedGroupKFold`, seed **20261012**): **dev 60% / test 40%**.
- The test split is locked: it is used once, for the final v1-against-v2 comparison. All tuning and
  selection (LLM choice, thresholds, relation choice) use dev only.

## Not allowed
No label is written by anyone other than the four annotators; no label is changed after adjudication; the
test split is not looked at before the final run.
