"""
recompute_signals.py  --  Stage 2 of the bilingual signal recompute.

Embeds the cached bilingual corpus (corpus_passages.json), builds an EXACT FAISS
index, and recomputes sem_sim + nli_prob for every claim in gold_final.csv
against real (Hindi + English) evidence. Reuses the project's own components
and replicates pipeline.py's contradiction-aware NLI aggregation.

Writes gold_final_scored.csv (new file). NEVER overwrites gold_final.csv.
Old signal values are preserved as sem_sim_old / nli_prob_old for audit.

    .venv/Scripts/python.exe recompute_signals.py --limit 6   # smoke test
    .venv/Scripts/python.exe recompute_signals.py             # full run
"""
from __future__ import annotations
import argparse, json, os, sys
import numpy as np
import pandas as pd

from member1_model.embeddings import CrossLingualEmbedder
from member3_backend.faiss_retriever import FAISSRetriever
from member1_model.nli_scorer import NLIScorer

GOLD = "gold_final.csv"
PASSAGES = "corpus_passages.json"
OUT = "gold_final_scored.csv"
RETRIEVE_K = 5      # for sem_sim (top-1) and candidate evidence
NLI_TOP_K = 1       # NLI over top-1 retrieved (CPU-feasible; top-3 is ~1-2h here)
NLI_MAXLEN = 192    # premise+hypothesis token cap (shorter = much faster on CPU)


