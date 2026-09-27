"""
diagnose_true_claims.py -- where do TRUE statements go wrong in the live pipeline?

Input that is true by construction: the lead sentence of Wikipedia articles.
  seen    articles in the demo corpus (their text is in the evidence index)
  unseen  articles fetched by the expansion run that are NOT in the demo corpus
Each sentence runs through the full live pipeline (claim extraction, retrieval,
NLI, KG, scoring; the same objects the API builds). A true sentence marked
Hallucinated is a FALSE ALARM. For each claim the stage-level details are kept
(extracted text, the 3 passages with similarity and entail/neutral/contradict,
which passage decided, KG) so every false alarm can be attributed to a stage.

It also re-scores the same NLI numbers under alternative evidence-aggregation
rules. This is a DIAGNOSIS on true-only data (it cannot show the cost in missed
hallucinations); any rule change must then be tested on the labelled splits.

    .venv/Scripts/python.exe diagnose_true_claims.py      (GPU recommended; ~5 min)
Writes results/diagnosis_true_claims.md and results/diagnosis_true_claims.csv.
"""
from __future__ import annotations
import json
import random
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from member3_backend.pipeline import MIN_RELEVANCE_THRESHOLD

ROOT = Path(__file__).resolve().parent
N_EN, N_HI, SEED = 40, 20, 7
_EN_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")
_HI_SENT = re.compile(r"(?<=[।!?])\s+")


def lead_sentence(text: str, lang: str) -> str | None:
    para = next((p.strip() for p in text.split("\n") if len(p.strip()) > 60), "")
    parts = (_HI_SENT if lang == "hi" else _EN_SENT).split(para)
    s = " ".join(parts[0].split()) if parts else ""
    return s if 40 <= len(s) <= 300 else None


def samples() -> list[dict]:
    rng = random.Random(SEED)
    demo = json.loads((ROOT / "corpus_passages_demo.json").read_text(encoding="utf-8"))
    first = {(p["title"], p["lang"]): p["text"] for p in demo if p["id"].endswith("::0")}
    seen_titles = {t for t, _ in first}
    out = []
    for lang, n in (("en", N_EN), ("hi", N_HI)):
        pool = [(t, s) for (t, l), txt in sorted(first.items()) if l == lang and (s := lead_sentence(txt, lang))]
        out += [{"group": "seen", "lang": lang, "title": t, "text": s} for t, s in rng.sample(pool, min(n, len(pool)))]
    cache = ROOT / "results" / "_wiki_cache"
    unseen = []
    for f in sorted(cache.glob("*/*.json")):
        a = json.loads(f.read_text(encoding="utf-8"))
        if a["title"] not in seen_titles and (s := lead_sentence(a["text"], a["lang"])):
            unseen.append({"group": "unseen", "lang": a["lang"], "title": a["title"], "text": s})
    for lang, n in (("en", N_EN), ("hi", N_HI)):
        pool = [u for u in unseen if u["lang"] == lang]
        out += rng.sample(pool, min(n, len(pool)))
    return out


def tier(s: float) -> str:
    return "Hallucinated" if s < 0.35 else "Verified" if s > 0.65 else "Uncertain"


# alternative evidence-aggregation rules (diagnostic only), from per-passage (sim, e, c)
def rule_current(rows):      # most decisive passage (live)
    n = [0.5 + 0.5 * (e - c) for _, e, c in rows]
    return max(n, key=lambda x: abs(x - 0.5)) if n else 0.5


def rule_top1(rows):         # the most similar passage only
    return 0.5 + 0.5 * (rows[0][1] - rows[0][2]) if rows else 0.5


def rule_support_first(rows):  # any entailing passage wins; contradiction only if nothing entails
    if not rows:
        return 0.5
    e = max(r[1] for r in rows)
    return 0.5 + 0.5 * e if e >= 0.5 else 0.5 - 0.5 * max(r[2] for r in rows)


RULES = {"current (most decisive)": rule_current, "top-1 passage only": rule_top1,
         "support-first": rule_support_first}


