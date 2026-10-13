"""
v2data/kg_relations_eval.py -- keep-or-drop check for the Version 2 Wikidata relations
(results/v2_data_PROTOCOL.md, "Wikidata relations"), on the DEV sets only, with live Wikidata.

Claims: every dev claim the v1 run did not already decide by a source, taken from v2data/runs/v1_dev.jsonl.
Gold for a claim: a Mu-SHROOM labelled claim's own label; otherwise the item's label, used only when the
item has exactly one claim. A contradiction is correct if gold is false; a support is correct if gold is true.

    .venv/Scripts/python.exe v2data/kg_relations_eval.py
Writes results/v2_kg_relations_dev.md and caches answers in v2data/runs/_kg_relations_dev.jsonl.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "v2data"))
os.environ["SATYASCORE_KG_RELATIONS"] = "1"
from score import decided_by_source  # noqa: E402
from member2_data import kg_extra  # noqa: E402
from member2_data.entity_linker import EntityLinker  # noqa: E402
from member2_data.wikidata_connector import WikidataConnector  # noqa: E402

RUN = ROOT / "v2data" / "runs" / "v1_dev.jsonl"
CACHE = ROOT / "v2data" / "runs" / "_kg_relations_dev.jsonl"
OUT = ROOT / "results" / "v2_kg_relations_dev.md"
REL = {"P27": "nationality", "P495": "country of origin", "P17": "country", "P577": "year of a work",
       "P580": "year of a work", "P571": "year of a work", "P57": "director", "P161": "cast member",
       "P175": "performer", "P106": "occupation"}


def claims_with_gold() -> list[dict]:
    run = {(r["set"], r["key"]): r for r in map(json.loads, RUN.read_text(encoding="utf-8").splitlines())}
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
                if len(cl) != 1:
                    continue
            for c in cl:
                if not decided_by_source(c):
                    out.append({"set": name, "language": it.language, "gold": it.label, "claim": c["text"]})
    return out


def main() -> None:
    items = claims_with_gold()
    done = {}
    if CACHE.exists():
        for line in CACHE.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done[(r["language"], r["claim"])] = r
    todo = list({(x["language"], x["claim"]) for x in items} - set(done))
    print(f"{len(items)} claims, {len(todo)} to check", flush=True)
    linker, wd = EntityLinker(), WikidataConnector()

    def one(key):
        lang, claim = key
        try:
            v = kg_extra.check(claim, lang, linker, wd)
        except Exception as e:  # recorded, never a decision
            return {"language": lang, "claim": claim, "status": None, "pid": None, "error": type(e).__name__}
        ok = v is not None and v.status in ("supported", "contradicted")
        return {"language": lang, "claim": claim, "status": v.status if ok else None,
                "pid": v.property_pid if ok else None, "shown": list(v.actual_text) if ok else []}

    with open(CACHE, "a", encoding="utf-8") as f, ThreadPoolExecutor(4) as pool:
        for k, r in enumerate(pool.map(one, todo), 1):
            done[(r["language"], r["claim"])] = r
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            if k % 100 == 0:
                print(f"{k}/{len(todo)}", flush=True)

    tally = defaultdict(Counter)
    examples = defaultdict(list)
    for x in items:
        r = done.get((x["language"], x["claim"]))
        if not r or not r["status"]:
            continue
        rel = REL.get(r["pid"], r["pid"])
        right = (r["status"] == "contradicted") == (x["gold"] == "Hallucinated")
        tally[rel][(r["status"], right)] += 1
        if not right and len(examples[rel]) < 6:
            examples[rel].append(f"{x['set']}/{x['language']} gold={x['gold']} {r['status']}: {x['claim']} "
                                 f"(Wikidata: {', '.join(r.get('shown') or [])})")
    lines = ["# Version 2 Wikidata relations on the dev sets (keep-or-drop check)", "",
             f"{len(items)} dev claims that no v1 source decided; rule: keep a relation if >= 90% of its decisions "
             "are correct; contradictions below 90% -> support only.", "",
             "| relation | supported (correct/all) | contradicted (correct/all) | all decisions correct |",
             "|---|---|---|---|"]
    for rel, c in sorted(tally.items()):
        s_ok, s_all = c[("supported", True)], c[("supported", True)] + c[("supported", False)]
        k_ok, k_all = c[("contradicted", True)], c[("contradicted", True)] + c[("contradicted", False)]
        tot = s_all + k_all
        lines.append(f"| {rel} | {s_ok}/{s_all} | {k_ok}/{k_all} | {(s_ok + k_ok) / tot:.0%} ({s_ok + k_ok}/{tot}) |")
    lines += ["", "## Wrong decisions (up to 6 per relation)", ""]
    for rel, ex in sorted(examples.items()):
        lines += [f"**{rel}**", ""] + [f"- {e}" for e in ex] + [""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:len(tally) + 6]))


if __name__ == "__main__":
    main()