def net_nli(results) -> float:
    """Contradiction-aware net score, pick the most decisive (pipeline.py)."""
    nets = [0.5 + 0.5 * (r.entailment_prob - r.contradiction_prob) for r in results]
    return float(max(nets, key=lambda s: abs(s - 0.5))) if nets else float("nan")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="score only first N claims (smoke test)")
    args = ap.parse_args()

    passages = json.loads(open(PASSAGES, encoding="utf-8").read())
    print(f"passages: {len(passages)} (EN {sum(p['lang']=='en' for p in passages)}, "
          f"HI {sum(p['lang']=='hi' for p in passages)})")

    embedder = CrossLingualEmbedder()
    print(f"device: {embedder.device}")

    # --- embed corpus (cached) + build EXACT index (n_clusters=1 -> searches all) ---
    VEC_CACHE = "corpus_vectors.npy"
    vecs = None
    if os.path.exists(VEC_CACHE):
        cached = np.load(VEC_CACHE)
        if cached.shape[0] == len(passages):
            vecs = cached
            print("loaded cached corpus vectors")
    if vecs is None:
        print("embedding corpus (forcing XLM-R for a single comparable vector space)...")
        # Force XLM-R for ALL passages by tagging them 'en': our Hindi is all
        # Devanagari (XLM-R handles it), and MuRIL (the 'hi'+transliterated
        # fallback) lives in a DIFFERENT vector space, so mixing the two would
        # make cosine similarity meaningless. One model = one comparable space.
        vecs = embedder.embed([p["id"] for p in passages],
                              [p["text"] for p in passages],
                              ["en"] * len(passages)).vectors
        np.save(VEC_CACHE, vecs)
        print(f"saved corpus vectors -> {VEC_CACHE}")
    retr = FAISSRetriever(n_clusters=1)
    retr.build_index([p["id"] for p in passages], [p["text"] for p in passages], vecs)
    ptext = {p["id"]: p for p in passages}
    print(f"index built: {len(retr)} passages")

    # --- claims ---
    df = pd.read_csv(GOLD, encoding="utf-8")
    if args.limit:
        # take a mix of en/hi for the smoke test
        df = pd.concat([df[df.language == "en"].head(args.limit // 2),
                        df[df.language == "hi"].head(args.limit - args.limit // 2)])
    print(f"scoring {len(df)} claims...")
    # same reason: force XLM-R so claim vectors are comparable to the index
    cres = embedder.embed(df["claim_id"].tolist(), df["claim_text"].tolist(), ["en"] * len(df))

    import torch
    nli = NLIScorer()
    nli._ensure_loaded()
    print(f"NLI device: {nli.device}", flush=True)
    _tok, _model = nli._tokenizer, nli._model
    _lab = {i: l.lower() for i, l in _model.config.id2label.items()}
    _ent = next(i for i, l in _lab.items() if l == "entailment")
    _con = next(i for i, l in _lab.items() if l == "contradiction")

    # Phase 1 — retrieval (fast): sem_sim (top-1) + collect NLI (premise, hypothesis) pairs
    rows = [None] * len(df)
    pairs = []  # (premise=passage_text, hypothesis=claim_text)
    claim_texts = df["claim_text"].tolist()
    claim_ids = df["claim_id"].tolist()
    for i, cvec in enumerate(cres.vectors):
        r = retr.retrieve(claim_ids[i], cvec, top_k=RETRIEVE_K)
        if not r.passages:
            rows[i] = {"sem_sim_new": np.nan, "nli_prob_new": np.nan, "evidence_title": None,
                       "evidence_lang": None, "n_evidence": 0, "_idx": []}
            continue
        rows[i] = {
            "sem_sim_new": float(np.clip(r.passages[0].score, 0.0, 1.0)),
            "nli_prob_new": np.nan,
            "evidence_title": ptext[r.passages[0].passage_id]["title"],
            "evidence_lang": ptext[r.passages[0].passage_id]["lang"],
            "n_evidence": len(r.passages), "_idx": [],
        }
        for p in r.passages[:NLI_TOP_K]:
            rows[i]["_idx"].append(len(pairs))
            pairs.append((p.text, claim_texts[i]))
    print(f"retrieval done: {len(pairs)} NLI pairs to score in batches", flush=True)

    # Free the embedder + index before NLI — with XLM-R still resident the NLI
    # passes run ~10x slower (CPU cache/memory contention), the real reason the
    # full run crawled.
    import gc
    del embedder, retr, cres
    gc.collect()

    # Phase 2 — batched NLI (one matmul per batch; far faster + robust vs 1000s of calls)
    nets = np.full(len(pairs), np.nan)
    BS = 16
    for s in range(0, len(pairs), BS):
        chunk = pairs[s:s + BS]
        enc = _tok([p for p, h in chunk], [h for p, h in chunk],
                   return_tensors="pt", truncation=True, max_length=NLI_MAXLEN, padding=True)
        with torch.no_grad():
            probs = torch.softmax(_model(**enc).logits, dim=-1)
        e, c = probs[:, _ent].tolist(), probs[:, _con].tolist()
        for k in range(len(chunk)):
            nets[s + k] = 0.5 + 0.5 * (e[k] - c[k])
        print(f"  NLI {min(s + BS, len(pairs))}/{len(pairs)} pairs", flush=True)
        if (s // BS) % 10 == 0:
            np.save("nets_partial.npy", nets)  # crash-resilience: partial progress persists

    for i in range(len(rows)):
        idx = rows[i].pop("_idx", [])
        if idx:
            rows[i]["nli_prob_new"] = float(max((nets[j] for j in idx), key=lambda x: abs(x - 0.5)))

    scored = df.copy().reset_index(drop=True)
    add = pd.DataFrame(rows).reset_index(drop=True)
    scored["sem_sim_old"] = scored.get("sem_sim")
    scored["nli_prob_old"] = scored.get("nli_prob")
    scored["sem_sim"] = add["sem_sim_new"]
    scored["nli_prob"] = add["nli_prob_new"]
    for c in ("evidence_title", "evidence_lang", "n_evidence"):
        scored[c] = add[c]

    if not args.limit:
        scored.to_csv(OUT, index=False, encoding="utf-8")
        print(f"\nwrote {OUT} ({len(scored)} rows)")

    # --- report / spot-check ---
    print("\n=== coverage ===")
    print("claims with evidence retrieved:", int(add['n_evidence'].gt(0).sum()), "/", len(add))
    print("evidence language used, by claim language:")
    tmp = scored.assign(evl=add['evidence_lang'].values)
    print(tmp.groupby(['language', 'evl']).size().to_string())
    print("\nmean new sem_sim / nli by (language, gold_verdict):")
    print(scored.groupby(['language', 'gold_verdict'])[['sem_sim', 'nli_prob']].mean().round(3).to_string())

    print("\n=== spot check (first few) ===")
    for _, r in scored.head(6).iterrows():
        sys.stdout.buffer.write(
            (f"[{r['language']}/{r['gold_verdict']}] sem={r['sem_sim']:.3f} nli={r['nli_prob']:.3f} "
             f"ev={r['evidence_title']}({r['evidence_lang']})\n   claim: {str(r['claim_text'])[:90]}\n"
             ).encode("utf-8"))


if __name__ == "__main__":
    main()
