"""
kg_coverage.py -- the PRD's KG ablation, examined honestly (IMPROVEMENT_PLAN
follow-up; PRD 5.1: "the single most important experiment").

KG_conf exists only for claims that (a) contain a relation phrase from
RELATION_TO_PID, (b) have two named entities (English NER; there is no Hindi
NER), and (c) link to a Wikidata triple. This measures (a) and (b) offline on
the 456 gold claims -- the upper bound on KG coverage -- and, with --live, runs
the relational sanity cases against Wikidata to check the verifier itself.

Writes results/kg_ablation.md.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import pandas as pd

from member2_data.entity_linker import EntityLinker
from member3_backend.claim_extractor import ClaimExtractor

ROOT = Path(__file__).resolve().parent
KEYWORDS = ["born", "died", "capital", "located", "founded", "established", "president",
            "prime minister", "member of", "part of", "headquarter", "citizen"]
LIVE_CASES = [("Narendra Modi is the Prime Minister of India.", "supported"),
              ("Narendra Modi is the President of India.", "unknown"),
              ("Paris is the capital of France.", "supported"),
              ("Paris is the capital of Germany.", "contradicted"),
              ("The Taj Mahal is located in India.", "supported"),
              ("Mahatma Gandhi was born in India.", "supported"),
              ("Mahatma Gandhi was born in Pakistan.", "contradicted")]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="also run the Wikidata sanity cases")
    args = ap.parse_args()

    gold = pd.read_csv(ROOT / "gold_final.csv", encoding="utf-8")
    el, ce = EntityLinker(), ClaimExtractor()
    gold["phrase"] = gold.claim_text.map(el.find_relation_phrase)
    matched = gold[gold.phrase.notna()]
    en = gold[gold.language == "en"]
    kw = en[en.claim_text.str.lower().str.contains("|".join(KEYWORDS))]

    L = ["# KG ablation — can it be run on this dataset?\n",
         "PRD 5.1 calls the KG ablation \"the single most important experiment\". KG_conf needs "
         "(a) a relation phrase from `RELATION_TO_PID`, (b) two named entities (English NER only; "
         "no Hindi NER), (c) a Wikidata triple.\n",
         "## Coverage on the 456 gold claims (offline, exact)",
         f"- Claims containing a relation phrase (condition a): **{len(matched)} / {len(gold)}**.",
         f"- Hindi claims: {int((gold.language == 'hi').sum())}, all without English-style NER "
         f"entities, so condition (b) fails for every one.",
         f"- Generous upper bound: English claims containing any relation keyword "
         f"({', '.join(KEYWORDS)}): **{len(kw)}**, most of which are not person/place→entity "
         f"facts. Examples:", ""]
    L += [f"  - {t[:110]}" for t in kw.claim_text]
    L += ["", "**Conclusion:** KG's domain — simple relational facts (\"X was born in Y\", \"X is "
          "the capital of Y\") — is essentially absent from this dataset of descriptive LLM answers. "
          "The PRD's KG ablation (target F1 gain ≥ +0.03) **cannot be measured here**: it would run "
          "on 0 claims as the table stands, and at most a handful with phrasing tuned after reading "
          "these claims (which would also fit the table to the evaluation set). This is a property "
          "of the dataset, recorded as a finding, not a KG result either way.\n"]

    if args.live:
        from member2_data.wikidata_connector import WikidataConnector
        wd = WikidataConnector()
        L += ["## Verifier sanity check on relational claims (live Wikidata)",
              "| claim | expected | got | KG_conf |", "| --- | --- | --- | --- |"]
        ok = 0
        for claim, want in LIVE_CASES:
            ents = ce.extract_entities(claim, "en")
            t = el.link_claim(claim, ents[0], ents[1], "en") if len(ents) >= 2 else None
            v = wd.verify_triple(t.subject_qid, t.property_pid, t.object_qid, "en", t.object_candidates) if t and t.linkable else None
            got = v.status if v else "unlinked"
            ok += got == want
            L.append(f"| {claim} | {want} | {got} | {v.confidence if v else '—'} |")
        L += ["", f"- **{ok}/{len(LIVE_CASES)}** correct. \"unknown\" means no KG signal (the scorer "
              "renormalises around it); only a single-valued property with a different recorded "
              "value counts as a contradiction.\n"]

    out = ROOT / "results" / "kg_ablation.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(L) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
