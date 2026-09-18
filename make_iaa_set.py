"""
make_iaa_set.py  --  builds a BLIND inter-annotator-agreement overlap set from
gold_final.csv, for two people to label independently so we can compute a clean
human-human Cohen's kappa (PRD Section 11.2 Step 6, target kappa >= 0.65).

Each row gives the annotator the CONTEXT they need to judge the claim:
  - source_question  (the original query the LLM was asked)
  - claim_text       (the atomic claim they must judge)
  - full_response    (the whole LLM answer, for disambiguating fragments)
The AI's verdict and the three signal scores are withheld (no anchoring).
Stratified by (language x verdict) so all three classes appear in both languages.

Writes into iaa/ :
  iaa_overlap_ANNOTATOR_A.xlsx / .csv   blind, to fill (dropdown on verdict)
  iaa_overlap_ANNOTATOR_B.xlsx / .csv   identical copy for the 2nd annotator
  iaa_key_DO_NOT_SHARE.csv              claim_id -> annotator-1 verdict (private)
  IAA_INSTRUCTIONS.md
"""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
from openpyxl.styles import Font, Alignment
from openpyxl.worksheet.datavalidation import DataValidation

GOLD = "gold_final.csv"
SRC = "final annotator file(Sheet1) (1).csv"   # intact Original Query / Full Response Context
OUTDIR = Path("iaa")
TARGET = 50
SEED = 42

COLW = {"claim_id": 22, "language": 8, "domain": 12, "source_question": 50,
        "claim_text": 60, "full_response": 60, "verdict": 16, "evidence_url": 30, "notes": 28}
WRAP = {"source_question", "claim_text", "full_response", "notes"}


def has_dev(v): return any("ऀ" <= ch <= "ॿ" for ch in str(v))


def write_xlsx(df: pd.DataFrame, path: Path) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="IAA")
        ws = w.sheets["IAA"]
        ws.freeze_panes = "A2"
        for i, col in enumerate(df.columns, start=1):
            letter = ws.cell(row=1, column=i).column_letter
            ws.column_dimensions[letter].width = COLW.get(col, 18)
            ws.cell(row=1, column=i).font = Font(bold=True)
            if col in WRAP:
                for r in range(2, len(df) + 2):
                    ws.cell(row=r, column=i).alignment = Alignment(wrap_text=True, vertical="top")
        # dropdown on the verdict column
        vcol = list(df.columns).index("verdict") + 1
        letter = ws.cell(row=1, column=vcol).column_letter
        dv = DataValidation(type="list", formula1='"Verified,Hallucinated,Uncertain"', allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(f"{letter}2:{letter}{len(df) + 1}")


def main() -> None:
    df = pd.read_csv(GOLD, encoding="utf-8")
    src = pd.read_csv(SRC, encoding="utf-8").set_index("Claim ID")
    OUTDIR.mkdir(exist_ok=True)

    picks = []
    for (lang, verdict), grp in df.groupby(["language", "gold_verdict"]):
        k = min(len(grp), max(4, round(TARGET * len(grp) / len(df))))
        picks.append(grp.sample(n=k, random_state=SEED))
    sample = pd.concat(picks).sample(frac=1, random_state=SEED).reset_index(drop=True)

    q = src["Original Query"].reindex(sample["claim_id"]).values
    resp = src["Full Response Context"].reindex(sample["claim_id"]).values

    blind = pd.DataFrame({
        "claim_id": sample["claim_id"],
        "language": sample["language"],
        "domain": sample["domain"],
        "source_question": q,
        "claim_text": sample["claim_text"],
        "full_response": resp,
        "verdict": "",         # fill: Verified / Hallucinated / Uncertain
        "evidence_url": "",    # fill
        "notes": "",           # optional
    })

    # retire the old context-free files (skip any locked/open in Excel)
    for old in OUTDIR.glob("iaa_overlap_ANNOTATOR_*"):
        try:
            old.unlink()
        except OSError:
            print(f"note: couldn't remove {old.name} (open in Excel?) — ignore it, use the iaa_annotator_* files")

    for tag in ("A", "B"):
        write_xlsx(blind, OUTDIR / f"iaa_annotator_{tag}.xlsx")
        blind.to_csv(OUTDIR / f"iaa_annotator_{tag}.csv", index=False, encoding="utf-8-sig")
    sample[["claim_id", "language", "gold_verdict"]].rename(
        columns={"gold_verdict": "annotator1_verdict"}
    ).to_csv(OUTDIR / "iaa_key_DO_NOT_SHARE.csv", index=False, encoding="utf-8-sig")

    missing_q = int(pd.isna(q).sum())
    sys.stdout.buffer.write(b"IAA overlap set rebuilt (with question + response context).\n")
    print(f"claims: {len(sample)}   rows missing a source_question: {missing_q}")
    print("by (language, verdict):")
    print(sample.groupby(["language", "gold_verdict"]).size().to_string())
    hi = blind[blind["language"] == "hi"]
    print(f"Hindi: {len(hi)}  question Devanagari intact: {hi['source_question'].apply(has_dev).sum()}")

    instructions = f"""# IAA Labeling Task — {len(sample)} claims

You are one of **two** people labeling the SAME {len(sample)} claims, **independently**.
Do NOT discuss or compare until both files are submitted — that is the whole point.

Open **your .xlsx** in Excel (Hindi displays correctly):
- Annotator A -> `iaa_annotator_A.xlsx`
- Annotator B -> `iaa_annotator_B.xlsx`

## Each row gives you
- **source_question** — the question the AI was asked (context)
- **claim_text** — the ONE atomic claim you must judge
- **full_response** — the AI's whole answer, to understand fragment claims

## Fill the `verdict` column (dropdown) with one of:
| Verdict | Meaning |
|---|---|
| **Verified** | Factually correct; clear supporting evidence. |
| **Hallucinated** | Factually wrong, fabricated, or contradicted by evidence. |
| **Uncertain** | Can't confirm or deny — real ambiguity, opinion, or missing/conflicting evidence. (NOT "didn't check".) |

**If the claim bundles several facts (common in Hindi):** judge it by its WORST part —
any part false -> Hallucinated; else any part unverifiable -> Uncertain; else Verified.
Note the offending part in `notes`.

- Judge **only the `claim_text`**, using the question/response for context. Judge factual truth, not writing quality.
- Put your best source in `evidence_url` (blank OK for Uncertain-no-evidence).
- Hindi rows: an English source confirming/denying the same fact is fine.
- ~2-3 min per claim.

## When done
Save and send both completed .xlsx files back. Kappa is computed with
`compute_iaa.py`; target >= 0.65 (PRD 5.2). A low number means we tighten the
guideline and relabel — the normal pilot outcome, not a failure.
"""
    (OUTDIR / "IAA_INSTRUCTIONS.md").write_text(instructions, encoding="utf-8")
    print("wrote iaa/: ANNOTATOR_A/B (.xlsx + .csv), key (private), IAA_INSTRUCTIONS.md")


if __name__ == "__main__":
    main()
