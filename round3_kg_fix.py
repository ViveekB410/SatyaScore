"""
round3_kg_fix.py -- EXPLORATORY, not pre-registered. Re-runs only the KG step of
round 3 with the place-linking fix (EntityLinker.PLACE_PIDS: a place is every
item with exactly the claimed name, not the top search hit), after the labels
were seen. The locked signals (round3/signals_round3.csv) and the pre-registered
result (results/round3_kg_pilot.md) are left untouched.

    .venv/Scripts/python.exe round3_kg_fix.py

Writes round3/signals_round3_kgfix.csv and results/round3_kg_fix_exploratory.md.
"""
from __future__ import annotations
from pathlib import Path

import pandas as pd

from analyze_round3 import SENSITIVITY_EXCLUDE, discrimination
from compute_round2 import _norm1
from member1_model.calibration import wilson
from member2_data.entity_linker import EntityLinker
from member2_data.wikidata_connector import WikidataConnector
from member3_backend.claim_extractor import ClaimExtractor
from round3_signals import kg_stable

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "round3"


def main() -> None:
    locked = pd.read_csv(OUT / "signals_round3.csv").set_index("claim_id")
    ce, el, wd = ClaimExtractor(), EntityLinker(), WikidataConnector()
    new = locked.copy()
    kgs = [kg_stable(c, ce, el, wd) for c in new.claim_text]
    new["kg_conf"] = [k for k, _ in kgs]
    new["kg_status"] = [s for _, s in kgs]
    new.reset_index().to_csv(OUT / "signals_round3_kgfix.csv", index=False, encoding="utf-8")

    A = pd.read_excel(OUT / "round3_annotator_A.xlsx").set_index("claim_id")
    B = pd.read_excel(OUT / "round3_annotator_B.xlsx").set_index("claim_id")
    d = pd.DataFrame({"a": A.verdict.map(_norm1), "b": B.verdict.map(_norm1)}).dropna()
    gold_ids = d[(d.a == d.b) & d.a.isin(["Verified", "Hallucinated"])].index

    changed = new[new.kg_status != locked.kg_status]
    L = ["# Round 3 — KG place-linking fix: EXPLORATORY re-run\n",
         "> **Not pre-registered.** The fix was made after the labels were seen, to correct a "
         "diagnosed bug (place names linked to non-places: \"Erode\" → a given name, \"Naigaon\" → "
         "a monorail station, \"Niphad\" → an insect genus, \"Bodua\" → an encyclopedia article). "
         "Only the KG signal was recomputed; NLI and labels are unchanged. The pre-registered "
         "result stays `results/round3_kg_pilot.md`. Labels are AI-assisted, annotator-verified "
         "(Deviation 3).\n",
         f"- KG status before: {locked.kg_status.value_counts().to_dict()}",
         f"- KG status after: {new.kg_status.value_counts().to_dict()}\n",
         "## Claims whose KG status changed", "| claim | gold | before | after |",
         "| --- | --- | --- | --- |"]
    for cid, r in changed.iterrows():
        g = d.a[cid] if cid in gold_ids else "(not gold)"
        L.append(f"| {r.claim_text[:90]} | {g} | {locked.kg_status[cid]} | {r.kg_status} |")
    L.append("")

    gold = d.loc[gold_ids].join(new)
    L.append("## KG correctness on gold claims")
    for status, label in (("supported", "Verified"), ("contradicted", "Hallucinated")):
        s = gold[gold.kg_status == status]
        k = int((s.a == label).sum())
        lo, hi = wilson(k, len(s))
        L.append(f"- KG **{status}** → gold {label}: {k}/{len(s)}"
                 + (f" ({k / len(s):.0%}, 95% CI [{lo:.0%}, {hi:.0%}])" if len(s) else ""))
    L.append("")
    L += discrimination(gold, "All gold claims (exploratory)")
    L += discrimination(gold.drop([c for c in SENSITIVITY_EXCLUDE if c in gold.index]),
                        "Without the 3 coreference-garbled claims (exploratory)")
    out = ROOT / "results" / "round3_kg_fix_exploratory.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
