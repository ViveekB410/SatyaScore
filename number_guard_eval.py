"""
number_guard_eval.py -- should the number guard (member3_backend/number_guard.py) be on?

Sets:
  wiki       sentences with a number from cached Wikipedia introductions (English and Hindi,
             results/_wiki_cache + instance/wiki_cache), each TRUE as written, plus a FALSE
             copy with one year or number changed (years +/- 3..25, other numbers x2, x3 or /2).
             Labels by construction. Verbatim Wikipedia is easy to retrieve (flattering for the
             true sentences), hence also:
  annotated  the annotated chatbot claims (train / test / round 3) that contain a number.

The pipeline runs once per text with the guard OFF (the live configuration otherwise); the
guard is applied to its output exactly as the pipeline would (Verified by an NLI passage that
lacks a claim number -> Uncertain), so ON and OFF are compared on identical evidence.

DECISION RULE (fixed 2026-10-03, committed before the first run). The guard becomes the live
default (SATYASCORE_NUMBER_GUARD=true) only if
  (a) wiki: FALSE-number claims marked Verified fall by at least half;
  (b) wiki: TRUE claims marked Verified fall by at most 5% (relative);
  (c) annotated: gold-Verified claims marked Verified fall by at most 10% (relative).
The guard never creates a Hallucinated verdict, so false alarms cannot rise.

    .venv/Scripts/python.exe number_guard_eval.py      (GPU; ~30 min) -> results/number_guard_eval.md/.csv
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path

import pandas as pd

from member1_model.cmhsa import KG_NOTE
from member3_backend.factcheck_rules import FC_NOTE_PREFIX
from member3_backend.number_guard import _NUM, _is_year, missing_numbers, numbers
from nli_model_search import load_sets

ROOT = Path(__file__).resolve().parent
CACHES = (ROOT / "results" / "_wiki_cache", ROOT / "instance" / "wiki_cache")
SEED, N_EN, N_HI = 3, 100, 40
_SENT = {"en": re.compile(r"(?<=[.!?])\s+(?=[A-Z])"), "hi": re.compile(r"(?<=[।!?])\s+")}


def wiki_sentences(lang: str, n: int, rng: random.Random) -> list[str]:
    pool, seen = [], set()
    for cache in CACHES:
        for f in sorted(cache.glob(f"{lang}/*.json")):
            a = json.loads(f.read_text(encoding="utf-8"))
            if a.get("title") in seen:
                continue
            seen.add(a.get("title"))
            para = next((p.strip() for p in a.get("text", "").split("\n") if len(p.strip()) > 150), "")
            for s in _SENT[lang].split(" ".join(para.split()))[:5]:
                if 40 <= len(s) <= 250 and numbers(s) and "(" not in s:
                    pool.append(s)
                    break
    return rng.sample(pool, min(n, len(pool)))


def perturb(sentence: str, rng: random.Random) -> tuple[str, str] | None:
    """(false sentence, the new number as written) with one number changed."""
    ms = list(_NUM.finditer(sentence))
    if not ms:
        return None
    m = rng.choice(ms)
    raw = m.group(1)
    x = float(raw.replace(",", ""))
    if _is_year(x):
        new = int(x) + rng.choice([-1, 1]) * rng.randint(3, 25)
        new = min(new, 2025) if new != int(x) else new + 7
        txt = str(new)
    elif x.is_integer():
        new = int(x) * rng.choice([2, 3]) if x < 4 or rng.random() < 0.6 else int(x) // 2
        txt = f"{new:,}" if "," in raw else str(new)
    else:
        txt = str(round(x * 2, len(raw.split(".")[1])))
    if txt == raw:
        return None
    return sentence[:m.start(1)] + txt + sentence[m.end(1):], txt


def guarded(verdict: str, note: str | None, claim: str, deciding, text: str | None) -> str:
    elsewhere = note and (note == KG_NOTE or note.startswith(("judged by LLM", FC_NOTE_PREFIX)))
    if verdict == "Verified" and not elsewhere and deciding and deciding[1] == "supports" and text \
            and missing_numbers(claim, text):
        return "Uncertain"
    return verdict


def run_text(pipe, text: str, lang: str) -> list[dict]:
    r = pipe.run(text, lang)
    return [{"claim": c.text, "off": s.verdict.value,
             "on": guarded(s.verdict.value, s.note, c.text, ev.get("deciding"), ev.get("deciding_text"))}
            for c, s, ev in zip(r.claims, r.scores, r.evidence)]


def main() -> None:
    import member3_backend.api as api
    api.load_starter_corpus()
    api._warmup_models()
    pipe = api._pipeline
    pipe.number_guard = False
    rng = random.Random(SEED)
    rows = []
    for lang, n in (("en", N_EN), ("hi", N_HI)):
        for k, s in enumerate(wiki_sentences(lang, n, rng)):
            for c in run_text(pipe, s, lang):
                rows.append({"set": "wiki", "lang": lang, "gold": "Verified", **c})
            if (p := perturb(s, rng)) is not None:
                false_s, new = p
                for c in run_text(pipe, false_s, lang):  # only claims carrying the changed number are false
                    if new in c["claim"].replace(",", "") or new in c["claim"]:
                        rows.append({"set": "wiki", "lang": lang, "gold": "Hallucinated", **c})
            print(f"wiki {lang}: {k + 1}/{n}", flush=True)
    for name, df in load_sets().items():
        for r in df.itertuples(index=False):
            if not numbers(r.claim_text):
                continue
            out = run_text(pipe, r.claim_text, r.language)
            if len(out) == 1:
                rows.append({"set": "annotated", "lang": r.language, "gold": r.gold_verdict, **out[0]})
    res = pd.DataFrame(rows)
    res.to_csv(ROOT / "results" / "number_guard_eval.csv", index=False, encoding="utf-8")

    def ver(d, col):
        return int((d[col] == "Verified").sum())
    w, a = res[res.set == "wiki"], res[res.set == "annotated"]
    wt, wf, at, af = w[w.gold == "Verified"], w[w.gold == "Hallucinated"], a[a.gold == "Verified"], a[a.gold == "Hallucinated"]
    fa, fb = ver(wf, "off"), ver(wf, "on")
    ta, tb = ver(wt, "off"), ver(wt, "on")
    aa, ab = ver(at, "off"), ver(at, "on")
    ok_a, ok_b, ok_c = fb <= fa / 2, tb >= 0.95 * ta, ab >= 0.90 * aa
    L = ["# Number guard: Verified only if the evidence contains the claim's numbers\n",
         "**Decision rule (fixed before running):** adopt only if (a) wiki false-number claims marked Verified "
         "fall by at least half, (b) wiki true claims marked Verified fall by at most 5%, (c) annotated "
         "gold-Verified claims marked Verified fall by at most 10%. The guard never creates a Hallucinated verdict.\n",
         "| set | claims | marked Verified: guard off | guard on |", "|---|---|---|---|",
         f"| wiki, TRUE claims | {len(wt)} | {ta} | {tb} |",
         f"| wiki, FALSE-number claims (wrongly Verified) | {len(wf)} | **{fa}** | **{fb}** |",
         f"| annotated, gold Verified | {len(at)} | {aa} | {ab} |",
         f"| annotated, gold Hallucinated (wrongly Verified) | {len(af)} | {ver(af, 'off')} | {ver(af, 'on')} |", "",
         f"(a) {'met' if ok_a else 'NOT met'} ({fa} -> {fb}); (b) {'met' if ok_b else 'NOT met'} ({ta} -> {tb}); "
         f"(c) {'met' if ok_c else 'NOT met'} ({aa} -> {ab}). "
         + ("**Adopt: SATYASCORE_NUMBER_GUARD on by default.**" if ok_a and ok_b and ok_c else "**Do not adopt.**"),
         "", "## True claims that lose Verified (the cost)", ""]
    lost = res[(res.gold == "Verified") & (res.off == "Verified") & (res.on != "Verified")]
    L += [f"- [{r.set}, {r.lang}] {r.claim}" for r in lost.itertuples()] or ["- none"]
    (ROOT / "results" / "number_guard_eval.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:12]))


if __name__ == "__main__":
    main()
