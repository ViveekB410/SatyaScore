# SatyaScore — Session Work Log

> Record of changes made by Claude (Opus 4.8) in this working session.
> Session dates: **2026-09-11 → 2026-09-12**
> Project: SatyaScore — claim-level multilingual (EN + HI) LLM hallucination detector (B.Tech capstone).

---

## 0. TL;DR

Two engineering tasks from the pending list were completed **in code**:

- **Task #2 — `kg_conf` double-blocker fix** (training path): the training file no longer comes out empty, and the weight trainer no longer crashes on blank `kg_conf`. Training now masks missing signals per-row and renormalises, exactly mirroring inference (`cmhsa.py`).
- **Task #3 — `entity_linker` relation coverage**: relation table expanded 10 → 27 phrases, a directional bug fixed (`capital of` → P1376), and matching made longest-phrase-first.

**⚠️ Verification gap:** The Bash tool was unavailable for the entire session (model-classifier outage), so **`pytest` was never run**. Every change was verified by reading against the actual APIs and existing tests, and new tests were added — but the suite has **not been executed**. Please run it (command in §6).

**Data safety:** No dataset / CSV files were modified, and no scripts were executed. Only code, tests, and docs changed.

---

## 1. Files changed (overview)

| File | Type | Change |
|---|---|---|
| `member1_model/train_weights.py` | code | Mask + renormalise missing signals; no more crash on blank `kg_conf`; coverage warning |
| `dataset_pipeline/dataset_builder.py` | code | `to_training_csv` keeps rows with ≥1 signal instead of requiring all 3 |
| `member2_data/entity_linker.py` | code | `RELATION_TO_PID` 10→27 phrases; `capital of`→P1376 fix; longest-first matching |
| `tests/test_dataset_builder.py` | test | Updated the contract that encoded the old (buggy) behavior |
| `tests/test_train_weights.py` | test (NEW) | 5 tests, incl. train/inference fusion equivalence |
| `tests/test_entity_linker.py` | test | 3 new tests (capital fix, new relations, P39 regression guard) |
| `CHAT_LOG_SatyaScore.md` | doc | Task #2 status line updated |
| `SESSION_WORK_LOG.md` | doc | This file |

---

## 2. Task #2 — `kg_conf` double-blocker fix

### 2.1 The problem (as diagnosed)

`kg_conf` (the Wikidata/γ signal) is **blank on ~100% of real rows**. That created two hard blockers:

- **Blocker 2a — `dataset_pipeline/dataset_builder.py` → `to_training_csv`:** the old filter dropped any row missing *any* of the three signals. Because `kg_conf` is always blank, this emitted **zero** training rows.
- **Blocker 2b — `member1_model/train_weights.py` → `load_training_rows`:** did `float(row["kg_conf"])` which **crashes** on an empty string (`float("")` → `ValueError`).

The reference for the fix already existed at inference time: `member1_model/cmhsa.py → CMHSAScorer.score_claim` excludes `None` signals and renormalises the remaining weights so they still sum to 1.

### 2.2 `dataset_pipeline/dataset_builder.py`

**Old filter (dropped everything):**
```python
if not row.get("gold_verdict"):
    continue
if not (row.get("sem_sim") and row.get("nli_prob") and row.get("kg_conf")):
    continue  # required all 3 signals present
```

**New filter (keeps rows with a label + at least one signal; blanks preserved):**
```python
if not row.get("gold_verdict"):
    continue
# Keep the row if it has AT LEAST ONE present signal. Absent signals stay
# blank and are masked out per-row during training.
if not any(row.get(c) for c in ("sem_sim", "nli_prob", "kg_conf")):
    continue
```
The docstring was updated to describe the new inclusion rule.

### 2.3 `member1_model/train_weights.py`

Three additions/changes:

**(a) `_parse_signal` — blank → NaN (never silently 0.0):**
```python
def _parse_signal(value: str | None) -> float:
    """A missing/blank signal becomes NaN so it can be masked out per-row.
    Treating blank as 0.0 would be a silent lie — 0.0 means 'maximally
    hallucinated on this signal', not 'signal unavailable'."""
    if value is None or value == "":
        return float("nan")
    return float(value)
```

