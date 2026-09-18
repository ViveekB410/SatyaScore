# dataset_pipeline/pilot_sampler.py
"""
PRD Section 11.2 Step 5: Pilot subset sampling.

Samples a stratified pilot subset from the full claim pool BEFORE full-scale
annotation begins, so guideline/schema problems surface on ~60 claims instead
of on all 509.

Confirmed against the real unannotated_dataset.csv export:
    claim_id, source_query_id, source_llm, language, domain, claim_text,
    sem_sim, nli_prob, kg_conf, gold_verdict, evidence_url
Only claim_id / domain / language are used for stratification; every other
column (including the pre-filled sem_sim/nli_prob/kg_conf signals) passes
through untouched.
"""


# ---- Config ----
import pandas as pd
import numpy as np
from pathlib import Path

# ---- Config ----
# Resolve paths relative to the project root (one level up from this file's
# folder), so this works no matter what PyCharm sets as the working directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_CSV = PROJECT_ROOT / "unannotated_dataset.csv"
OUTPUT_DIR = PROJECT_ROOT / "dataset_pipeline" / "output"
PILOT_OUTPUT_CSV = OUTPUT_DIR / "pilot_annotation.csv"
REMAINING_OUTPUT_CSV = OUTPUT_DIR / "remaining_pool.csv"
STRATIFY_COLS = ["domain", "language"]
PILOT_SIZE = 60
MIN_PER_STRATUM = 3
RANDOM_STATE = 42


"""
Small addition to dataset_pipeline/pilot_sampler.py — apply as a patch,
not a full file replacement, since I haven't seen the rest of your project
structure since the pilot_sampler was written.

WHAT THIS ADDS: a function that strips sem_sim/nli_prob/kg_conf out of the
pilot CSV before annotators see it, so the anchoring-bias risk (annotators
seeing the model's own guess while forming their independent judgement) is
structurally impossible rather than relying on annotators remembering to
hide columns themselves.

WHERE TO ADD THIS: paste this function into pilot_sampler.py, anywhere
after the imports (e.g. right after sample_pilot() or right before
_print_summary()).

THEN UPDATE THE __main__ BLOCK to call it — see the diff at the bottom of
this file for the exact lines to add.
"""

BLIND_COLUMNS_TO_DROP = ["sem_sim", "nli_prob", "kg_conf"]




# ---------------------------------------------------------------------------
# DIFF for the __main__ block in pilot_sampler.py — add these lines:
# ---------------------------------------------------------------------------
#
#     pilot_df.to_csv(PILOT_OUTPUT_CSV, index=False)
#     remaining_df.to_csv(REMAINING_OUTPUT_CSV, index=False)
#
# +   BLIND_OUTPUT_CSV = OUTPUT_DIR / "pilot_annotation_BLIND.csv"
# +   export_blind_csv(pilot_df, BLIND_OUTPUT_CSV)
# +   print(f"Wrote BLIND annotator copy (no model signals) -> {BLIND_OUTPUT_CSV}")
#
#     _print_summary(pilot_df, STRATIFY_COLS)
#
# Also update ANNOTATION_GUIDELINE.md section 3 to say:
#     "Annotate using pilot_annotation_BLIND.csv, not pilot_annotation.csv
#      — the blind copy has the model's own signal columns removed so you
#      can't see them even by accident."

def sample_pilot(
    df: pd.DataFrame,
    pilot_size: int = PILOT_SIZE,
    stratify_cols: list = STRATIFY_COLS,
    min_per_stratum: int = MIN_PER_STRATUM,
    random_state: int = RANDOM_STATE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (pilot_df, remaining_df).

    Proportional allocation across strata, with a floor of min_per_stratum,
    capped so we never sample more than pilot_size in total or more than
    exists in any single stratum.
    """
    missing = [c for c in stratify_cols + ["claim_id"] if c not in df.columns]
    if missing:
        raise ValueError(
            f"Input CSV is missing expected column(s): {missing}. "
            f"Check STRATIFY_COLS / your dataset_builder.py export schema."
        )

    rng = np.random.RandomState(random_state)
    strata = df.groupby(stratify_cols, dropna=False)

    # Proportional allocation first
    stratum_sizes = strata.size()
    total = len(df)
    raw_alloc = (stratum_sizes / total * pilot_size).round().astype(int)

    # Enforce floor, cap at stratum's actual size
    alloc = raw_alloc.clip(lower=min_per_stratum)
    alloc = pd.concat([alloc, stratum_sizes], axis=1).min(axis=1)
    alloc.name = "n_sample"

    # If floors pushed total over pilot_size, trim largest strata down
    overflow = alloc.sum() - pilot_size
    if overflow > 0:
        sorted_idx = alloc.sort_values(ascending=False).index
        for idx in sorted_idx:
            if overflow <= 0:
                break
            reducible = alloc[idx] - min_per_stratum
            take = min(reducible, overflow)
            if take > 0:
                alloc[idx] -= take
                overflow -= take

    pilot_parts = []
    for stratum_key, n in alloc.items():
        if n <= 0:
            continue
        group = strata.get_group(stratum_key)
        sampled = group.sample(n=int(n), random_state=rng.randint(0, 1_000_000))
        pilot_parts.append(sampled)

    pilot_df = pd.concat(pilot_parts).sort_values("claim_id").reset_index(drop=True)
    remaining_df = df[~df["claim_id"].isin(pilot_df["claim_id"])].reset_index(drop=True)

    return pilot_df, remaining_df

BLIND_COLUMNS_TO_DROP = ["sem_sim", "nli_prob", "kg_conf"]


def export_blind_csv(pilot_df, output_path):
    blind_df = pilot_df.drop(columns=BLIND_COLUMNS_TO_DROP, errors="ignore")
    blind_df.to_csv(output_path, index=False)
    return blind_df

def _print_summary(pilot_df: pd.DataFrame, stratify_cols: list) -> None:
    print(f"Pilot subset: {len(pilot_df)} claims")
    print(pilot_df.groupby(stratify_cols, dropna=False).size().to_string())

if __name__ == "__main__":

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    full_df = pd.read_csv(INPUT_CSV)
    pilot_df, remaining_df = sample_pilot(full_df)

    pilot_df.to_csv(PILOT_OUTPUT_CSV, index=False)
    remaining_df.to_csv(REMAINING_OUTPUT_CSV, index=False)

    BLIND_OUTPUT_CSV = OUTPUT_DIR / "pilot_annotation_BLIND.csv"
    export_blind_csv(pilot_df, BLIND_OUTPUT_CSV)
    print(f"Wrote BLIND annotator copy -> {BLIND_OUTPUT_CSV}")


    _print_summary(pilot_df, STRATIFY_COLS)
    print(f"\nWrote pilot subset -> {PILOT_OUTPUT_CSV}")
    print(f"Wrote remaining pool -> {REMAINING_OUTPUT_CSV}")
