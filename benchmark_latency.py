"""
benchmark_latency.py  --  PHASE3 Task A / BACKEND_IMPROVEMENTS Task 7.

Runs the demo claims through DetectionPipeline directly (no HTTP), reads the
per-stage timings_ms the pipeline now populates, and reports per-claim and
per-document latency against the PRD targets (<500ms/claim, <3s per 10-claim doc).
Discards the first run as warm-up. Runs unchanged on CPU or GPU.

Writes results/latency_benchmark.md.
"""
from __future__ import annotations
import json
import re
import statistics
import sys
from pathlib import Path

import numpy as np

from member1_model.cmhsa import CMHSAScorer
from member1_model.embeddings import CrossLingualEmbedder
from member1_model.nli_scorer import NLIScorer
from member2_data.entity_linker import EntityLinker
from member2_data.wikidata_connector import WikidataConnector
from member3_backend.claim_extractor import ClaimExtractor
from member3_backend.faiss_retriever import FAISSRetriever
from member3_backend.pipeline import DetectionPipeline

ROOT = Path(__file__).resolve().parent
STAGES = ["claim_extraction", "embedding", "retrieval", "nli", "kg", "fusion", "total"]
PER_CLAIM_TARGET_MS = 500
PER_DOC_TARGET_MS = 3000

# A ~10-claim English document to measure per-document latency (the <3s target).
DOC_10 = (
    "The capital of France is Paris. Water is composed of hydrogen and oxygen. "
    "The Sun is a star at the centre of the Solar System. Mahatma Gandhi led the "
    "Indian independence movement. The Taj Mahal is in India. Cricket is popular "
    "in India. The heart pumps blood through the body. Dengue is spread by "
    "mosquitoes. Photosynthesis occurs in plants. The Earth orbits the Sun."
)


def load_demo_claims() -> list[tuple[str, str]]:
    p = ROOT / "DEMO_CLAIMS.md"
    claims: list[tuple[str, str]] = []
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\|\s*(en|hi)\s*\|\s*(.+?)\s*\|", line)
            if m and m.group(2).lower() != "claim":  # skip the header row
                claims.append((m.group(1), m.group(2).strip()))
    if not claims:  # fallback if the file/tables aren't parseable
        claims = [("en", "The capital of France is Paris."),
                  ("hi", "पेरिस फ्रांस की राजधानी है।")]
    return claims


def build_pipeline() -> DetectionPipeline:
    embedder = CrossLingualEmbedder()
    retriever = FAISSRetriever(n_clusters=1)  # exact search; matches api.py
    # Experiment corpus (never the demo corpus for measurement consistency).
    passages = json.loads((ROOT / "corpus_passages.json").read_text(encoding="utf-8"))
    vectors = np.load(ROOT / "corpus_vectors.npy")
    retriever.build_index([p["id"] for p in passages], [p["text"] for p in passages], vectors)

    scorer = CMHSAScorer()
    for lang in ("en", "hi", "mr"):
        wf = ROOT / f"weights_{lang}.json"
        if wf.exists():
            w = json.loads(wf.read_text(encoding="utf-8"))
            scorer.load_weights(lang, alpha=w["alpha"], beta=w["beta"], gamma=w["gamma"])
        else:
            scorer.load_weights(lang, alpha=0.5, beta=0.3, gamma=0.2)

    return DetectionPipeline(
        embedder=embedder, retriever=retriever, scorer=scorer,
        claim_extractor=ClaimExtractor(), nli_scorer=NLIScorer(),
        entity_linker=EntityLinker(), wikidata=WikidataConnector(), nli_top_k=3,
    )


def main() -> None:
    print("building pipeline + loading models...", flush=True)
    pipeline = build_pipeline()
    device = pipeline.nli_scorer.device

    claims = load_demo_claims()
    print(f"warm-up run (discarded)...", flush=True)
    pipeline.run(claims[0][1], claims[0][0])  # warm-up, discarded

    per_stage: dict[str, list[float]] = {s: [] for s in STAGES}
    print(f"timing {len(claims)} single claims...", flush=True)
    for i, (lang, text) in enumerate(claims, 1):
        r = pipeline.run(text, lang)
        for s in STAGES:
            per_stage[s].append(float(r.timings_ms.get(s, 0.0)))
        print(f"  {i}/{len(claims)}  total={r.timings_ms.get('total', 0):.0f}ms", flush=True)

    print("timing a 10-claim document...", flush=True)
    doc = pipeline.run(DOC_10, "en")
    doc_total = doc.timings_ms.get("total", 0.0)
    doc_claims = len(doc.claims)

    claim_total_mean = statistics.mean(per_stage["total"])
    claim_total_median = statistics.median(per_stage["total"])

    def met(v, target):
        return "MET" if v <= target else "MISSED"

    lines = []
    lines.append("# Latency benchmark\n")
    lines.append(f"- Device: **{device}**")
    lines.append(f"- Single claims timed: {len(claims)} (first run discarded as warm-up)")
    lines.append(f"- NLI top-k: {pipeline.nli_top_k}, corpus: experiment ({len(pipeline.retriever)} passages)\n")

    lines.append("## Per-stage timings across single claims (ms)")
    lines.append("| Stage | mean | median |")
    lines.append("| --- | --- | --- |")
    for s in STAGES:
        lines.append(f"| {s} | {statistics.mean(per_stage[s]):.1f} | {statistics.median(per_stage[s]):.1f} |")

    lines.append("\n## PRD targets")
    lines.append("| Metric | Measured | Target | Result |")
    lines.append("| --- | --- | --- | --- |")
    lines.append(f"| Per-claim total (mean) | {claim_total_mean:.0f} ms | < {PER_CLAIM_TARGET_MS} ms | "
                 f"**{met(claim_total_mean, PER_CLAIM_TARGET_MS)}** |")
    lines.append(f"| Per-claim total (median) | {claim_total_median:.0f} ms | < {PER_CLAIM_TARGET_MS} ms | "
                 f"**{met(claim_total_median, PER_CLAIM_TARGET_MS)}** |")
    lines.append(f"| {doc_claims}-claim document total | {doc_total:.0f} ms | < {PER_DOC_TARGET_MS} ms | "
                 f"**{met(doc_total, PER_DOC_TARGET_MS)}** |")

    lines.append(f"\n_NLI is the dominant stage; on CPU the per-claim targets are expected to be MISSED. "
                 f"Re-run on a GPU (device=cuda) for the real numbers._\n")

    out = ROOT / "results" / "latency_benchmark.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(lines) + "\n").encode("utf-8"))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
