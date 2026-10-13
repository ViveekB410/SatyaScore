"""
v2data/score.py -- scores a cached run (v2data/runs/<tag>_<split>.jsonl) on the Version 2 sets.

Verdict modes, all computed from the same cached run (no re-run needed):
  live          the verdicts the system gave
  no_factcheck  as live, but a claim decided by a published fact-check falls back to its evidence score
                (for X-FACT, whose rumours are exactly what fact-check sites cover)
  crosscheck    member3_backend/crosscheck.py applied with cached LLM answers (--llm <cache.jsonl>)

    .venv/Scripts/python.exe v2data/score.py --run v1_dev
    .venv/Scripts/python.exe v2data/score.py --run v1_dev --llm v2data/llm/groq__openai_gpt-oss-120b.jsonl
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from member3_backend.crosscheck import crosscheck_verdict, llm_verdict_used, second_reading_candidate  # noqa: E402
from member3_backend.number_guard import NUMBER_NOTE  # noqa: E402

KG_NOTE = "decided by the knowledge graph"
FC_NOTE = "fact-checked"


def tier(s) -> str:
    if s is None or (isinstance(s, float) and math.isnan(s)):
        return "Uncertain"
    return "Hallucinated" if s < 0.35 else "Verified" if s > 0.65 else "Uncertain"


def decided_by_source(c: dict) -> bool:
    note = c.get("note") or ""
    return note.startswith(KG_NOTE) or note.startswith(FC_NOTE)


GROUNDED: dict | None = None  # second-reading answers (last round); None = off
FLAG_NEEDS_LLM = False  # v4a: contradiction alone never flags, and flagged claims get the second-reading guard
REASONS: dict | None = None  # the LLM's reasons (for the no-evidence filter); set by load_llm_with_reasons
SYMMETRIC = True  # --first-rule: the cross-check rule as first chosen (member3_backend/crosscheck.py)


def claim_verdict(c: dict, mode: str, llm: dict | None) -> str:
    note = c.get("note") or ""
    if mode == "live":
        return c["verdict"]
    if mode == "no_factcheck":
        return tier(c.get("nli_prob")) if note.startswith(FC_NOTE) else c["verdict"]
    if mode == "crosscheck":
        j = llm_verdict_used((llm or {}).get(c["text"]), (REASONS or {}).get(c["text"]))
        v = crosscheck_verdict(c["verdict"], decided_by_source(c), c.get("nli_prob"), j, note.startswith(NUMBER_NOTE), SYMMETRIC,
                               FLAG_NEEDS_LLM)
        if FLAG_NEEDS_LLM and v == "Hallucinated" and not decided_by_source(c) and (GROUNDED or {}).get(c["text"]) == "Verified":
            v = "Uncertain"  # the guard: the retrieved sources state the claim
        if (GROUNDED is not None and v == "Uncertain" and not decided_by_source(c)
                and second_reading_candidate(c.get("nli_prob"), j, note.startswith(NUMBER_NOTE))
                and GROUNDED.get(c["text"]) == "Verified"):
            v = "Verified"
        return v
    raise ValueError(mode)


def document_verdict(verdicts: list[str]) -> str:
    """Same rule as member1_model.cmhsa.aggregate_document."""
    if not verdicts:
        return "Uncertain"
    h = verdicts.count("Hallucinated")
    if h and 3 * h >= len(verdicts):
        return "Hallucinated"
    return "Uncertain" if h or verdicts.count("Uncertain") else "Verified"


def predictions(run: list[dict], split: str, mode: str, llm: dict | None) -> pd.DataFrame:
    """One row per labelled item: set, language, gold label, predicted verdict."""
    rows = []
    by_key = {(r["set"], r["key"]): r for r in run}
    for path in sorted((ROOT / "v2data" / "sets").glob(f"*_{split}.csv")):
        name = path.stem[: -len(split) - 1]
        items = pd.read_csv(path, encoding="utf-8", dtype=str)
        for it in items.itertuples():
            if name == "mushroom":
                m = json.loads(it.meta)
                r = by_key.get((name, m["answer_id"]))
                if r is None:
                    continue
                c = next((c for c in r["claims"] if c["start"] == m["start"] and c["end"] == m["end"]), None)
                if c is None:
                    continue
                pred = claim_verdict(c, mode, llm)
            else:
                r = by_key.get((name, it.item_id))
                if r is None:
                    continue
                vs = [claim_verdict(c, mode, llm) for c in r["claims"]]
                pred = vs[0] if len(vs) == 1 else document_verdict(vs)
            rows.append({"set": name, "language": it.language, "gold": it.label, "pred": pred})
    return pd.DataFrame(rows)


def summary(df: pd.DataFrame) -> pd.DataFrame:
    out = []
    for (s, lang), g in df.groupby(["set", "language"]):
        t, f = g[g.gold == "Verified"], g[g.gold == "Hallucinated"]
        dec = g[g.pred != "Uncertain"]
        out.append({"set": s, "lang": lang, "n_true": len(t), "n_false": len(f),
                    "true_verified": f"{(t.pred == 'Verified').mean():.0%}" if len(t) else "-",
                    "false_alarm": f"{(t.pred == 'Hallucinated').mean():.0%}" if len(t) else "-",
                    "caught": f"{(f.pred == 'Hallucinated').mean():.0%}" if len(f) else "-",
                    "false_verified": f"{(f.pred == 'Verified').mean():.0%}" if len(f) else "-",
                    "uncertain": f"{(g.pred == 'Uncertain').mean():.0%}",
                    "acc_decided": f"{(dec.pred == dec.gold).mean():.0%}" if len(dec) else "-"})
    return pd.DataFrame(out)


def load_llm(path: str | None, field: str = "verdict") -> dict | None:
    if not path:
        return None
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["claim"]] = r.get(field)
    return out


def _span_in(answer: str, c: dict, word: str) -> range:
    """The wrong words inside the claim's slice of the answer; the whole slice if not found."""
    k = answer[c["start"]:c["end"]].casefold().find(word.casefold()) if word else -1
    return range(c["start"] + k, c["start"] + k + len(word)) if k >= 0 else range(c["start"], c["end"])


