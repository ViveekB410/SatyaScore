"""
FR-04: "SHALL output a final HalluScore in [0.0, 1.0] with a confidence interval."

A single HalluScore has no sampling interval of its own, so the interval is put
on what the score means: the probability that a claim with this score is
Verified. The training split is cut into equal-count score bins; in each bin the
share of claims that are Verified is that probability, with a 95% Wilson
interval from the bin's claim count. Fitted on the TRAIN split only
(build_calibration.py); checked on test in results/calibration.md.

Caveat: fitted on the evaluation signals (NLI on the top-1 passage, experiment
corpus). The live API uses the most decisive of the top-3 passages, so its
scores are only approximately on the same scale.
"""
from __future__ import annotations
import bisect
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

N_BINS = 5


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def fit_bins(scores: np.ndarray, verified: np.ndarray, n_bins: int = N_BINS) -> dict:
    """Equal-count bins over the training scores -> per-bin P(Verified) + 95% CI."""
    qs = np.quantile(scores, np.linspace(0, 1, n_bins + 1)[1:-1])
    edges = sorted(set(round(float(q), 6) for q in qs))  # interior cut points
    idx = np.searchsorted(edges, scores, side="right")
    bins = []
    for b in range(len(edges) + 1):
        m = idx == b
        n, k = int(m.sum()), int(verified[m].sum())
        lo, hi = wilson(k, n)
        bins.append({"n": n, "n_verified": k, "p_verified": (k / n) if n else None,
                     "ci95": [round(lo, 4), round(hi, 4)]})
    return {"edges": edges, "bins": bins}


@dataclass
class Calibrated:
    p_verified: float | None
    ci95: tuple[float, float]
    n: int


def lookup(score: float, table: dict) -> Calibrated:
    b = table["bins"][bisect.bisect_right(table["edges"], score)]
    return Calibrated(b["p_verified"], tuple(b["ci95"]), b["n"])


def load_table(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
