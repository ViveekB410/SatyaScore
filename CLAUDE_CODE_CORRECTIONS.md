# SatyaScore — Corrections Spec (for Claude Code)

**Why this exists:** an audit against the raw data found that the code is correct, but the evaluation has validity problems and the documents overstate in places. This spec fixes what can be fixed in code and documents, and prepares the files the team needs for re-annotation (see `TEAM_TASKS.md`).

**Work in this order:** Part A → Part B → Part C (after the team returns the sheets). Part D is optional.

---

## Ground rules

1. **`RESULTS_SUMMARY.md` is auto-generated.** Never hand-edit it. Every change goes into `generate_results_summary.py`, then regenerate.
2. **Never overwrite `gold_final.csv`.** Any corrected labels go in a new file (`gold_final_v2.csv`), never in place.
3. **Archive, don't delete.** Before any result is regenerated, copy the old version into `_archive/results_pre_regroup/`. Old and new must both remain inspectable.
4. **Report results that get worse.** If regrouping the split lowers any number, that is the result. Do not choose a different seed or fold after seeing numbers.
5. **Private keys never enter git.** Any `*_key*` file with AI verdicts goes into `.gitignore` before it is created.
6. **`python -m pytest` passes before and after each part.** 114 today.

---

## Part A — Prepare annotation files for the team (do first)

The team cannot start until these exist. Reuse the machinery in `make_iaa_set.py` (blind columns, Excel dropdown, stratification, fixed seed). Put everything in a new folder `annotation_round2/`.

### A1. Calibration set — 10 claims

- Sample 10 claims from `gold_final.csv`: 5 English, 5 Hindi.
- Exclude: the 56 round-1 IAA claims, and any claim flagged `broken` in `claim_quality.csv`.
- Include a mix of the three gold verdicts so the discussion covers all three labels.
- Columns: `claim_id, language, source_question, claim_text, full_response, verdict, evidence_url, notes`. Pull `source_question` and `full_response` from the intact source file exactly as `make_iaa_set.py` does.
- **Blind:** no `ai_verdict`, no `ai_reasoning`, no signal scores, no `gold_verdict`.
- One file only: `annotation_round2/calibration_10.xlsx`, with the three-option dropdown on `verdict`.

### A2. Round-2 set — 50 claims, two identical copies

This one exercise does two jobs: it measures human–human agreement properly, **and** it checks whether the reviewed gold labels are reproduced when the AI verdict is hidden.

- Sample 50 claims where `gold_source == "ai_agreed"` — labels that were reviewed with the AI verdict visible. Blind re-labelling shows whether they hold up without that anchor.
- Exclude round-1 IAA claims, calibration claims, and `broken` claims.
- Stratify: 30 English, 20 Hindi. Fixed seed, recorded in the script.
- Same blind columns and dropdown as A1.
- Write two identical copies: `round2_annotator_A.xlsx` and `round2_annotator_B.xlsx`.
- Write the private key `round2_key_DO_NOT_SHARE.csv` (`claim_id, ai_verdict, gold_verdict`). Add it to `.gitignore` **before** writing it, then confirm with `git check-ignore`.

### A3. Instructions file

Write `annotation_round2/INSTRUCTIONS.md` in plain, non-technical language. It must state:
- all three labels must be used where they apply — "Uncertain" is required when evidence is genuinely unclear, not optional;
- work alone, no discussion until both files are returned;
- follow `ANNOTATION_GUIDELINE.md` plus the calibration decisions file the team writes;
- roughly 2–3 minutes per claim.

### A4. Analysis script — `compute_round2.py`

Runs once both sheets are filled. Reports:
1. Human–human agreement: 3-class Cohen's kappa and binary (hallucinated vs not) kappa, each with a 95% bootstrap CI (2,000 resamples), the confusion matrix, and **how many claims both annotators called Hallucinated**.
2. Label-scheme check: how often each annotator used each label. Flag loudly if either annotator never used a label.
3. **Anchoring check:** where the two humans agree, how often the existing gold label (and the AI verdict) matches them. Report the match rate with a 95% CI (Wilson interval), split by language.
4. Writes `results/label_audit.md`.

### A5. Tidy the round-1 files

- `git mv iaa/iaa_annotator_A_AAsawari.xlsx iaa/iaa_round1_annotator_A.xlsx` — this also removes a teammate's name from a filename.
- Update both `compute_iaa.py` and `generate_results_summary.py` to read the renamed file. `compute_iaa.py` currently reads the *empty* `iaa_annotator_A.xlsx` and reports "Not labeled yet".
- Confirm both scripts now produce the same kappa values.

---

## Part B — Fixes that can be done now

### B1. Group the train/test split by source question

**Problem:** 43 of the 52 source questions in the test split also appear in training, so claims from the same LLM answer land on both sides.

**Fix in `make_clean_split.py`:**
- Replace `train_test_split` with `StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)`, grouped by `source_query_id`, stratified by language × verdict.
- **Use fold 0 as the test set. Decide this before running. Do not try other folds.**
- Assert that train and test share zero `source_query_id` values; fail loudly if not.
- Print Hallucinated counts per language in both splits.

**Then, in order:** archive the old results (ground rule 3), re-run `make_clean_split.py`, `python -m member1_model.train_weights --csv gold_train_clean.csv --languages en hi`, both `honest_ablation.py` variants (with and without SemSim), then `generate_results_summary.py`.

