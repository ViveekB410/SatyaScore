"""
relabel/merge.py -- Version 2 data, steps 1d-1e (relabel/PROTOCOL.md).

Stage 1 (after the four sheets come back):
    .venv/Scripts/python.exe relabel/merge.py
  reads relabel/package/annotator_A..D.xlsx, checks completeness, reports Cohen's kappa per pair and
  overall (binary: Hallucinated vs not; and 4-label), writes results/relabel_agreement.md and
  relabel/package/adjudication.xlsx (only the disagreements, both labels shown, `final_verdict` empty).

Stage 2 (after the adjudication meeting has filled `final_verdict` for every row):
    .venv/Scripts/python.exe relabel/merge.py --final
  writes gold_v2.csv (agreed labels + adjudicated ones, with both original labels kept) and the locked
  grouped split gold_v2_dev.csv / gold_v2_test.csv (60/40 by source question, seed 20261012).
No label is ever filled in by this script.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "relabel" / "package"
LABELS = ["Verified", "Hallucinated", "Uncertain", "Not a claim"]
SEED = 20261012


def cohen_kappa(a: list[str], b: list[str]) -> float:
    """Cohen's kappa for two raters over the same items (nan if undefined)."""
    a, b = np.asarray(a), np.asarray(b)
    cats = sorted(set(a) | set(b))
    if len(a) == 0:
        return float("nan")
    po = float(np.mean(a == b))
    pe = sum(float(np.mean(a == c)) * float(np.mean(b == c)) for c in cats)
    return float("nan") if pe == 1 else (po - pe) / (1 - pe)


def read_sheets(pkg: Path) -> pd.DataFrame:
    rows = []
    for a in "ABCD":
        df = pd.read_excel(pkg / f"annotator_{a}.xlsx", dtype=str).fillna("")
        df["annotator"] = a
        rows.append(df[["claim_id", "annotator", "verdict", "evidence_url", "notes"]])
    long = pd.concat(rows, ignore_index=True)
    long["verdict"] = long.verdict.str.strip()
    bad = long[~long.verdict.isin(LABELS)]
    if len(bad):
        per = bad.groupby("annotator").size().to_dict()
        sys.exit(f"{len(bad)} rows have no valid label yet (per annotator: {per}). Finish labelling first.")
    return long


def stage1(pkg: Path, out_md: Path) -> None:
    key = pd.read_csv(pkg / "assignment_key.csv", encoding="utf-8")
    long = read_sheets(pkg)
    ev = key[key.role == "evaluation"]
    got = long.groupby("claim_id").size()
    missing = ev[~ev.claim_id.isin(got[got == 2].index)]
    if len(missing):
        sys.exit(f"{len(missing)} evaluation claims do not have exactly two labels.")
    wide = long.sort_values("annotator").groupby("claim_id").agg(
        annotators=("annotator", "".join), v1=("verdict", "first"), v2=("verdict", "last"),
        e1=("evidence_url", "first"), e2=("evidence_url", "last"), n1=("notes", "first"), n2=("notes", "last"))
    wide = wide.join(key.set_index("claim_id")[["language", "set"]])
    L = ["# Version 2 labels: agreement before adjudication", "",
         "| pair | claims | raw agreement | kappa (Hallucinated vs not) | kappa (4 labels) |", "|---|---|---|---|---|"]
    for pair, g in list(wide.groupby("annotators")) + [("all", wide)]:
        hb = lambda s: (s == "Hallucinated").map({True: "H", False: "n"})
        L.append(f"| {pair} | {len(g)} | {np.mean(g.v1 == g.v2):.0%} | {cohen_kappa(hb(g.v1), hb(g.v2)):.2f} | "
                 f"{cohen_kappa(g.v1, g.v2):.2f} |")
    for lang, g in wide.groupby("language"):
        L.append(f"| all, {lang} | {len(g)} | {np.mean(g.v1 == g.v2):.0%} | "
                 f"{cohen_kappa((g.v1 == 'Hallucinated'), (g.v2 == 'Hallucinated')):.2f} | {cohen_kappa(g.v1, g.v2):.2f} |")
    dis = wide[wide.v1 != wide.v2].reset_index()
    L += ["", f"Disagreements to adjudicate: {len(dis)} of {len(wide)}."]
    out_md.write_text("\n".join(L) + "\n", encoding="utf-8")
    claims = pd.concat([pd.read_csv(ROOT / "relabel" / f, encoding="utf-8")
                        for f in ("claims_v2_original.csv", "claims_v2_new_hi.csv")]).set_index("claim_id")
    adj = dis.join(claims[["source_question", "claim_text", "full_response"]], on="claim_id")
    adj["final_verdict"] = ""
    adj["reason"] = ""
    adj.to_excel(pkg / "adjudication.xlsx", index=False)
    print("\n".join(L))


def stage2(pkg: Path, out: Path) -> None:
    key = pd.read_csv(pkg / "assignment_key.csv", encoding="utf-8")
    long = read_sheets(pkg)
    adj = pd.read_excel(pkg / "adjudication.xlsx", dtype=str).fillna("")
    if (~adj.final_verdict.str.strip().isin(LABELS)).any():
        sys.exit("adjudication.xlsx: every row needs a final_verdict from the meeting.")
    wide = long.sort_values("annotator").groupby("claim_id").agg(
        annotators=("annotator", "".join), label_1=("verdict", "first"), label_2=("verdict", "last"))
    wide["gold_verdict"] = np.where(wide.label_1 == wide.label_2, wide.label_1, "")
    wide["gold_source"] = np.where(wide.label_1 == wide.label_2, "agreed", "adjudicated")
    fin = adj.set_index("claim_id").final_verdict.str.strip()
    wide.loc[fin.index, "gold_verdict"] = fin
    claims = pd.concat([pd.read_csv(ROOT / "relabel" / f, encoding="utf-8")
                        for f in ("claims_v2_original.csv", "claims_v2_new_hi.csv")])
    gold = claims.merge(wide.reset_index(), on="claim_id", how="inner")
    gold = gold[gold.gold_verdict != "Not a claim"].reset_index(drop=True)
    gold.to_csv(out / "gold_v2.csv", index=False, encoding="utf-8")
    strata = gold.language + "_" + gold.gold_verdict
    folds = list(StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED).split(gold, strata, gold.source_query_id))
    test_idx = np.concatenate([folds[0][1], folds[1][1]])  # 2 of 5 folds = 40%, fixed in the protocol
    is_test = gold.index.isin(test_idx)
    gold[~is_test].to_csv(out / "gold_v2_dev.csv", index=False, encoding="utf-8")
    gold[is_test].to_csv(out / "gold_v2_test.csv", index=False, encoding="utf-8")
    assert not set(gold[is_test].source_query_id) & set(gold[~is_test].source_query_id)
    print(f"gold_v2.csv: {len(gold)} claims (Not a claim excluded); dev {int((~is_test).sum())}, test {int(is_test.sum())}")
    print(gold.groupby(["language", "gold_verdict"]).size().unstack(fill_value=0).to_string())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--pkg", default=str(PKG))
    ap.add_argument("--out", default=str(ROOT), help="where gold_v2*.csv and results/ go (default: the project)")
    args = ap.parse_args()
    pkg = Path(args.pkg)
    if args.final:
        stage2(pkg, Path(args.out))
    else:
        (Path(args.out) / "results").mkdir(exist_ok=True)
        stage1(pkg, Path(args.out) / "results" / "relabel_agreement.md")


if __name__ == "__main__":
    main()
