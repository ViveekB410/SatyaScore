"""
compute_iaa.py  --  Cohen's kappa on the completed IAA overlap set.

Run AFTER both annotators fill their files:
    .venv/Scripts/python.exe compute_iaa.py

Reports pairwise kappa between A and B (the clean human-human number), and, if
present, each annotator vs the original annotator-1 key. Honest about n and the
class distribution, since kappa on a small skewed set is easy to over-read.
"""
from __future__ import annotations
from pathlib import Path
import pandas as pd
from sklearn.metrics import cohen_kappa_score, confusion_matrix

IAA = Path("iaa")
NORM = {
    "verified": "Verified", "ok": "Verified", "correct": "Verified", "true": "Verified",
    "hallucinated": "Hallucinated", "hallucination": "Hallucinated", "false": "Hallucinated",
    "uncertain": "Uncertain", "unsure": "Uncertain", "unclear": "Uncertain",
}
LABELS = ["Verified", "Uncertain", "Hallucinated"]
TARGET = 0.65


def _read(stem: Path):
    """Prefer the .xlsx an annotator filled in Excel; fall back to .csv."""
    xlsx, csv = stem.with_suffix(".xlsx"), stem.with_suffix(".csv")
    if xlsx.exists():
        return pd.read_excel(xlsx)
    return pd.read_csv(csv, encoding="utf-8")


def load(stem: Path, col):
    df = _read(stem)
    df[col] = df[col].astype(str).str.strip().str.lower().map(NORM)
    return df.set_index("claim_id")[col]


def report(name, a, b):
    shared = a.index.intersection(b.index)
    both = pd.DataFrame({"a": a.reindex(shared), "b": b.reindex(shared)}).dropna()
    n = len(both)
    if n < 2:
        print(f"[{name}] only {n} claims labeled by both — cannot compute kappa yet.")
        return
    k = cohen_kappa_score(both["a"], both["b"], labels=LABELS)
    agree = (both["a"] == both["b"]).mean()
    print(f"\n=== {name} ===")
    print(f"n (both labeled): {n}   raw agreement: {agree:.3f}   Cohen's kappa: {k:.3f}   "
          f"{'MEETS' if k >= TARGET else 'BELOW'} target {TARGET}")
    print("confusion (rows=A, cols=B, order Verified/Uncertain/Hallucinated):")
    print(confusion_matrix(both["a"], both["b"], labels=LABELS))
    missing = len(a.index.union(b.index)) - n
    if missing:
        print(f"note: {missing} claims not yet labeled by both.")


def main() -> None:
    stem_a = IAA / "iaa_annotator_A"
    stem_b = IAA / "iaa_annotator_B"
    if not (stem_a.with_suffix(".xlsx").exists() or stem_a.with_suffix(".csv").exists()):
        print("Fill iaa/iaa_annotator_A and _B (.xlsx or .csv) first.")
        return
    a = load(stem_a, "verdict")
    b = load(stem_b, "verdict")
    if a.notna().sum() == 0 or b.notna().sum() == 0:
        print(f"Not labeled yet (A: {a.notna().sum()} filled, B: {b.notna().sum()} filled).")
        return

    report("Annotator A vs Annotator B  (the clean human-human kappa)", a, b)

    key_stem = IAA / "iaa_key_DO_NOT_SHARE"
    if key_stem.with_suffix(".csv").exists() or key_stem.with_suffix(".xlsx").exists():
        key = load(key_stem, "annotator1_verdict")
        report("Annotator A vs original Annotator-1 label", a, key)
        report("Annotator B vs original Annotator-1 label", b, key)

    print("\nReminder: n is a pilot-sized sample; report kappa WITH its n and the "
          "class counts, and treat a single low number as a signal to refine the "
          "guideline, not a verdict on the whole dataset.")


if __name__ == "__main__":
    main()
