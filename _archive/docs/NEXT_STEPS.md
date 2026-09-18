# SatyaScore — state after the corpus and calibration session

## Confirmed, not re-derived

`honest_eval.py` was rebuilt (it was referenced in the handoff but absent from
the zip) and reproduces the prior diagnosis exactly from the CSVs: fused score
identical to `nli_prob`, kg_conf 0/576, EN synthetic recall 0.895 against
human-annotated recall 0.222, EN human-annotated Hallucinated-F1 0.200 shipped
and 0.000 after retuning, EN train-fitted cut-points 0.18/0.23 giving test
accuracy 0.653.

Hindi cut-points differ from the previous session's note. Grid search on train
macro-F1 gives 0.01/0.21 (test accuracy 0.769), not 0.43/0.49 (test accuracy
0.692). With seven hallucinated claims in the Hindi training split, the
objective surface is nearly flat and the difference is noise. Do not treat
either pair as meaningful until Hindi retrieval works.

## Done in this session

- `corpus.py` (new). Single shared corpus builder for every entry point.
  Per-language Wikipedia domains, Hindi titles resolved through the MediaWiki
  langlinks API rather than hardcoded, real per-chunk language list passed to
  the embedder, every `evidence_url` in the gold CSVs pulled into the corpus,
  Devanagari danda added to the sentence splitter, article text and langlink
  lookups cached to `evidence_corpus_cache.json` so reruns are network-free.
- `score_merge_train_ablate.py`, `generate_dataset.py`, `member3_backend/api.py`
  now all call `corpus.build_and_index`. All three previously carried their own
  English-only copy of the topic list, fetcher and chunker. The API also loaded
  hardcoded placeholder weights (0.5/0.3/0.2) and now loads the trained ones.
- `member1_model/cmhsa.py`: per-language verdict cut-points, `load_thresholds`,
  and `load_language_config` which reads `weights_{lang}.json` and
  `thresholds_{lang}.json` with the old defaults as fallback.
- `thresholds_en.json`, `thresholds_hi.json` fitted on the train split only.
- `honest_eval.py` (rebuilt) with `--calibrate`, `--write-thresholds`, and a
  threshold-free AUC block that holds the positive class fixed while swapping
  synthetic for human-annotated negatives.
- `kg_coverage.py` (new). Answers handoff step 4 offline.
- `honest_ablation.py` (new). Refits cut-points per configuration on the train
  split, reports every configuration over the full test split and over
  human-annotated claims separately, and detects configurations whose
  predictions are identical. Writes `results/honest_ablation.json` and
  `ablation_table.md`.
- `make_figures.py` (new). Writes the three results figures to `figures/`.
- `tests/test_corpus.py` and `tests/test_honest_eval.py` (new, 21 tests, no
  torch or network needed). They cover the per-chunk language assignment, the
  cache, langlink resolution, the fusion arithmetic, the fast cut-point search
  against brute force, and the synthetic/human disaggregation.
- `ablation_and_limitations.md`: report prose built around the negative result.

## Blocked here, run locally

The container used for this session cannot reach wikipedia.org, so the corpus
could not be fetched and the dataset could not be regenerated. Everything
above is verified against the existing CSVs, and `corpus.py` was tested
end to end against a stubbed MediaWiki API (title planning, langlink
resolution, chunking, per-chunk language assignment, cache reuse).

Run in order:

```bash
python corpus.py                       # builds the cache, prints per-language counts
python score_merge_train_ablate.py     # regenerates signals, weights, ablation
python honest_eval.py --calibrate --write-thresholds
python honest_eval.py
```

Check before reading any Hindi metric: the Hindi drop rate printed by
`score_merge_train_ablate.py`, and `hi.test_coverage.dropped_no_signal` in
`results/honest_eval.json`. If Hindi claims are still being dropped, the
corpus fix did not take and the Hindi numbers remain uninterpretable.

## KG signal: closed

`kg_coverage.py` reports that 0 of 576 claims contain any of the 27 relation
phrases in `RELATION_TO_PID`. The coverage ceiling is zero before Wikidata is
ever contacted, because the claims are descriptive sentences rather than
binary relations between entities. `--online` samples Wikidata resolution if a
number for the linker itself is wanted, but it cannot change the ceiling. This
is a limitations finding, not a task.

## New finding from the per-configuration ablation

Once each configuration is calibrated on its own training distribution rather
than on the shipped 0.35/0.65, SemSim-only becomes scoreable and the ranking
inverts by population. On the full English test split the NLI configurations
lead, at accuracy 0.653 and Hallucinated-F1 0.560 against 0.417 and 0.195. On
human-annotated claims only, SemSim-only reaches Hallucinated-F1 0.200 while
every NLI configuration reaches 0.000, and the AUC ordering agrees, at 0.591
against 0.545. The weight model discarded the only signal that has any purchase
on real hallucinations, because it was trained against a hallucinated class
that is two thirds synthetic. Both numbers rest on nine claims, so state the
count whenever quoting them.

## Open decisions

- Whether to ship the recalibrated cut-points. They raise English test accuracy
  from 0.444 to 0.653 and drop human-annotated hallucination recall from 0.222
  to 0.000. The files are written and loaded; reverting is a matter of deleting
  `thresholds_{lang}.json`.
- Whether to keep synthetic perturbations in the test split at all. Keeping
  them supports the evaluation-validity finding. Removing them from the test
  split while keeping them in train would give a cleaner headline number and
  lose the comparison that makes the finding measurable.
