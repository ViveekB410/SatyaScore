"""Tests for honest_eval.py. Pure CSV maths, so these run without torch."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import f1_score

import honest_eval as he


def make_frame(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    for column in he.SIGNALS:
        if column not in frame:
            frame[column] = np.nan
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if "gold_source" not in frame:
        frame["gold_source"] = ""
    frame["is_synthetic"] = frame["gold_source"] == he.SYNTHETIC_SOURCE
    return frame


EQUAL_WEIGHTS = {"alpha": 1 / 3, "beta": 1 / 3, "gamma": 1 / 3}
NLI_ONLY_WEIGHTS = {"alpha": 0.0, "beta": 0.5, "gamma": 0.5}


def test_fusion_renormalises_over_present_signals():
    row = pd.Series({"sem_sim": 0.8, "nli_prob": 0.4, "kg_conf": np.nan})
    assert he.fuse(row, EQUAL_WEIGHTS) == pytest.approx(0.6)


def test_missing_kg_makes_fused_score_equal_nli_when_alpha_is_zero():
    """The central arithmetic claim of the whole diagnosis: with kg_conf absent
    and alpha trained to zero, the composite score is the NLI probability."""
    row = pd.Series({"sem_sim": 0.9, "nli_prob": 0.21, "kg_conf": np.nan})
    assert he.fuse(row, NLI_ONLY_WEIGHTS) == pytest.approx(0.21, abs=1e-6)


def test_single_signal_survives_a_zero_weight():
    """CMHSAScorer clamps weights to 1e-8, so a SemSim-only ablation is still
    scoreable after alpha trains to zero. Without the floor this is 0/0."""
    row = pd.Series({"sem_sim": 0.73, "nli_prob": np.nan, "kg_conf": np.nan})
    assert he.fuse(row, NLI_ONLY_WEIGHTS) == pytest.approx(0.73)


def test_row_with_no_signal_is_nan_not_zero():
    row = pd.Series({"sem_sim": np.nan, "nli_prob": np.nan, "kg_conf": np.nan})
    assert np.isnan(he.fuse(row, EQUAL_WEIGHTS))


@pytest.mark.parametrize("score,expected", [
    (0.10, "Hallucinated"), (0.18, "Uncertain"), (0.20, "Uncertain"),
    (0.23, "Uncertain"), (0.30, "Verified"),
])
def test_verdict_boundaries_are_strict(score, expected):
    assert he.verdict(score, 0.18, 0.23) == expected


def test_unscored_rows_are_excluded_from_metrics():
    frame = make_frame([
        {"gold_verdict": "Verified", "nli_prob": 0.9},
        {"gold_verdict": "Hallucinated", "nli_prob": 0.1},
        {"gold_verdict": "Hallucinated"},  # retrieved nothing
    ])
    frame["fused"] = [he.fuse(row, NLI_ONLY_WEIGHTS) for _, row in frame.iterrows()]
    result = he.metrics(frame, (0.35, 0.65))
    assert result["n"] == 2
    assert result["accuracy"] == pytest.approx(1.0)


def test_recall_by_population_separates_synthetic_from_human():
    frame = make_frame([
        {"gold_verdict": "Hallucinated", "nli_prob": 0.05, "gold_source": he.SYNTHETIC_SOURCE},
        {"gold_verdict": "Hallucinated", "nli_prob": 0.02, "gold_source": he.SYNTHETIC_SOURCE},
        {"gold_verdict": "Hallucinated", "nli_prob": 0.80, "gold_source": "human_override"},
        {"gold_verdict": "Verified", "nli_prob": 0.90, "gold_source": "human_override"},
    ])
    frame["fused"] = [he.fuse(row, NLI_ONLY_WEIGHTS) for _, row in frame.iterrows()]
    split = he.recall_by_population(frame, (0.35, 0.65))
    assert split["synthetic_perturbation"] == {"n": 2, "recall": 1.0}
    assert split["human_annotated"] == {"n": 1, "recall": 0.0}


def test_metrics_match_sklearn():
    rng = np.random.default_rng(0)
    frame = make_frame([
        {"gold_verdict": rng.choice(he.CLASSES), "nli_prob": float(rng.random())}
        for _ in range(200)
    ])
    frame["fused"] = frame["nli_prob"]
    result = he.metrics(frame, (0.3, 0.7))
    predicted = [he.verdict(s, 0.3, 0.7) for s in frame["fused"]]
    expected = f1_score(frame["gold_verdict"], predicted, labels=he.CLASSES,
                        average="macro", zero_division=0)
    assert result["macro_f1"] == pytest.approx(round(expected, 4))


def test_fast_search_matches_brute_force():
    """search_cutpoints uses cumulative counts instead of re-scoring the split
    for every candidate pair. It must agree with the slow path."""
    rng = np.random.default_rng(7)
    frame = make_frame([
        {"gold_verdict": verdict_label, "nli_prob": float(np.clip(centre + rng.normal(0, 0.12), 0, 1))}
        for verdict_label, centre in
        [("Hallucinated", 0.2)] * 40 + [("Uncertain", 0.5)] * 20 + [("Verified", 0.75)] * 60
    ])
    frame["fused"] = frame["nli_prob"]

    labels = frame["gold_verdict"].map(he.CLASS_CODES).to_numpy(dtype=int)
    fast = he.search_cutpoints(frame["fused"].to_numpy(dtype=float), labels, "macro_f1")

    best = None
    for low in he.CALIBRATION_GRID[::5]:
        for high in he.CALIBRATION_GRID[::5][he.CALIBRATION_GRID[::5] >= low]:
            result = he.metrics(frame, (low, high))
            key = (result["macro_f1"], round(float(high - low), 4))
            if best is None or key > best[0]:
                best = (key, (float(low), float(high)))

    assert he.metrics(frame, fast)["macro_f1"] >= best[0][0], \
        "the fast search must not find a worse optimum than a coarse brute force"


def test_discrimination_auc_holds_the_positive_class_fixed():
    frame = make_frame(
        [{"gold_verdict": "Verified", "nli_prob": 0.6, "gold_source": "human_override"}] * 10
        + [{"gold_verdict": "Hallucinated", "nli_prob": 0.1,
            "gold_source": he.SYNTHETIC_SOURCE}] * 10
        + [{"gold_verdict": "Hallucinated", "nli_prob": 0.6,
            "gold_source": "human_override"}] * 10
    )
    frame["language"] = "en"
    frame["fused"] = frame["nli_prob"]

    auc = he.discrimination_auc(frame, "en")
    assert auc["n_positive"] == 10
    assert auc["vs_synthetic_hallucinated"]["fused_auc"] == pytest.approx(1.0)
    assert auc["vs_human_annotated_hallucinated"]["fused_auc"] == pytest.approx(0.5)


# --- IMPROVEMENT_PLAN.md 1.2 / 1.3 -------------------------------------------

def test_metrics_with_ci_reports_intervals_and_positive_count():
    import pandas as pd
    frame = pd.DataFrame({
        "gold_verdict": ["Hallucinated"] * 3 + ["Verified"] * 7,
        "fused": [0.1, 0.2, 0.9] + [0.9] * 7,
    })
    m = he.metrics(frame, (0.35, 0.65), ci=True)
    assert m["n"] == 10 and m["n_hallucinated"] == 3
    assert m["too_few_positives"] is True  # 3 < MIN_POSITIVES_TO_INTERPRET
    lo, hi = m["hallucinated_f1_ci95"]
    assert 0.0 <= lo <= m["hallucinated_f1"] <= hi <= 1.0
    lo, hi = m["accuracy_ci95"]
    assert 0.0 <= lo <= m["accuracy"] <= hi <= 1.0
    assert "accuracy_ci95" not in he.metrics(frame, (0.35, 0.65))  # off by default


def test_committed_split_shares_no_source_question():
    import pandas as pd
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    train = pd.read_csv(root / "gold_train_clean.csv")
    test = pd.read_csv(root / "gold_test_clean.csv")
    assert not set(train.source_query_id) & set(test.source_query_id)
