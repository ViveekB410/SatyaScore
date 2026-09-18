"""
inspect_source.py  --  READ ONLY. Touches nothing on disk.

Answers one question before we attempt any recovery: does the authoritative
3-person verification .xlsx (and the unannotated_dataset.csv fallback) still
hold intact Devanagari for the Hindi claim_ids that are currently corrupted to
'?' in the gold files, and do the claim_ids line up for a clean join?

Run:
    .venv/Scripts/python.exe inspect_source.py
"""

from __future__ import annotations
import sys
from pathlib import Path

import pandas as pd

XLSX = Path(r"C:\Users\vivek\Downloads\individual_claims_3person_verification_merged.xlsx")
GOLD = ["gold_train_v3.csv", "gold_test_v3.csv"]
FALLBACK = "unannotated_dataset.csv"


def has_devanagari(value) -> bool:
    return any("\u0900" <= ch <= "\u097f" for ch in str(value))


def guess(colnames, *keywords):
    """First column whose name contains any keyword (case-insensitive)."""
    for c in colnames:
        low = str(c).lower()
        if any(k in low for k in keywords):
            return c
    return None


def describe_frame(name, df):
    print("=" * 72)
    print(f"{name}   shape={df.shape}")
    print("columns:", list(df.columns))
    dev_cols = [c for c in df.columns if df[c].astype(str).apply(has_devanagari).any()]
    print("columns containing Devanagari:", dev_cols or "NONE")
    idc = guess(df.columns, "claim_id", "claimid", "id")
    txc = guess(df.columns, "claim_text", "claim", "text", "response", "sentence")
    print(f"guessed id column   -> {idc!r}")
    print(f"guessed text column -> {txc!r}")
    if txc is not None:
        n_dev = df[txc].astype(str).apply(has_devanagari).sum()
        print(f"rows with Devanagari in {txc!r}: {n_dev} / {len(df)}")
    return idc, txc, dev_cols


def main() -> None:
    # ---- corrupted gold: which hi claim_ids need rescue ----
    gold = pd.concat([pd.read_csv(f, encoding="utf-8") for f in GOLD], ignore_index=True)
    hi = gold[gold["language"] == "hi"].copy()
    hi_ids = set(hi["claim_id"])
    corrupt = hi[~hi["claim_text"].astype(str).apply(has_devanagari)]
    print(f"GOLD v3: {len(gold)} rows, {len(hi)} Hindi, "
          f"{len(corrupt)} Hindi rows with NO Devanagari (corrupted).")
    print(f"distinct Hindi claim_ids needing recovery: {len(hi_ids)}")

    # ---- fallback source ----
    fb = pd.read_csv(FALLBACK, encoding="utf-8")
    fb_id, fb_tx, _ = describe_frame(FALLBACK, fb)
    if fb_id and fb_tx:
        m = fb[fb[fb_id].isin(hi_ids)]
        recoverable = m[m[fb_tx].astype(str).apply(has_devanagari)]
        print(f">>> {FALLBACK}: {m[fb_id].nunique()} of {len(hi_ids)} hi claim_ids "
              f"present; {recoverable[fb_id].nunique()} have intact Devanagari.")

    # ---- authoritative xlsx ----
    if not XLSX.exists():
        print("=" * 72)
        print(f"XLSX NOT FOUND at {XLSX}")
        return
    try:
        sheets = pd.read_excel(XLSX, sheet_name=None)
    except ImportError:
        print("=" * 72)
        print("Need openpyxl. Run:  .venv/Scripts/python.exe -m pip install openpyxl")
        return
    print("=" * 72)
    print(f"XLSX sheets: {list(sheets.keys())}")
    for sh, df in sheets.items():
        xid, xtx, _ = describe_frame(f"XLSX[{sh}]", df)
        if xid and xtx:
            m = df[df[xid].astype(str).isin(hi_ids)]
            recoverable = m[m[xtx].astype(str).apply(has_devanagari)]
            print(f">>> XLSX[{sh}]: {m[xid].astype(str).nunique()} of {len(hi_ids)} "
                  f"hi claim_ids present; {recoverable[xid].astype(str).nunique()} "
                  f"have intact Devanagari.")
        # surface any verdict-like columns for the rebuild
        vcols = [c for c in df.columns if any(k in str(c).lower()
                 for k in ("verdict", "label", "annotat", "verif", "final", "gold"))]
        if vcols:
            print(f"    verdict/annotation-like columns: {vcols}")


if __name__ == "__main__":
    sys.exit(main())
