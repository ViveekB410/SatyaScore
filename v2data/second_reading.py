"""
v2data/second_reading.py -- Version 2 "second reading" (results/v2_data_PROTOCOL.md, "Last round"): for claims the
cross-check leaves Uncertain although one side leans true, the LLM reads ALL 10 retrieved passages in "grounded"
mode (passages only, no outside knowledge): does the evidence itself state the claim?

    .venv/Scripts/python.exe v2data/second_reading.py --run v1_testS --llm v2data/llm/v1_testS__ollama__gpt-oss-20b.jsonl
Writes <llm file without .jsonl>__grounded10.jsonl. Resumable.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "v2data"))
from score import decided_by_source, load_llm  # noqa: E402
from member3_backend.crosscheck import crosscheck_verdict, llm_verdict_used, second_reading_candidate  # noqa: E402
from member3_backend.number_guard import NUMBER_NOTE  # noqa: E402
from member1_model.llm_verifier import LLMVerifier  # noqa: E402


def candidate(c: dict, open_verdict: str | None) -> bool:
    """See member3_backend.crosscheck.second_reading_candidate (the same rule the live pipeline uses)."""
    if decided_by_source(c):
        return False
    return second_reading_candidate(c.get("nli_prob"), open_verdict, (c.get("note") or "").startswith(NUMBER_NOTE))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--llm", required=True, help="the open-mode answers for this run")
    ap.add_argument("--provider", default="ollama")
    ap.add_argument("--model", default="gpt-oss:20b")
    ap.add_argument("--flagged", action="store_true",
                    help="instead: every claim the cross-check flags Hallucinated (no source) -- the false-alarm guard")
    a = ap.parse_args()
    llm, reasons = load_llm(a.llm), load_llm(a.llm, "reason")
    out = Path(a.llm[:-6] + "__grounded10.jsonl")
    done = {json.loads(l)["claim"] for l in out.read_text(encoding="utf-8").splitlines() if l.strip()} if out.exists() else set()
    todo, seen = [], set(done)
    for r in map(json.loads, (ROOT / "v2data" / "runs" / f"{a.run}.jsonl").read_text(encoding="utf-8").splitlines()):
        for c in r["claims"]:
            if c["text"] in seen or c["text"] not in llm:
                continue
            used = llm_verdict_used(llm[c["text"]], reasons.get(c["text"]))
            if a.flagged:
                pick = not decided_by_source(c) and crosscheck_verdict(
                    c["verdict"], False, c.get("nli_prob"), used, (c.get("note") or "").startswith(NUMBER_NOTE)) == "Hallucinated"
            else:
                pick = candidate(c, used)
            if pick:
                seen.add(c["text"])
                todo.append(c)
    print(f"{len(done)} done, {len(todo)} to ask", flush=True)
    local = a.provider == "ollama"
    v = LLMVerifier(model=a.model, mode="grounded", provider=a.provider, min_interval_s=0 if local else 2.5,
                    timeout_s=900 if local else 90)
    v.max_passages = 10
    with open(out, "a", encoding="utf-8") as f:
        for k, c in enumerate(todo, 1):
            try:
                j = v.verify(c["text"], c["passages"])
            except Exception as e:
                print(f"skip ({type(e).__name__})", flush=True)
                continue
            f.write(json.dumps({"claim": c["text"], "verdict": j.verdict, "p_true": j.p_true, "reason": j.reason},
                               ensure_ascii=False) + "\n")
            f.flush()
            if k % 25 == 0:
                print(f"{k}/{len(todo)}", flush=True)
    print("finished", flush=True)


if __name__ == "__main__":
    main()
