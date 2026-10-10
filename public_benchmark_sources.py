"""Which source decided each claim in the public-benchmark run, and the FEVER false alarms (for the paper's
error analysis). Reads results/_public_benchmarks_cache.jsonl; writes results/public_benchmarks_sources.md.
    .venv/Scripts/python.exe public_benchmark_sources.py"""
from __future__ import annotations

import collections
import json

from public_benchmark_eval import CACHE, ROOT, fever_sample


def source(note: str | None) -> str:
    n = note or ""
    if n.startswith("decided by the knowledge"):
        return "statistics / Wikidata"
    if n.startswith("fact-check"):
        return "published fact-check"
    return "passages (NLI) or no evidence"


def main() -> None:
    rs = [json.loads(l) for l in CACHE.read_text(encoding="utf-8").splitlines() if l.strip()]
    text = {it["id"]: it["text"] for it in fever_sample()}
    L = ["# Public benchmarks: deciding sources and FEVER false alarms", "",
         "| set | answers | answers with no extractable claim | claims | statistics / Wikidata | published fact-check | passages or none |",
         "|---|---|---|---|---|---|---|"]
    for st in ("fever", "mushroom-hi", "mushroom-en"):
        s = [r for r in rs if r["set"] == st]
        c = collections.Counter(source(cl["note"]) for r in s for cl in r["claims"])
        L.append(f"| {st} | {len(s)} | {sum(bool(r.get('no_claims')) for r in s)} | {sum(c.values())} | "
                 f"{c['statistics / Wikidata']} | {c['published fact-check']} | {c['passages (NLI) or no evidence']} |")
    fever = [r for r in rs if r["set"] == "fever"]
    kg = [(r["label"], cl["verdict"]) for r in fever for cl in r["claims"] if source(cl["note"]) == "statistics / Wikidata"]
    ok = sum((l == "SUPPORTS" and v == "Verified") or (l == "REFUTES" and v == "Hallucinated") for l, v in kg)
    L += ["", f"FEVER claims decided by statistics / Wikidata: {len(kg)}, of which correct: {ok}.", "",
          "## FEVER false alarms (gold SUPPORTS, system Hallucinated)", "", "| claim | claim verdicts (verdict, score, source) |", "|---|---|"]
    verdict = lambda r: r["claims"][0]["verdict"] if len(r["claims"]) == 1 else r["document"]
    for r in fever:
        if r["label"] == "SUPPORTS" and verdict(r) == "Hallucinated":
            parts = "; ".join(f"{c['verdict']}, {c['score']:.2f}, {source(c['note'])}" for c in r["claims"])
            L.append(f"| {text[r['id']]} | {parts} |")
    (ROOT / "results" / "public_benchmarks_sources.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
