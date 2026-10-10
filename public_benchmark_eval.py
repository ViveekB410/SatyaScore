"""
public_benchmark_eval.py -- the live system on two public, human-labelled benchmarks:
FEVER (English claims vs Wikipedia) and Mu-SHROOM (SemEval-2025 Task 3; Hindi and English
model answers with hallucinated character spans).

Protocol fixed before any run: results/public_benchmarks_PROTOCOL.md (reported only; nothing
in the system is tuned on these data).

    .venv/Scripts/python.exe public_benchmark_eval.py          (GPU; ~1-2 h, mostly web look-ups)
Resumable: every answered item is appended to results/_public_benchmarks_cache.jsonl.
Writes results/public_benchmarks.md.
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from member1_model.cmhsa import aggregate_document

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "benchmarks" / "data"
CACHE = ROOT / "results" / "_public_benchmarks_cache.jsonl"
SEED = 20261010
N_PER_LABEL = 150


def tier(score) -> str:
    if score is None or (isinstance(score, float) and math.isnan(score)):
        return "Uncertain"
    return "Hallucinated" if score < 0.35 else "Verified" if score > 0.65 else "Uncertain"


def wilson(k: int, n: int) -> str:
    if n == 0:
        return "n/a"
    z = 1.96; p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return f"{k}/{n} ({p:.0%}; 95% CI {max(0, c - h):.0%}-{min(1, c + h):.0%})"


# ---------------------------------------------------------------- data
def fever_sample() -> list[dict]:
    rows = [json.loads(l) for l in open(DATA / "fever_paper_dev.jsonl", encoding="utf-8")]
    rng = random.Random(SEED)
    out = []
    for label in ("SUPPORTS", "REFUTES"):
        pool = sorted((r for r in rows if r["label"] == label), key=lambda r: r["id"])
        for r in rng.sample(pool, N_PER_LABEL):
            out.append({"set": "fever", "id": f"fever-{r['id']}", "lang": "en", "text": r["claim"], "label": label})
    return out


def mushroom_items(lang: str) -> list[dict]:
    d = pd.read_parquet(DATA / f"mushroom_{lang}_test.parquet")
    out = []
    for r in d.itertuples(index=False):
        hard = [[int(a), int(b)] for a, b in r.hard_labels]
        soft = [{"start": int(s["start"]), "end": int(s["end"]), "prob": float(s["prob"])} for s in r.soft_labels]
        out.append({"set": f"mushroom-{lang}", "id": r.id, "lang": lang, "text": r.model_output_text,
                    "hard": hard, "soft": soft})
    return out


# ---------------------------------------------------------------- run
def run_item(pipe, item: dict) -> dict:
    try:
        res = pipe.run(item["text"], item["lang"])
    except ValueError as e:
        if "No claims could be extracted" not in str(e):
            raise
        # nothing checkable in the text: the system marks nothing (recorded as no claims, not as a failure)
        return {**{k: v for k, v in item.items() if k != "text"}, "claims": [], "document": "Uncertain",
                "text_len": len(item["text"]), "no_claims": True}
    claims = []
    for c, s, sub in zip(res.claims, res.scores, res.sub_scores):
        claims.append({"start": c.start_char, "end": c.end_char, "verdict": s.verdict.value,
                       "score": float(s.hallu_score), "nli_prob": sub.nli_prob, "note": s.note})
    return {**{k: v for k, v in item.items() if k != "text"}, "claims": claims,
            "document": res.document.document_verdict.value, "text_len": len(item["text"])}


def load_cache() -> dict:
    if not CACHE.exists():
        return {}
    done = {}
    for line in CACHE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            done[(r["set"], r["id"])] = r
    return done


# ---------------------------------------------------------------- measures
def fever_report(rs: list[dict]) -> list[str]:
    L = []
    for name, verdict_of in (("Live system", lambda r: r["claims"][0]["verdict"] if len(r["claims"]) == 1 else r["document"]),
                             ("NLI only (structured sources ignored)", lambda r: tier(r["claims"][0]["nli_prob"]) if len(r["claims"]) == 1
                              else aggregate_document([tier(c["nli_prob"]) for c in r["claims"]]).document_verdict.value if r["claims"] else "Uncertain")):
        sup = [verdict_of(r) for r in rs if r["label"] == "SUPPORTS"]
        ref = [verdict_of(r) for r in rs if r["label"] == "REFUTES"]
        decided = [(v, "Verified" if lab == "SUPPORTS" else "Hallucinated") for v, lab in
                   [(verdict_of(r), r["label"]) for r in rs] if v != "Uncertain"]
        L += [f"### {name}", "",
              "| | Verified | Hallucinated | Uncertain |", "|---|---|---|---|",
              f"| SUPPORTS ({len(sup)}) | {wilson(sup.count('Verified'), len(sup))} | {wilson(sup.count('Hallucinated'), len(sup))} (false alarms) | {wilson(sup.count('Uncertain'), len(sup))} |",
              f"| REFUTES ({len(ref)}) | {wilson(ref.count('Verified'), len(ref))} (missed) | {wilson(ref.count('Hallucinated'), len(ref))} (caught) | {wilson(ref.count('Uncertain'), len(ref))} |",
              "", f"- Accuracy over decided claims: {wilson(sum(v == g for v, g in decided), len(decided))}; "
                  f"share decided: {wilson(len(decided), len(rs))}.", ""]
    return L


def char_sets(r: dict):
    pred = set()
    for c in r["claims"]:
        if c["verdict"] == "Hallucinated":
            pred.update(range(c["start"], c["end"]))
    gold = set()
    for a, b in r["hard"]:
        gold.update(range(a, b))
    return pred, gold


def iou(pred: set, gold: set) -> float:
    if not pred and not gold:
        return 1.0
    return len(pred & gold) / len(pred | gold)


def cor(pred_probs: np.ndarray, gold_probs: np.ndarray) -> float:
    if len(set(pred_probs)) == 1 or len(set(gold_probs)) == 1:
        return 1.0 if len(set(pred_probs)) == 1 and len(set(gold_probs)) == 1 else 0.0
    return float(spearmanr(pred_probs, gold_probs).correlation)


def mushroom_report(rs: list[dict]) -> list[str]:
    ious = {"Satya-Score (live)": [], "mark-all baseline": [], "mark-none baseline": []}
    cors = {k: [] for k in ious}
    flagged_answers, flagged_claims, flagged_hit = 0, 0, 0
    n_claims = 0
    for r in rs:
        n = r["text_len"]
        pred, gold = char_sets(r)
        ious["Satya-Score (live)"].append(iou(pred, gold))
        ious["mark-all baseline"].append(iou(set(range(n)), gold))
        ious["mark-none baseline"].append(iou(set(), gold))
        g = np.zeros(n)
        for s in r["soft"]:
            g[s["start"]:s["end"]] = s["prob"]
        p = np.zeros(n)
        for c in r["claims"]:
            p[c["start"]:c["end"]] = 1.0 - c["score"]
        cors["Satya-Score (live)"].append(cor(p, g))
        cors["mark-all baseline"].append(cor(np.ones(n), g))
        cors["mark-none baseline"].append(cor(np.zeros(n), g))
        n_claims += len(r["claims"])
        hal = [c for c in r["claims"] if c["verdict"] == "Hallucinated"]
        flagged_answers += bool(hal)
        for c in hal:
            flagged_claims += 1
            flagged_hit += bool(set(range(c["start"], c["end"])) & gold)
    L = ["| method | mean IoU | mean Spearman (soft labels) |", "|---|---|---|"]
    for k in ious:
        L.append(f"| {k} | {np.mean(ious[k]):.3f} | {np.mean(cors[k]):.3f} |")
    L += ["", f"- Answers: {len(rs)}; claims extracted: {n_claims}; answers with at least one claim flagged: "
              f"{wilson(flagged_answers, len(rs))}.",
          f"- Flagged claims overlapping a gold hallucinated span: {wilson(flagged_hit, flagged_claims)}.", ""]
    return L


def main() -> None:
    items = fever_sample() + mushroom_items("hi") + mushroom_items("en")
    done = load_cache()
    todo = [it for it in items if (it["set"], it["id"]) not in done]
    print(f"{len(items)} items; cached {len(items) - len(todo)}; to run {len(todo)}", flush=True)
    failures = []
    if todo:
        import member3_backend.api as api
        api.load_starter_corpus()
        api._warmup_models()
        pipe = api._pipeline
        print("fact-checks:", "ON" if pipe.fact_checker is not None else "OFF", flush=True)
        with open(CACHE, "a", encoding="utf-8") as f:
            for k, it in enumerate(todo, 1):
                try:
                    r = run_item(pipe, it)
                except Exception as e:  # network or other failure: recorded, not hidden
                    failures.append((it["set"], it["id"], type(e).__name__))
                    print(f"FAILED {it['set']} {it['id']}: {type(e).__name__}", flush=True)
                    continue
                f.write(json.dumps(r, ensure_ascii=False) + "\n"); f.flush()
                done[(it["set"], it["id"])] = r
                if k % 10 == 0:
                    print(f"{k}/{len(todo)}", flush=True)
    by_set = {}
    for it in items:
        if (it["set"], it["id"]) in done:
            by_set.setdefault(it["set"], []).append(done[(it["set"], it["id"])])
    L = ["# Public benchmarks: FEVER and Mu-SHROOM (live system)", "",
         "Protocol fixed before the run: `results/public_benchmarks_PROTOCOL.md`. Reported only; nothing was "
         "tuned on these data.", "",
         f"## FEVER paper_dev (English), random sample (seed {SEED})", ""]
    L += fever_report(by_set.get("fever", []))
    for lang, name in (("hi", "Hindi"), ("en", "English")):
        L += [f"## Mu-SHROOM test, {name}", ""] + mushroom_report(by_set.get(f"mushroom-{lang}", []))
    L += ["## Run record", "", f"- Items answered: {sum(len(v) for v in by_set.values())} of {len(items)}.",
          f"- Failures in this run: {len(failures)}" + ("" if not failures else ": " + "; ".join(f"{a} {b} ({c})" for a, b, c in failures)),
          "- FEVER labels refer to Wikipedia of 2017; the system reads today's Wikipedia and Wikidata."]
    (ROOT / "results" / "public_benchmarks.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
