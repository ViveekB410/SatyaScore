"""
number_guard_eval_v2.py -- second attempt: should number guard VERSION 2 be on?

Version 1 was not adopted (results/number_guard_eval.md). Version 2 (member3_backend/
number_guard.py) checks only years and numbers >= 100 written in digits, skips reference
numbers, reads Indian digit grouping, compares round numbers at their own precision, and looks
in every retrieved passage of the deciding passage's article.

FRESH data: version 1 used the FIRST sentence with a number of each cached Wikipedia
introduction; this uses the SECOND such sentence (disjoint by construction). The sentence must
contain a number the guard checks, and the FALSE copy changes one of those (years +/- 3..25,
other numbers x2, x3 or /2) -- small numbers are outside version 2's scope by design (stated as
a limitation). The annotated claims are the same as in version 1 (seen; reported, and rule (c)
still applies).

DECISION RULE (fixed 2026-10-03, committed before the first run; the same as version 1):
adopt (SATYASCORE_NUMBER_GUARD=true by default) only if
  (a) wiki: FALSE-number claims marked Verified fall by at least half;
  (b) wiki: TRUE claims marked Verified fall by at most 5% (relative);
  (c) annotated: gold-Verified claims marked Verified fall by at most 10% (relative).

    .venv/Scripts/python.exe number_guard_eval_v2.py   -> results/number_guard_eval_v2.md/.csv
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import pandas as pd

from member1_model.cmhsa import KG_NOTE
from member3_backend.factcheck_rules import FC_NOTE_PREFIX
from member3_backend.number_guard import _NUM, _REFERENCE, _is_year, checked_numbers, missing_numbers, numbers
from nli_model_search import load_sets
from number_guard_eval import CACHES, _SENT

ROOT = Path(__file__).resolve().parent
SEED, N_EN, N_HI = 4, 100, 40


def wiki_sentences(lang: str, n: int, rng: random.Random) -> list[str]:
    pool, seen = [], set()
    for cache in CACHES:
        for f in sorted(cache.glob(f"{lang}/*.json")):
            a = json.loads(f.read_text(encoding="utf-8"))
            if a.get("title") in seen:
                continue
            seen.add(a.get("title"))
            para = next((p.strip() for p in a.get("text", "").split("\n") if len(p.strip()) > 150), "")
            qualifying = [s for s in _SENT[lang].split(" ".join(para.split()))[:5]
                          if 40 <= len(s) <= 250 and numbers(s) and "(" not in s]
            # version 1 used qualifying[0]; the second one is fresh
            if len(qualifying) >= 2 and checked_numbers(qualifying[1]):
                pool.append(qualifying[1])
    return rng.sample(pool, min(n, len(pool)))


def perturb(sentence: str, rng: random.Random) -> tuple[str, str] | None:
    """(false sentence, the new number as written), changing a number the guard checks."""
    ms = []
    for m in _NUM.finditer(sentence):
        raw = m.group(1)
        x = float(raw.replace(",", "").translate(str.maketrans("०१२३४५६७८९", "0123456789")))
        if not _REFERENCE.search(sentence[:m.start(1)]) and (("," not in raw and _is_year(x)) or x >= 100):
            ms.append((m, raw, x))
    if not ms:
        return None
    m, raw, x = rng.choice(ms)
    if "," not in raw and _is_year(x):
        new = int(x) + rng.choice([-1, 1]) * rng.randint(3, 25)
        txt = str(min(new, 2025)) if min(new, 2025) != int(x) else str(int(x) - 9)
    elif x.is_integer():
        new = int(x) * rng.choice([2, 3]) if rng.random() < 0.6 else int(x) // 2
        txt = f"{new:,}" if "," in raw else str(new)
    else:
        txt = str(round(x * 2, len(raw.split(".")[1])))
    if txt == raw:
        return None
    return sentence[:m.start(1)] + txt + sentence[m.end(1):], txt


def guarded(verdict: str, note: str | None, claim: str, deciding, texts: list[str]) -> str:
    elsewhere = note and (note == KG_NOTE or note.startswith(("judged by LLM", FC_NOTE_PREFIX)))
    if verdict == "Verified" and not elsewhere and deciding and deciding[1] == "supports" and texts \
            and missing_numbers(claim, texts):
        return "Uncertain"
    return verdict


def run_text(pipe, text: str, lang: str) -> list[dict]:
    try:
        r = pipe.run(text, lang)
    except ValueError:  # no claims in the text
        return []
    return [{"claim": c.text, "off": s.verdict.value,
             "on": guarded(s.verdict.value, s.note, c.text, ev.get("deciding"), ev.get("article_texts") or [])}
            for c, s, ev in zip(r.claims, r.scores, r.evidence)]


def main() -> None:
    import member3_backend.api as api
    api.load_starter_corpus()
    api._warmup_models()
    pipe = api._pipeline
    pipe.number_guard = False
    pipe.keep_article_texts = True
    rng = random.Random(SEED)
    rows = []
    for lang, n in (("en", N_EN), ("hi", N_HI)):
        for k, s in enumerate(wiki_sentences(lang, n, rng)):
            for c in run_text(pipe, s, lang):
                rows.append({"set": "wiki", "lang": lang, "gold": "Verified", **c})
            if (p := perturb(s, rng)) is not None:
                false_s, new = p
                for c in run_text(pipe, false_s, lang):
                    if new in c["claim"] or new.replace(",", "") in c["claim"].replace(",", ""):
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
    res.to_csv(ROOT / "results" / "number_guard_eval_v2.csv", index=False, encoding="utf-8")

    def ver(d, col):
        return int((d[col] == "Verified").sum())
    w, a = res[res.set == "wiki"], res[res.set == "annotated"]
    wt, wf, at, af = w[w.gold == "Verified"], w[w.gold == "Hallucinated"], a[a.gold == "Verified"], a[a.gold == "Hallucinated"]
    fa, fb, ta, tb, aa, ab = ver(wf, "off"), ver(wf, "on"), ver(wt, "off"), ver(wt, "on"), ver(at, "off"), ver(at, "on")
    ok_a, ok_b, ok_c = fb <= fa / 2, tb >= 0.95 * ta, ab >= 0.90 * aa
    L = ["# Number guard, version 2 (fresh Wikipedia sentences)\n",
         "**Decision rule (fixed before running, same as version 1):** adopt only if (a) wiki false-number claims "
         "marked Verified fall by at least half, (b) wiki true claims marked Verified fall by at most 5%, "
         "(c) annotated gold-Verified claims marked Verified fall by at most 10%. Version 2 checks only years "
         "and numbers >= 100 written in digits; the false copies change such a number.\n",
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
    (ROOT / "results" / "number_guard_eval_v2.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L[:12]))


if __name__ == "__main__":
    main()
