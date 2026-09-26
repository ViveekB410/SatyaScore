"""
round3_signals.py -- KG relational pilot, step 2 (round3/PREREGISTRATION.md).
Run after round3_generate.py and BEFORE the labels come back.

Per pilot claim, with the live system's settings (demo corpus, top-3 retrieval,
relevance threshold 0.3):
  nli_net     net score of the most decisive of the top-3 passages (as the API)
  contra_top1 1 - P(contradiction) on the top-1 passage (as Phase 3)
  kg_conf     fixed verifier: 1.0 supported / 0.0 contradicted / blank unknown
  kg_status   supported / contradicted / unknown / unlinked

Writes round3/signals_round3.csv.

    .venv/Scripts/python.exe round3_signals.py
"""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
import pandas as pd

from member1_model.nli_scorer import NLIScorer
from member2_data.entity_linker import EntityLinker
from member2_data.wikidata_connector import WikidataConnector
from member3_backend.claim_extractor import ClaimExtractor
from member3_backend.pipeline import MIN_RELEVANCE_THRESHOLD, NLI_EVIDENCE_TOP_K
from retrieval_eval import corpus_vectors, encode

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "round3"


def kg(claim: str, ce: ClaimExtractor, el: EntityLinker, wd: WikidataConnector):
    """Mirror of DetectionPipeline._try_kg_verification, keeping the status."""
    if not el.find_relation_pid(claim):
        return None, "unlinked"
    ents = ce.extract_entities(claim, "en")
    if len(ents) < 2:
        return None, "unlinked"
    t = el.link_claim(claim_text=claim, subject_text=ents[0], object_text=ents[1], language="en")
    if not t.linkable:
        return None, "unlinked"
    v = wd.verify_triple(t.subject_qid, t.property_pid, t.object_qid, "en", t.object_candidates)
    return v.confidence, v.status


KG_ATTEMPTS, KG_RETRY_WAIT_S = 3, 5


def kg_stable(claim, ce, el, wd):
    """A failed Wikidata search (e.g. rate-limited) looks the same as "no match"
    (unlinked) and a failed lookup as "unknown". Found on the first run: one claim
    was unlinked, then contradicted on re-run. Retry non-answers; a genuine
    unlinked/unknown is stable, so retries cannot manufacture an answer."""
    import time
    conf, status = kg(claim, ce, el, wd)
    for _ in range(KG_ATTEMPTS - 1):
        if status in ("supported", "contradicted"):
            break
        time.sleep(KG_RETRY_WAIT_S)
        conf, status = kg(claim, ce, el, wd)
    return conf, status


def main() -> None:
    df = pd.read_csv(OUT / "claims_round3.csv", encoding="utf-8")
    passages = json.loads((ROOT / "corpus_passages_demo.json").read_text(encoding="utf-8"))
    texts = [p["text"] for p in passages]
    S = encode("xlmr", df.claim_text.tolist(), passage=False) @ corpus_vectors("xlmr", texts, "demo").T
    order = np.argsort(-S, axis=1)[:, :NLI_EVIDENCE_TOP_K]

    pairs, owner = [], []
    for i, row in enumerate(order):
        for rank, j in enumerate(row):
            if S[i, j] >= MIN_RELEVANCE_THRESHOLD:
                pairs.append((texts[j], df.claim_text[i], rank))
                owner.append(i)
    res = NLIScorer().score_batch(claim_ids=[str(o) for o in owner],
                                  premises=[p for p, _, _ in pairs],
                                  hypotheses=[h for _, h, _ in pairs])
    net = [[] for _ in range(len(df))]
    contra = [None] * len(df)
    for (_, _, rank), i, r in zip(pairs, owner, res):
        net[i].append(0.5 + 0.5 * (r.entailment_prob - r.contradiction_prob))
        if rank == 0:
            contra[i] = 1 - r.contradiction_prob
    df["nli_net"] = [max(n, key=lambda s: abs(s - 0.5)) if n else np.nan for n in net]
    df["contra_top1"] = contra
    df["top1_sim"] = S.max(axis=1)

    ce, el, wd = ClaimExtractor(), EntityLinker(), WikidataConnector()
    kgs = [kg_stable(c, ce, el, wd) for c in df.claim_text]
    df["kg_conf"] = [k for k, _ in kgs]
    df["kg_status"] = [s for _, s in kgs]
    df[["claim_id", "claim_text", "relation_phrase", "nli_net", "contra_top1", "top1_sim",
        "kg_conf", "kg_status"]].to_csv(OUT / "signals_round3.csv", index=False, encoding="utf-8")
    print(f"wrote round3/signals_round3.csv: {len(df)} claims; KG status "
          f"{df.kg_status.value_counts().to_dict()}")


if __name__ == "__main__":
    main()
