"""Machine-readable summary of the public-benchmark run (same measures as public_benchmark_eval.py's report).
    .venv/Scripts/python.exe summarise_public_benchmarks.py      -> results/public_benchmarks_summary.json"""
from __future__ import annotations

import json
import math

import numpy as np

# order matters on Windows: SciPy (via public_benchmark_eval) must load before PyTorch (via cmhsa)
from public_benchmark_eval import (CACHE, ROOT, char_sets, cor, fever_sample, iou, load_cache, mushroom_items, tier)
from member1_model.cmhsa import aggregate_document


def frac(k, n):
    if not n:
        return {"k": k, "n": n}
    z = 1.96; p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return {"k": k, "n": n, "p": round(p, 4), "lo": round(max(0, c - h), 4), "hi": round(min(1, c + h), 4)}


def fever(rs):
    out = {}
    live = lambda r: r["claims"][0]["verdict"] if len(r["claims"]) == 1 else r["document"]
    nli = lambda r: (tier(r["claims"][0]["nli_prob"]) if len(r["claims"]) == 1 else
                     aggregate_document([tier(c["nli_prob"]) for c in r["claims"]]).document_verdict.value if r["claims"] else "Uncertain")
    for name, f in (("live", live), ("nli_only", nli)):
        sup = [f(r) for r in rs if r["label"] == "SUPPORTS"]; ref = [f(r) for r in rs if r["label"] == "REFUTES"]
        dec = [(f(r), "Verified" if r["label"] == "SUPPORTS" else "Hallucinated") for r in rs if f(r) != "Uncertain"]
        out[name] = {"supports_verified": frac(sup.count("Verified"), len(sup)),
                     "supports_false_alarm": frac(sup.count("Hallucinated"), len(sup)),
                     "supports_uncertain": frac(sup.count("Uncertain"), len(sup)),
                     "refutes_caught": frac(ref.count("Hallucinated"), len(ref)),
                     "refutes_missed": frac(ref.count("Verified"), len(ref)),
                     "refutes_uncertain": frac(ref.count("Uncertain"), len(ref)),
                     "accuracy_decided": frac(sum(v == g for v, g in dec), len(dec)),
                     "decided": frac(len(dec), len(rs))}
    return out


def mushroom(rs):
    res = {"live": {"iou": [], "cor": []}, "mark_all": {"iou": [], "cor": []}, "mark_none": {"iou": [], "cor": []}}
    fa = fc = fh = nc = noc = 0
    for r in rs:
        n = r["text_len"]; pred, gold = char_sets(r)
        res["live"]["iou"].append(iou(pred, gold)); res["mark_all"]["iou"].append(iou(set(range(n)), gold))
        res["mark_none"]["iou"].append(iou(set(), gold))
        g = np.zeros(n)
        for s in r["soft"]:
            g[s["start"]:s["end"]] = s["prob"]
        p = np.zeros(n)
        for c in r["claims"]:
            p[c["start"]:c["end"]] = 1.0 - c["score"]
        res["live"]["cor"].append(cor(p, g)); res["mark_all"]["cor"].append(cor(np.ones(n), g))
        res["mark_none"]["cor"].append(cor(np.zeros(n), g))
        nc += len(r["claims"]); noc += bool(r.get("no_claims"))
        hal = [c for c in r["claims"] if c["verdict"] == "Hallucinated"]
        fa += bool(hal)
        for c in hal:
            fc += 1; fh += bool(set(range(c["start"], c["end"])) & gold)
    return {k: {"iou": round(float(np.mean(v["iou"])), 4), "cor": round(float(np.mean(v["cor"])), 4)} for k, v in res.items()} | {
        "answers": len(rs), "claims": nc, "answers_without_claims": noc,
        "answers_flagged": frac(fa, len(rs)), "flagged_claims_on_gold": frac(fh, fc)}


def main():
    done = load_cache()
    items = fever_sample() + mushroom_items("hi") + mushroom_items("en")
    by = {}
    for it in items:
        if (it["set"], it["id"]) in done:
            by.setdefault(it["set"], []).append(done[(it["set"], it["id"])])
    s = {"items_total": len(items), "items_answered": sum(map(len, by.values())),
         "fever": fever(by.get("fever", [])), "mushroom_hi": mushroom(by.get("mushroom-hi", [])),
         "mushroom_en": mushroom(by.get("mushroom-en", []))}
    (ROOT / "results" / "public_benchmarks_summary.json").write_text(json.dumps(s, indent=1), encoding="utf-8")
    print(json.dumps(s, indent=1))


if __name__ == "__main__":
    main()
