"""
Tests for the CMHSA weight trainer, focused on the kg_conf sparsity fix:
missing signals must be MASKED per-row (not read as 0.0), and the training-time
fusion must be identical to CMHSAScorer.score_claim's inference-time fusion.
"""

import csv

import pytest
import torch

from member1_model.cmhsa import CMHSAScorer, ClaimSubScores
from member1_model.train_weights import (
    _fused_scores,
    _parse_signal,
    load_training_rows,
    train_language_weights,
)

TRAINING_COLUMNS = ["claim_id", "language", "sem_sim", "nli_prob", "kg_conf", "gold_verdict"]


def _write_training_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRAINING_COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def test_parse_signal_blank_becomes_nan():
    assert _parse_signal("") != _parse_signal("")  # NaN
    assert _parse_signal(None) != _parse_signal(None)  # NaN
    assert _parse_signal("0.42") == pytest.approx(0.42)
    # A real 0.0 is a value, NOT a missing signal.
    assert _parse_signal("0.0") == 0.0


def test_load_training_rows_masks_blanks_and_filters(tmp_path):
    path = tmp_path / "training.csv"
    _write_training_csv(
        path,
        [
            {"claim_id": "c1", "language": "en", "sem_sim": "0.9", "nli_prob": "0.8", "kg_conf": "", "gold_verdict": "Verified"},
            {"claim_id": "c2", "language": "en", "sem_sim": "0.2", "nli_prob": "", "kg_conf": "", "gold_verdict": "Hallucinated"},
            {"claim_id": "c3", "language": "hi", "sem_sim": "0.5", "nli_prob": "0.5", "kg_conf": "0.5", "gold_verdict": "Verified"},  # other language
            {"claim_id": "c4", "language": "en", "sem_sim": "", "nli_prob": "", "kg_conf": "", "gold_verdict": "Verified"},  # no signal at all
            {"claim_id": "c5", "language": "en", "sem_sim": "0.7", "nli_prob": "0.6", "kg_conf": "0.5", "gold_verdict": ""},  # unannotated
        ],
    )
    X, mask, y, verdicts = load_training_rows(path, "en")

    # Only c1 and c2 survive: c3 is Hindi, c4 has no signal, c5 is unannotated.
    assert X.shape == (2, 3)
    assert mask[0].tolist() == [True, True, False]
    assert mask[1].tolist() == [True, False, False]
    assert y.tolist() == [1.0, 0.0]


def test_load_training_rows_raises_when_no_rows_for_language(tmp_path):
    path = tmp_path / "training.csv"
    _write_training_csv(
        path,
        [{"claim_id": "c1", "language": "en", "sem_sim": "0.9", "nli_prob": "0.8", "kg_conf": "", "gold_verdict": "Verified"}],
    )
    with pytest.raises(ValueError):
        load_training_rows(path, "mr")


def test_fused_scores_matches_scorer_full_and_partial(monkeypatch):
    """The whole point of the fix: training-time fusion == inference-time fusion,
    including the renormalisation over present signals when one is missing.
    At inference a KG answer now overrides the fusion (cmhsa.KG_DECIDES), so the
    fusion itself is compared with that rule switched off; the KG-missing row is
    fused the same way either way."""
    from member1_model import cmhsa
    monkeypatch.setattr(cmhsa, "KG_DECIDES", False)
    scorer = CMHSAScorer()
    scorer.load_weights("en", alpha=0.5, beta=0.3, gamma=0.2)
    model = scorer._models["en"]  # reuse the exact same weights the scorer uses

    X = torch.tensor([[0.9, 0.8, 0.7], [0.8, 0.8, float("nan")]])
    mask = ~torch.isnan(X)
    fused = _fused_scores(model, X, mask)

    expected_full = scorer.score_claim(ClaimSubScores("c0", 0.9, 0.8, 0.7), "en").hallu_score
    expected_partial = scorer.score_claim(ClaimSubScores("c1", 0.8, 0.8, None), "en").hallu_score

    assert fused[0].item() == pytest.approx(expected_full, abs=1e-5)
    assert fused[1].item() == pytest.approx(expected_partial, abs=1e-5)
    # Sanity: the kg-missing row renormalises to just sem_sim+nli (0.5,0.3)->/0.8.
    assert fused[1].item() == pytest.approx(0.8, abs=1e-5)


def test_training_runs_and_warns_when_kg_conf_absent(tmp_path, capsys):
    """End-to-end: training must succeed with kg_conf blank on every row
    (the real-world case) and must surface that gamma is unlearned."""
    path = tmp_path / "training.csv"
    _write_training_csv(
        path,
        [
            {"claim_id": "c0", "language": "en", "sem_sim": "0.9", "nli_prob": "0.7", "kg_conf": "", "gold_verdict": "Verified"},
            {"claim_id": "c1", "language": "en", "sem_sim": "0.2", "nli_prob": "0.1", "kg_conf": "", "gold_verdict": "Hallucinated"},
            {"claim_id": "c2", "language": "en", "sem_sim": "0.8", "nli_prob": "0.6", "kg_conf": "", "gold_verdict": "Verified"},
            {"claim_id": "c3", "language": "en", "sem_sim": "0.3", "nli_prob": "0.2", "kg_conf": "", "gold_verdict": "Hallucinated"},
            {"claim_id": "c4", "language": "en", "sem_sim": "0.5", "nli_prob": "0.5", "kg_conf": "", "gold_verdict": "Uncertain"},
        ],
    )
    alpha, beta, gamma = train_language_weights(path, "en", epochs=50)

    # Softmax constraint holds regardless of missing signals.
    assert alpha + beta + gamma == pytest.approx(1.0, abs=1e-4)
    assert all(0.0 <= w <= 1.0 for w in (alpha, beta, gamma))

    out = capsys.readouterr().out
    assert "WARNING" in out and "kg_conf" in out  # gamma flagged as unlearned