def main() -> None:
    import member3_backend.api as api
    api.load_starter_corpus()
    api._warmup_models()
    pipe = api._pipeline
    items = samples()
    print(f"{len(items)} true sentences; running the live pipeline...", flush=True)

    recs = []
    for k, it in enumerate(items, 1):
        try:
            res = pipe.run(it["text"], it["lang"])
        except ValueError as e:
            recs.append({**it, "claim": None, "verdict": "no claims", "note": str(e)})
            continue
        for claim, score, sub in zip(res.claims, res.scores, res.sub_scores):
            v = api._embedder.embed(["q"], [claim.text], [it["lang"]]).vectors[0]
            passages = [p for p in api._retriever.retrieve("q", v, top_k=pipe.nli_top_k).passages
                        if p.score >= MIN_RELEVANCE_THRESHOLD]
            nli = api._nli_scorer.score_batch(["q"] * len(passages), [p.text for p in passages],
                                              [claim.text] * len(passages)) if passages else []
            rows = [(p.score, r.entailment_prob, r.contradiction_prob) for p, r in zip(passages, nli)]
            decisive = int(np.argmax([abs(0.5 * (e - c)) for _, e, c in rows])) if rows else None
            titles = [p.passage_id.split("::")[0].replace("wiki:en:", "").replace("wiki:hi:", "") for p in passages]
            rec = {**it, "claim": claim.text, "extraction": claim.extraction_method,
                   "verdict": score.verdict.value, "score": score.hallu_score,
                   "kg": sub.kg_conf, "kg_decided": bool(score.note and "knowledge graph" in score.note),
                   "n_passages": len(rows), "decisive_rank": None if decisive is None else decisive + 1,
                   "decisive_from_source": None if decisive is None else titles[decisive] == it["title"],
                   "source_in_top3": it["title"] in titles, "max_entail": max((r[1] for r in rows), default=0.0),
                   "passages": json.dumps([{"title": t, "sim": round(s, 3), "e": round(e, 3), "c": round(c, 3)}
                                           for t, (s, e, c) in zip(titles, rows)], ensure_ascii=False)}
            for name, fn in RULES.items():
                rec[f"rule:{name}"] = tier(fn(rows)) if not rec["kg_decided"] else score.verdict.value
            recs.append(rec)
        if k % 10 == 0:
            print(f"  {k}/{len(items)}", flush=True)

    df = pd.DataFrame(recs)
    df.to_csv(ROOT / "results" / "diagnosis_true_claims.csv", index=False, encoding="utf-8")
    ok = df[df.claim.notna()]
    L = ["# Diagnosis: true statements through the live pipeline\n",
         f"{len(items)} lead sentences of Wikipedia articles (true by construction; seed {SEED}): seen = article "
         f"in the evidence index, unseen = not in it. {len(ok)} claims extracted. A true claim marked "
         f"**Hallucinated is a false alarm**.\n",
         "## Verdicts on true claims (live rule)\n",
         "| group | lang | claims | Verified | Uncertain | **Hallucinated (false alarm)** |", "|---|---|---|---|---|---|"]
    for (g, l), s in ok.groupby(["group", "lang"]):
        c = s.verdict.value_counts()
        L.append(f"| {g} | {l} | {len(s)} | {c.get('Verified', 0)} | {c.get('Uncertain', 0)} | "
                 f"**{c.get('Hallucinated', 0)}** ({c.get('Hallucinated', 0) / len(s):.0%}) |")
    fa = ok[ok.verdict == "Hallucinated"]
    L += ["", f"## Why the {len(fa)} false alarms happened\n"]
    if len(fa):
        kg_dec = fa.kg_decided.astype(bool)
        L += [f"- decided by the KG: {int(kg_dec.sum())}",
              f"- decided by NLI: {int((~kg_dec).sum())}, of which:",
              f"  - the deciding passage was **not the top-1** (most similar) passage: "
              f"{int((fa.decisive_rank.fillna(1) > 1).sum())}",
              f"  - another retrieved passage **entailed** the claim (P(entail) ≥ 0.5) but a contradicting "
              f"passage won: {int((fa.max_entail >= 0.5).sum())}",
              f"  - seen group: the article the sentence came from was in the top 3: "
              f"{int(fa[fa.group == 'seen'].source_in_top3.sum())} of {int((fa.group == 'seen').sum())}; the "
              f"deciding passage came from that article: {int(fa[fa.group == 'seen'].decisive_from_source.fillna(False).sum())}"]
    L += ["", "## Same NLI numbers, other aggregation rules (diagnostic, true claims only)\n",
          "| rule | Verified | Uncertain | Hallucinated (false alarms) |", "|---|---|---|---|"]
    for name in RULES:
        c = ok[f"rule:{name}"].value_counts()
        L.append(f"| {name} | {c.get('Verified', 0)} | {c.get('Uncertain', 0)} | {c.get('Hallucinated', 0)} |")
    L += ["", "Fewer false alarms here is necessary but not sufficient: a rule must also keep catching real "
          "hallucinations, which only the labelled splits can show.", "",
          "## Every false alarm", "", "| group | lang | claim | deciding passage (rank) | passages: title sim e c |",
          "|---|---|---|---|---|"]
    for _, r in fa.iterrows():
        ps = "; ".join(f"{p['title'][:28]} {p['sim']} e{p['e']} c{p['c']}" for p in json.loads(r.passages))
        L.append(f"| {r.group} | {r.lang} | {str(r.claim)[:90]} | {r.decisive_rank} | {ps} |")
    out = ROOT / "results" / "diagnosis_true_claims.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    sys.stdout.buffer.write(("\n".join(L[:30]) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
