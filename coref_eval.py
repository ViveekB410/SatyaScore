"""
coref_eval.py -- which pronoun rule should claim extraction use?

  nearest   the nearest preceding entity of a compatible type (the original rule)
  salience  the sentence subject / topic first (ClaimExtractor._referents_by_salience)

Test data, labels by construction: introductions of English Wikipedia articles (cached by
the Wikipedia expansion, results/_wiki_cache and instance/wiki_cache), sentences 2-6 of the
first paragraph. In an article's introduction, "it / its / he / his / she / her" almost
always refers to the article's own subject, so a pronoun counts as RIGHT when its
referent names the article subject (shares a word with the title, e.g. "Gandhi" for
"Mahatma Gandhi") and WRONG when it names something else. Noise (a pronoun that really
refers to another person or thing) affects both rules alike.

Split by a hash of the title: DESIGN (1 in 5) may be inspected while building the rule;
HELD-OUT (the rest) is run once, after this rule was committed.

DECISION RULE (fixed 2026-10-03, committed before the held-out run). "salience" becomes
the default (COREF_RULE) only if, on HELD-OUT:
  (a) wrong referents are FEWER than with "nearest", and
  (b) right referents are NOT fewer.

    .venv/Scripts/python.exe coref_eval.py design      (inspect while building)
    .venv/Scripts/python.exe coref_eval.py heldout     (once; writes results/coref_eval.md)
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

import member3_backend.claim_extractor as ce

ROOT = Path(__file__).resolve().parent
CACHES = (ROOT / "results" / "_wiki_cache", ROOT / "instance" / "wiki_cache")
PRONOUNS = {"it", "its", "he", "his", "she", "her"}
MAX_ARTICLES = 400
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
_STOP = {"the", "of", "and", "in", "a", "an", "list", "history"}


def articles(split: str) -> list[dict]:
    seen, out = set(), []
    for cache in CACHES:
        for f in sorted(cache.glob("en/*.json")):
            a = json.loads(f.read_text(encoding="utf-8"))
            title = a.get("title", "")
            if not title or title in seen:
                continue
            seen.add(title)
            design = int(hashlib.md5(title.encode()).hexdigest(), 16) % 5 == 0
            if design != (split == "design"):
                continue
            para = next((p.strip() for p in a.get("text", "").split("\n") if len(p.strip()) > 200), "")
            sents = _SENT.split(" ".join(para.split()))
            if len(sents) >= 3:
                out.append({"title": title, "text": " ".join(sents[:6]), "first": sents[0]})
    return out[:MAX_ARTICLES]


def title_words(title: str) -> set[str]:
    t = re.sub(r"\(.*?\)", "", title).casefold()
    return {w for w in re.findall(r"\w+", t) if w not in _STOP and len(w) > 1}


def score(rule: str, items: list[dict]) -> dict:
    ce.COREF_RULE = rule
    ex = ce.ClaimExtractor()
    nlp = ce._get_english_pipeline()
    right = wrong = unresolved = 0
    examples = []
    for it in items:
        doc = nlp(it["text"])
        refs = ex._build_pronoun_referents(doc)
        first_end = len(it["first"])
        for tok in doc:
            if tok.text.lower() not in PRONOUNS or tok.idx < first_end:
                continue
            r = refs.get(tok.i)
            if not r:
                unresolved += 1
            elif title_words(r) & title_words(it["title"]):
                right += 1
            else:
                wrong += 1
                if len(examples) < 15:
                    examples.append((it["title"], tok.text, r, tok.sent.text[:120]))
    return {"right": right, "wrong": wrong, "unresolved": unresolved, "examples": examples}


def main() -> None:
    split = sys.argv[1] if len(sys.argv) > 1 else "design"
    items = articles(split)
    res = {rule: score(rule, items) for rule in ("nearest", "salience")}
    n, s = res["nearest"], res["salience"]
    L = [f"# Pronoun resolution: nearest entity vs sentence subject ({split}: {len(items)} Wikipedia introductions)\n",
         "Pronouns it / its / he / his / she / her after the first sentence; RIGHT = the referent names the "
         "article's subject (labels by construction, see coref_eval.py).\n",
         "| rule | right | **wrong** | unresolved |", "|---|---|---|---|"]
    for rule, r in res.items():
        L.append(f"| {rule} | {r['right']} | **{r['wrong']}** | {r['unresolved']} |")
    if split == "heldout":
        a, b = s["wrong"] < n["wrong"], s["right"] >= n["right"]
        L += ["", "**Decision rule (fixed before this run):** adopt \"salience\" only if wrong referents are "
              "fewer and right referents not fewer than with \"nearest\".", "",
              f"(a) fewer wrong: {'met' if a else 'NOT met'} ({n['wrong']} -> {s['wrong']}); "
              f"(b) right not fewer: {'met' if b else 'NOT met'} ({n['right']} -> {s['right']}). "
              + ("**Adopt: COREF_RULE = \"salience\".**" if a and b else "**Do not adopt.**")]
    for rule, r in res.items():
        L += ["", f"## {rule}: examples of wrong referents", "", "| article | pronoun | resolved to | sentence |",
              "|---|---|---|---|"]
        L += [f"| {t} | {p} | {ref} | {sent} |" for t, p, ref, sent in r["examples"]]
    text = "\n".join(L) + "\n"
    if split == "heldout":
        (ROOT / "results" / "coref_eval.md").write_text(text, encoding="utf-8")
    print("\n".join(L[:8 if split == "design" else 12]))


if __name__ == "__main__":
    main()