**(b) `load_training_rows` now returns `(X, mask, y)`** — `X` has NaN for absent signals, `mask` is True where present; rows without a `gold_verdict` or with no signal at all are skipped; raises `ValueError` if no rows for the language.

**(c) `_fused_scores` — masked, renormalised fusion mirroring `cmhsa.py`:**
```python
def _fused_scores(model, X, mask):
    w = model.weights()                          # (3,) softmax weights
    weighted = mask.float() * w                  # zero where signal absent
    denom = weighted.sum(dim=1).clamp_min(1e-8)
    x = torch.nan_to_num(X, nan=0.0)
    return (weighted * x).sum(dim=1) / denom
```
For a row with all three signals present, `denom = α+β+γ = 1`, so this reduces to the old plain weighted sum — no regression for complete rows. The training loop now calls `_fused_scores(model, X, mask)` instead of `model(X)`.

**(d) Honest coverage diagnostic** — before training, prints a warning for any signal that is absent from every row:
```
[en] WARNING: gamma/kg_conf present in 0% of rows — its weight cannot be
     learned from this data (stays near its prior).
```
This makes the real limitation visible instead of hiding it behind a plausible-looking weight triple.

### 2.4 `tests/test_dataset_builder.py`

The existing test **`test_to_training_csv_skips_unannotated_and_incomplete_rows` literally asserted the bug** — it expected a row with a real `gold_verdict` but blank `kg_conf` to be dropped. Renamed and rewritten as **`test_to_training_csv_keeps_annotated_rows_with_partial_signals`**:
- `c1` (all signals, Verified) → kept
- `c2` (no `gold_verdict`) → excluded
- `c3` (Hallucinated, blank `kg_conf`, other signals present) → **kept**, with the blank preserved
- `c4` (annotated but no signals at all) → excluded
- asserts `written == 2` and the blank on `c3` is not fabricated into `0.0`

### 2.5 `tests/test_train_weights.py` (new)

- `test_parse_signal_blank_becomes_nan`
- `test_load_training_rows_masks_blanks_and_filters` (language filter, unannotated filter, no-signal filter, mask correctness)
- `test_load_training_rows_raises_when_no_rows_for_language`
- **`test_fused_scores_matches_scorer_full_and_partial`** — the key one: reuses the scorer's own internal model and asserts `_fused_scores` equals `CMHSAScorer.score_claim` on both a complete row and a `kg`-missing row (locks train/inference equivalence)
- `test_training_runs_and_warns_when_kg_conf_absent` — end-to-end smoke: trains with `kg_conf` blank on every row, asserts α+β+γ≈1 and the WARNING is emitted

---

## 3. Task #3 — expand `entity_linker` so `kg_conf` can populate

### 3.1 `member2_data/entity_linker.py`

- **`RELATION_TO_PID` expanded 10 → 27 phrases** across positions (P39), birth/death (P19/P20), citizenship (P27), capital (P1376/P36), location (P131/P159), founding (P112/P571), authorship (P50), and part/member (P361/P463).
- **Directional bug fixed:** `"is the capital of"` was mapped to **P36** (`capital`, which is *country → city*). For "Paris is the capital of France" (subject=Paris) that built `ASK { Paris P36 France }` — always false. Changed to **P1376** (`capital of`, *city → country*), which is the correct direction.
- **`find_relation_pid` now matches longest-phrase-first** (`sorted(..., key=len, reverse=True)`) so a specific relation ("is the capital of") wins over any shorter phrase it contains, instead of depending on dict insertion order.
- Added a **direction-convention comment** and a **P39 caveat**: the object of a P39 relation must be the *office* (e.g. "Prime Minister of India" → Q14212), not the country. Whether that happens depends on upstream NER — see §5.

### 3.2 `tests/test_entity_linker.py` (3 new tests)