**Write `results/regroup_comparison.md`:** the old and new ablation tables side by side, with Hallucinated counts for each split.

### B2. Show uncertainty in the results table

In the ablation output and the summary table:
- Next to every test metric, show **the number of Hallucinated claims it was computed on**.
- Add 95% bootstrap CIs (2,000 resamples) for accuracy and Hallu-F1.
- Where a language has fewer than 10 Hallucinated test claims, still print the number, but mark it **"too few positives to interpret"**. Do not leave a bare Hallu-F1 standing on two examples.

### B3. Correct `generate_results_summary.py`

Change the generator, then regenerate.

**Provenance section.** State the protocol accurately: every AI verdict was reviewed by the annotator, who wrote a verdict only when they disagreed. 360 of 456 gold labels (79%) are reviewed-and-agreed. Do **not** describe these as unreviewed. The limitation to state is **anchoring**: review happened with the AI verdict visible, which biases toward agreement. Include the round-1 evidence: blind annotators matched the gold labels 73% (B) and 36% (A) of the time on the 56 IAA claims. Round-2 results (Part C) will measure this directly.

Also add a short protocol paragraph to `ANNOTATION_PROVENANCE.md` recording that review was full, not sampled, and that a blank annotator field means "reviewed and agreed" — so the convention is documented rather than inferred.

**IAA section.** Remove the phrases "disagreement concentrated on the Verified/Uncertain boundary" and "substantial". Replace with computed facts: n, the confusion matrix, label usage per annotator, and the number of claims both called Hallucinated. State that annotator B never used "Uncertain", so the annotators applied different label schemes and the 3-class kappa reflects that mismatch. Binary kappa **0.53 is the headline figure**. If 0.61 is reported at all, it must carry its label ("well-formed subset") and its own n.

**Latency section.** Read `results/latency_benchmark.md`. Report the measured figures: T4 GPU median 104 ms per claim (target met), 2,414 ms per 10-claim document (target met), mean 1,171 ms (target missed — driven entirely by the KG network call; NLI mean 80 ms). Delete the unmeasured "~40s/call; GPU → <1s" line.

**New Phase 3 section.** Summarise, reading from the results files:
- Retrieval diagnostic: English source-article top-3 recall 0.64 Hallucinated vs 0.83 Verified, **computed only on claims with a recorded source** (the raw 0.60 vs 0.81 includes claims with no source and understates the comparison). Describe it as suggestive at this sample size.
- Hindi similarity inversion (Hallucinated 0.717 > Verified 0.649) as a candidate explanation for the below-chance Hindi SemSim AUC — hypothesis only, n = 9.
- C2-lite: English ΔAUC −0.012, 95% CI [−0.121, +0.094], no significant change, default stays off.
- **Do not** present the neutral-rate rise (0.67 → 0.80) as a finding. The number of scored units grew fivefold, so the rates aren't comparable.

**Limitations section. Add:**
- all responses were generated by a single LLM, which limits generalisation;
- the test split's Hallucinated counts (state the post-regroup numbers from B1);
- label reliability per the provenance and IAA findings above.

### B4. Hand-edit `HANDOFF.md` and `PROJECT_STATUS.md`

These are hand-written, so edit them directly:
- update the date and test count;
- replace latency claims with the measured figures from B3;
- use binary kappa 0.53 as the headline everywhere;
- in `PROJECT_STATUS.md`, remove "because of the dataset, not the code" and "more backend work will not move the accuracy numbers". Replace with: *the leading hypothesis is label reliability, supported by the round-1 IAA findings; the English retrieval gap is a pipeline-side factor that remains open.*
- remove the neutral-rate claim;
- move the latency target from "remaining" to "met on median, on GPU".

---

## Part C — After the team returns the sheets

1. Put the filled files in `annotation_round2/`. Run `compute_round2.py`.
2. Add a section to `generate_results_summary.py` reading `results/label_audit.md`. Regenerate.
3. **Do not quietly relabel the gold set.** If blind re-labelling disagrees with gold labels, write corrected labels for the audited claims only into `gold_final_v2.csv`, with `gold_source = "human_audit_round2"`. Report results on both v1 and v2 side by side, and say which is which.
4. If round-2 binary kappa reaches the guideline's target of 0.65, say so. If it doesn't, say that too.

---

## Part D — Optional: check fp16 on CPU

1. After loading `NLIScorer` on CPU, print the model's parameter dtype.
2. If it's `float16`, force `torch_dtype=torch.float32` when `device == "cpu"`. Leave GPU unchanged.
3. Time the `DEMO_CLAIMS.md` set on CPU before and after, and write the figures to `results/cpu_dtype_check.md`.
4. Confirm the demo verdicts are unchanged.

---

## Done when

- `annotation_round2/` contains the calibration file, two identical round-2 sheets, instructions, and a git-ignored key file.
- `compute_iaa.py` and the generator agree on round-1 kappa.
- Train and test share zero source questions, and `results/regroup_comparison.md` exists.
- Every test metric shows its Hallucinated count and a CI.
- `RESULTS_SUMMARY.md`, `HANDOFF.md` and `PROJECT_STATUS.md` state the measured latency, one kappa convention, the review protocol with its anchoring limitation, and the IAA scheme mismatch, and none of them claims the cause is proven.
- 114+ tests pass.
