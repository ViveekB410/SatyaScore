"""
v2data/run_eval.py -- runs the live pipeline on the Version 2 evaluation sets (results/v2_data_PROTOCOL.md)
and caches, per claim, everything later steps need: verdict, score, deciding source, NLI score and the
evidence passages (for the offline LLM comparison). Resumable.

    .venv/Scripts/python.exe v2data/run_eval.py --split dev --tag v1          (the current system)
    .venv/Scripts/python.exe v2data/run_eval.py --split dev --tag v1 --sets fever hiwiki
Writes v2data/runs/<tag>_<split>.jsonl (one line per item; Mu-SHROOM: one line per answer).
Scoring: v2data/score.py.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SETS = ("mushroom", "fever", "xfact_hi", "hiwiki", "hiwiki_para", "hiwiki_swap", "truthfulqa", "v1gold")


def run_text(pipe, text: str, lang: str) -> dict:
    try:
        r = pipe.run(text, lang)
    except ValueError as e:
        if "No claims could be extracted" not in str(e):
            raise
        return {"claims": [], "document": "Uncertain", "no_claims": True}
    claims = []
    for c, s, sub, ev in zip(r.claims, r.scores, r.sub_scores, r.evidence):
        claims.append({"text": c.text, "start": c.start_char, "end": c.end_char, "verdict": s.verdict.value,
                       "score": float(s.hallu_score), "nli_prob": sub.nli_prob, "kg_conf": sub.kg_conf,
                       "note": s.note, "passages": ev.get("passages", [])[:10],
                       "fact_check": (ev.get("fact_check") or {}).get("verdict"),
                       "error_spans": ev.get("error_spans", []), "llm_check": ev.get("llm_check")})
    return {"claims": claims, "document": r.document.document_verdict.value}


def items_for(name: str, split: str) -> list[dict]:
    path = ROOT / "v2data" / "sets" / f"{name}_{split}.csv"
    if not path.exists():  # a sample can have no items left from a set (testS3: hiwiki_swap)
        return []
    d = pd.read_csv(path, encoding="utf-8", dtype=str)
    if name != "mushroom":
        return [{"key": r.item_id, "set": name, "language": r.language, "text": r.text} for r in d.itertuples()]
    # Mu-SHROOM: run each whole answer once (claims keep their context); claims are matched by offset
    src = {}
    for lang in ("hi", "en"):
        p = pd.read_parquet(ROOT / "benchmarks" / "data" / f"mushroom_{lang}_{'validation' if split == 'dev' else 'test'}.parquet")
        src.update({r.id: (lang, r.model_output_text) for r in p.itertuples()})
    answers = sorted({json.loads(m)["answer_id"] for m in d.meta})
    return [{"key": a, "set": name, "language": src[a][0], "text": src[a][1]} for a in answers]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=("dev", "test", "testS", "testS2", "testS3", "testL"), required=True)
    ap.add_argument("--tag", required=True, help="name of the system configuration, e.g. v1 or crosscheck")
    ap.add_argument("--sets", nargs="*", default=list(SETS))
    args = ap.parse_args()
    if args.split in ("test", "testS", "testS2", "testS3", "testL") and input(f"Run the LOCKED test split for '{args.tag}'? Type yes: ").strip() != "yes":
        sys.exit("not run")
    out = ROOT / "v2data" / "runs" / f"{args.tag}_{args.split}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        done = {(json.loads(l)["set"], json.loads(l)["key"]) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()}
    todo = [it for name in args.sets for it in items_for(name, args.split) if (it["set"], it["key"]) not in done]
    print(f"{args.tag}/{args.split}: {len(done)} cached, {len(todo)} to run", flush=True)
    if not todo:
        return
    import member3_backend.api as api
    api.load_starter_corpus()
    api._warmup_models()
    pipe = api._pipeline
    print("fact-checks:", "ON" if pipe.fact_checker is not None else "OFF",
          "| LLM:", "ON" if pipe.llm_verifier is not None else "OFF", flush=True)
    t0 = time.time()
    with open(out, "a", encoding="utf-8") as f:
        for k, it in enumerate(todo, 1):
            try:
                res = run_text(pipe, it["text"], it["language"])
            except Exception as e:  # recorded and skipped; rerun resumes
                print(f"FAILED {it['set']} {it['key']}: {type(e).__name__}", flush=True)
                continue
            f.write(json.dumps({**{k2: it[k2] for k2 in ("set", "key", "language")}, **res}, ensure_ascii=False) + "\n")
            f.flush()
            if k % 25 == 0:
                print(f"{k}/{len(todo)}  ({(time.time() - t0) / k:.1f} s/item)", flush=True)


if __name__ == "__main__":
    main()