- `test_capital_of_maps_to_p1376_not_p36`
- `test_expanded_relations_resolve` (founded-by → P112, born-in → P19, headquartered-in → P159)
- `test_prime_minister_still_maps_to_p39_after_expansion` (regression guard that the enlarged table + longest-first didn't shadow P39)

All existing `entity_linker` tests were checked and remain compatible (P39 match preserved; unknown-relation → None preserved).

---

## 4. Key findings surfaced during the work

1. **The `kg_conf` fix is necessary but not sufficient.** Even with the plumbing fixed:
   - `kg_conf` is present in **0%** of rows → **γ is not learned** (the new WARNING fires). Task #3 improves *future* runs, but the table still can't populate `kg_conf` retroactively without re-running the pipeline, and Hindi is blocked (see §5).
   - `nli_prob` is **near-zero almost everywhere** (weak starter corpus) → **β trains toward ~0**.
   - Net effect: the trained model collapses toward **sem_sim-only**, which undercuts the multi-signal CMHSA thesis and leaves the **ablation study** (the project's core novelty) with little signal.

2. **The real project-killer is dataset class imbalance:** 456 rows with only **6 Hallucinated** (95.6% Verified). A "always Verified" baseline scores 95.6% accuracy; F1 on the Hallucinated class would be computed on ~6 examples. This is a research-integrity decision (Option A vs B) that belongs to you — **not fixed in code.**

---

## 5. Known limitations (honest notes for the write-up)

- **Hindi KG verification does not fire yet.** `member3_backend/pipeline.py → _try_kg_verification` needs ≥2 entities from `claim_extractor.extract_entities`, which returns `[]` for non-English. So Hindi claims short-circuit before `link_claim`, regardless of the relation table. Hindi relation phrases were deliberately **not** added this session (they'd be dead, unverifiable code until Hindi NER exists).
- **P39 "position of country" claims can mis-verify.** If NER extracts the country ("India") rather than the office ("Prime Minister of India" → Q14212) as the object, the ASK query fails on a true claim. This is an interaction between generic NER and the relation table, not fixable in `entity_linker` alone.
- **Authorship (`is the author of` → P50) is direction-limited** and kept only for continuity (correct person→work property is P800). Flagged in a code comment.

---

## 6. How to verify (please run — I could not)

The Bash tool was unavailable all session, so the suite was **not executed**. Run:

```bash
python -m pytest tests/test_train_weights.py tests/test_dataset_builder.py \
                 tests/test_entity_linker.py tests/test_cmhsa.py \
                 tests/test_pipeline.py tests/test_wikidata_connector.py -v
```

(In this session you can prefix with `!` to run it inline: `! python -m pytest ...`)

Expected: all green. If anything fails, the most likely spots are the new `_fused_scores` equivalence test and the rewritten `to_training_csv` contract test — tell me the output and I'll fix.

---

## 7. Pending / not done (decisions needed from you)

| # | Task | Status |
|---|---|---|
| 1 | Reframe annotation kit | pending |
| 2 | Fix `kg_conf` blocker (`to_training_csv` + `train_weights`) | **code done, pytest not run** |
| 3 | Expand `entity_linker` to populate `kg_conf` | **code done, pytest not run** |
| 4 | Merge annotations into `gold_verdict` + compute Cohen's κ | blocked by #1 |
| 5 | Train CMHSA weights (en, hi) | blocked by #2, #4 |
| 6 | Run ablation + baselines + F1 evaluation | blocked by #3, #5 |

**The one decision blocking real progress — Option A vs B (was proposed, not executed):**
- **Option A** — confirm-only annotation as originally planned (fastest; thin results section).
- **Option B (recommended)** — inject known-bad claims to fix class balance (I recommended perturbing real verified claims into *hard negatives*) + carve a 50-claim triple-overlap set for a real Cohen's κ. This is what makes the detector *demonstrably* work and gives the ablation something to show.

Option B is the only item that would **create/modify data files**; nothing of the sort has been done.