def mushroom_iou(run: list[dict], split: str, mode: str, llm: dict | None, spans: dict | None) -> list[str]:
    """Mu-SHROOM's official measure: character IoU between the marked and the gold hallucinated spans, per
    answer, averaged. 'claims' marks every Hallucinated claim whole; 'error spans' marks only the wrong
    words where known (Wikidata value, LLM wrong_span)."""
    lines = []
    for lang in ("en", "hi"):
        p = pd.read_parquet(ROOT / "benchmarks" / "data" / f"mushroom_{lang}_{'validation' if split == 'dev' else 'test'}.parquet")
        gold_of = {r.id: (r.model_output_text, {i for a, b in r.hard_labels for i in range(int(a), int(b))})
                   for r in p.itertuples()}
        res = {"claims": [], "error spans": [], "mark-all": []}
        for r in run:
            if r["set"] != "mushroom" or r["key"] not in gold_of:
                continue
            answer, gold = gold_of[r["key"]]
            whole, narrow = set(), set()
            for c in r["claims"]:
                if claim_verdict(c, mode, llm) != "Hallucinated":
                    continue
                whole.update(range(c["start"], c["end"]))
                word = ""
                if mode == "crosscheck" and spans is not None and not decided_by_source(c):
                    word = spans.get(c["text"]) or ""
                elif c.get("error_spans"):
                    a, b = c["error_spans"][0]
                    word = c["text"][a:b] if (a, b) != (0, len(c["text"])) else ""
                narrow.update(_span_in(answer, c, word))
            for k, pred in (("claims", whole), ("error spans", narrow), ("mark-all", set(range(len(answer))))):
                res[k].append(1.0 if not pred and not gold else len(pred & gold) / len(pred | gold))
        if res["claims"]:
            lines.append(f"Mu-SHROOM {lang} ({len(res['claims'])} answers) mean IoU: "
                         + ", ".join(f"{k} {sum(v) / len(v):.3f}" for k, v in res.items()))
    return lines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="e.g. v1_dev (v2data/runs/v1_dev.jsonl)")
    ap.add_argument("--llm", help="LLM answer cache for the crosscheck mode")
    ap.add_argument("--only-llm-claims", action="store_true", help="score only items whose claims all have an LLM answer")
    ap.add_argument("--first-rule", action="store_true", help="cross-check as first chosen: a contradiction alone decides")
    args = ap.parse_args()
    global SYMMETRIC
    SYMMETRIC = not args.first_rule
    run = [json.loads(l) for l in (ROOT / "v2data" / "runs" / f"{args.run}.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    split = args.run.rsplit("_", 1)[1]
    llm = load_llm(args.llm)
    spans = load_llm(args.llm, "wrong_span")
    global REASONS
    REASONS = load_llm(args.llm, "reason")
    if llm is not None and args.only_llm_claims:
        run = [dict(r, claims=r["claims"]) for r in run if r["claims"] and all(c["text"] in llm for c in r["claims"])]
    modes = ["live", "no_factcheck"] + (["crosscheck"] if llm is not None else [])
    pd.set_option("display.width", 200)
    for mode in modes:
        df = predictions(run, split, mode, llm)
        print(f"\n=== {args.run} | {mode} | {len(df)} items")
        print(summary(df).to_string(index=False))
        for line in mushroom_iou(run, split, mode, llm, spans):
            print(line)


if __name__ == "__main__":
    main()
