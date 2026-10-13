"""
v2data/llm_answer.py -- the frozen v2 LLM step for a cached run (results/v2_data_PROTOCOL.md, "Held-out test
sample"): asks the LLM ("open" prompt) about every SCORED claim that no source decided, using the passages the run
retrieved. Resumable; when the provider's quota runs out it waits and tries again until --until (hours).

    .venv/Scripts/python.exe v2data/llm_answer.py --run v1_testS --model openai/gpt-oss-20b
Writes v2data/llm/<run>__<provider>__<model>.jsonl; score with
    .venv/Scripts/python.exe v2data/score.py --run v1_testS --llm <that file>
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
sys.path.insert(0, str(ROOT / "v2data"))
from score import decided_by_source  # noqa: E402
from member1_model.llm_verifier import LLMQuotaExhausted, LLMVerifier, LLMVerifierError  # noqa: E402


def scored_claims(run_tag: str) -> list[dict]:
    split = run_tag.rsplit("_", 1)[1]
    run = {(r["set"], r["key"]): r for r in map(json.loads, (ROOT / "v2data" / "runs" / f"{run_tag}.jsonl")
                                               .read_text(encoding="utf-8").splitlines())}
    out, seen = [], set()
    for path in sorted((ROOT / "v2data" / "sets").glob(f"*_{split}.csv")):
        name = path.stem[: -len(split) - 1]
        for it in pd.read_csv(path, encoding="utf-8", dtype=str).itertuples():
            if name == "mushroom":
                m = json.loads(it.meta)
                cl = [c for c in run.get((name, m["answer_id"]), {}).get("claims", [])
                      if c["start"] == m["start"] and c["end"] == m["end"]]
            else:
                cl = run.get((name, it.item_id), {}).get("claims", [])
            for c in cl:
                if not decided_by_source(c) and c["text"] not in seen:
                    seen.add(c["text"])
                    out.append(c)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--provider", default="groq")
    ap.add_argument("--model", default="openai/gpt-oss-20b")
    ap.add_argument("--until", type=float, default=16, help="keep retrying after quota stops for this many hours")
    ap.add_argument("--mode", default="open", help="prompt: open (first version) or crosscheck (fix round)")
    a = ap.parse_args()
    suffix = "" if a.mode == "open" else f"__{a.mode}"
    path = ROOT / "v2data" / "llm" / f"{a.run}__{a.provider}__{a.model.replace('/', '_').replace(':', '-')}{suffix}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + a.until * 3600
    local = a.provider == "ollama"
    v = LLMVerifier(model=a.model, mode=a.mode, provider=a.provider, min_interval_s=0 if local else 2.5,
                    timeout_s=900 if local else 90)
    while True:
        done = {json.loads(l)["claim"] for l in path.read_text(encoding="utf-8").splitlines() if l.strip()} \
            if path.exists() else set()
        todo = [c for c in scored_claims(a.run) if c["text"] not in done]
        print(f"{time.strftime('%H:%M')} {len(done)} answered, {len(todo)} to ask", flush=True)
        if not todo:
            return
        stopped, answered = False, 0
        with open(path, "a", encoding="utf-8") as f:
            for c in todo:
                try:
                    j = v.verify(c["text"], c["passages"])
                except LLMQuotaExhausted as e:
                    print(f"{time.strftime('%H:%M')} quota: {e}", flush=True)
                    stopped = True
                    break
                except (LLMVerifierError, Exception) as e:  # one bad reply never stops the run
                    print(f"skip ({type(e).__name__})", flush=True)
                    continue
                f.write(json.dumps({"claim": c["text"], "verdict": j.verdict, "p_true": j.p_true,
                                    "wrong_span": j.wrong_span, "reason": j.reason}, ensure_ascii=False) + "\n")
                f.flush()
                answered += 1
        if not stopped:
            if answered:
                continue  # one more pass retries the skipped claims
            print("the remaining claims fail every time; stopping", flush=True)
            return
        if time.time() > deadline:
            print("deadline reached; rerun to resume", flush=True)
            return
        time.sleep(600)


if __name__ == "__main__":
    main()
