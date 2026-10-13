"""
v2data/llm_bakeoff.py -- Phase 2.2: compare free LLMs as the cross-check judge, offline, on the passages the v1
run already retrieved (v2data/runs/v1_dev.jsonl). Nothing on the test split is used.

Sample (fixed, seed 20261012): from every (set, language), up to PER_CELL items whose gold label is true and
PER_CELL whose gold label is false, among items NOT already decided by a structured source or fact-check
(the LLM is never consulted for those). Mu-SHROOM: one labelled claim = one item; other sets: the item's claims.

Each model is asked in "open" mode (passages + its own knowledge). Answers are cached per model in
v2data/llm/<provider>__<model>.jsonl, so a quota stop loses nothing; rerun to resume.

    .venv/Scripts/python.exe v2data/llm_bakeoff.py --sample              (writes v2data/llm/bakeoff_sample.json)
    .venv/Scripts/python.exe v2data/llm_bakeoff.py --provider groq --model openai/gpt-oss-120b
    .venv/Scripts/python.exe v2data/llm_bakeoff.py --report
Keys are read from your shell (GROQ_API_KEY, GEMINI_API_KEY, ...), never printed.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "v2data"))
from score import decided_by_source  # noqa: E402

RUN = ROOT / "v2data" / "runs" / "v1_dev.jsonl"
LLM_DIR = ROOT / "v2data" / "llm"
SAMPLE = LLM_DIR / "bakeoff_sample.json"
SEED, PER_CELL = 20261012, 12


def labelled_claims() -> list[dict]:
    """Every dev item as {set, language, gold, claims:[{text, passages}]} with its cached v1 claims."""
    run = {(r["set"], r["key"]): r for r in map(json.loads, RUN.read_text(encoding="utf-8").splitlines()) if r}
    out = []
    for path in sorted((ROOT / "v2data" / "sets").glob("*_dev.csv")):
        name = path.stem[:-4]
        for it in pd.read_csv(path, encoding="utf-8", dtype=str).itertuples():
            if name == "mushroom":
                m = json.loads(it.meta)
                r = run.get((name, m["answer_id"]))
                cl = [c for c in (r or {}).get("claims", []) if c["start"] == m["start"] and c["end"] == m["end"]]
            else:
                cl = run.get((name, it.item_id), {}).get("claims", [])
            if cl and not any(decided_by_source(c) for c in cl):
                out.append({"set": name, "language": it.language, "gold": it.label, "item": it.item_id,
                            "claims": [{"text": c["text"], "passages": c["passages"]} for c in cl]})
    return out


def make_sample() -> None:
    cells = defaultdict(list)
    for x in labelled_claims():
        cells[(x["set"], x["language"], x["gold"])].append(x)
    sample = []
    for key in sorted(cells):
        xs = sorted(cells[key], key=lambda x: x["item"])
        random.Random(f"{SEED}-{'-'.join(key)}").shuffle(xs)  # per cell: adding a set changes no other cell
        sample += xs[:PER_CELL]
    LLM_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLE.write_text(json.dumps(sample, ensure_ascii=False, indent=0), encoding="utf-8")
    n = defaultdict(int)
    for x in sample:
        n[(x["set"], x["language"], x["gold"])] += 1
    print(f"{len(sample)} items, {sum(len(x['claims']) for x in sample)} claims")
    for k in sorted(n):
        print(" ", k, n[k])


def cache_path(provider: str, model: str, mode: str = "open") -> Path:
    suffix = "" if mode == "open" else f"__{mode}"
    return LLM_DIR / f"{provider}__{model.replace('/', '_').replace(':', '-')}{suffix}.jsonl"  # ':' is not allowed in Windows file names


def run_model(provider: str, model: str, limit: int | None, mode: str = "open") -> None:
    from member1_model.llm_verifier import LLMQuotaExhausted, LLMVerifier, LLMVerifierError
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    path = cache_path(provider, model, mode)
    done = {json.loads(l)["claim"] for l in path.read_text(encoding="utf-8").splitlines() if l.strip()} if path.exists() else set()
    todo, seen = [], set(done)
    for x in sample:
        for c in x["claims"]:
            if c["text"] not in seen:
                seen.add(c["text"])
                todo.append(c)
    todo = todo[:limit] if limit else todo
    print(f"{provider}/{model}: {len(done)} cached, {len(todo)} to ask", flush=True)
    local = provider == "ollama"
    v = LLMVerifier(model=model, mode=mode, provider=provider, timeout_s=900 if local else 90,
                    min_interval_s=0 if local else 2.5 if provider == "groq" else 4.5)
    with open(path, "a", encoding="utf-8") as f:
        for k, c in enumerate(todo, 1):
            try:
                j = v.verify(c["text"], c["passages"])
            except LLMQuotaExhausted as e:
                print(f"stopped (quota): {e}  -- rerun later to resume", flush=True)
                break
            except LLMVerifierError as e:
                print(f"stopped: {e}", flush=True)
                break
            f.write(json.dumps({"claim": c["text"], "verdict": j.verdict, "p_true": j.p_true,
                                "wrong_span": j.wrong_span, "reason": j.reason}, ensure_ascii=False) + "\n")
            f.flush()
            if k % 25 == 0:
                print(f"{k}/{len(todo)}  tokens so far {v.tokens_used}", flush=True)
    print("tokens used:", v.tokens_used)


def document_verdict(vs: list[str]) -> str:
    from score import document_verdict as dv
    return vs[0] if len(vs) == 1 else dv(vs)


def report() -> None:
    from score import load_llm
    from member3_backend.crosscheck import crosscheck_verdict
    sample = json.loads(SAMPLE.read_text(encoding="utf-8"))
    run = {}
    for r in map(json.loads, RUN.read_text(encoding="utf-8").splitlines()):
        for c in r["claims"]:
            run[c["text"]] = c
    from member3_backend.number_guard import NUMBER_NOTE
    rows = []
    files = sorted(LLM_DIR.glob("*__*.jsonl"))
    for path in [None, *files]:
        name = "v1 (no LLM)" if path is None else path.stem
        llm = {} if path is None else load_llm(str(path))
        stats = defaultdict(lambda: defaultdict(int))
        complete = 0
        for x in sample:
            if path is not None and not all(c["text"] in llm for c in x["claims"]):
                continue
            complete += 1
            cs = [run[c["text"]] for c in x["claims"]]
            alone = [llm.get(c["text"]) or "Uncertain" for c in x["claims"]] if path else [c["verdict"] for c in cs]
            cross = [crosscheck_verdict(c["verdict"], False, c.get("nli_prob"), llm.get(c["text"]),
                                        (c.get("note") or "").startswith(NUMBER_NOTE)) for c in cs]
            for kind, vs in (("llm_alone", alone), ("crosscheck", cross)):
                p = document_verdict(vs)
                s = stats[kind]
                s["n_" + x["gold"]] += 1
                s[(x["gold"], p)] += 1
        for kind, s in stats.items():
            t, f = max(s["n_Verified"], 1), max(s["n_Hallucinated"], 1)
            rows.append({"model": name, "verdicts": kind if path else "v1", "items": complete,
                         "caught": f"{s[('Hallucinated', 'Hallucinated')] / f:.0%}",
                         "false_verified": f"{s[('Hallucinated', 'Verified')] / f:.0%}",
                         "true_verified": f"{s[('Verified', 'Verified')] / t:.0%}",
                         "false_alarm": f"{s[('Verified', 'Hallucinated')] / t:.0%}",
                         "balanced_acc": f"{(s[('Hallucinated', 'Hallucinated')] / f + s[('Verified', 'Verified')] / t) / 2:.0%}"})
            if path is None:
                break
    pd.set_option("display.width", 200)
    print(pd.DataFrame(rows).to_string(index=False))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--provider", default="groq")
    ap.add_argument("--model")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--mode", default="open", help="prompt: open (the bake-off) or crosscheck (dev tuning)")
    a = ap.parse_args()
    if a.sample:
        make_sample()
    elif a.report:
        report()
    elif a.model:
        run_model(a.provider, a.model, a.limit, a.mode)
    else:
        ap.error("give --sample, --report or --model")


if __name__ == "__main__":
    main()
