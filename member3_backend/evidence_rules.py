"""
How per-passage NLI results become ONE score for a claim.

Diagnosis (results/diagnosis_true_claims.md): on TRUE statements the live rule
("the most decisive passage wins") produced false alarms, 41% of English claims
on unseen topics. The NLI model outputs "contradiction" when a passage is simply
about a DIFFERENT thing (a football passage "contradicts" a cricket claim; the
prime minister of India "contradicts" one about Canada), and the most decisive
passage then overrode passages that supported the claim. Missing evidence was
being read as contradiction.

`gated` rule:
  1. support first: if any passage entails the claim (P(entail) >= 0.5), the
     claim is supported: score 0.5 + 0.5 * max entailment;
  2. otherwise only an ON-TOPIC passage may contradict it: a passage whose
     Wikipedia article title appears in the claim (a cricket claim can be
     contradicted by the "Cricket" article, never by "Association football");
  3. otherwise there is no usable evidence either way: the score stays near 0.5
     (Uncertain, "not enough evidence"), never Hallucinated.
`legacy` is the previous rule, kept for comparison.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ENTAIL_WINS = 0.5
_PAREN = re.compile(r"\s*\([^)]*\)")
# punctuation to spaces; keeps letters AND combining marks (Devanagari matras)
_PUNCT = re.compile(r"[\s.,;:!?\"'“”‘’()\[\]{}\-–—/|।॥]+")


def _norm(s: str) -> str:
    return " ".join(_PUNCT.sub(" ", s.casefold()).split())


_FUNCTION_WORDS = {"of", "and", "in", "the", "for", "on", "at", "to", "a", "an", "by", "with", "from",
                   "vs", "versus", "list", "comparison", "history", "outline", "glossary", "rules"}


def title_forms(title: str, strict: bool = False) -> list[str]:
    """Names that identify an article in a claim: the title without a
    parenthetical qualifier or trailing ", place" ("Chief Minister (India)" ->
    "chief minister"), plus its last word if that is a distinctive head noun or
    surname of 4+ letters ("Mahatma Gandhi" -> "gandhi", "Association football"
    -> "football"). strict: the last-word shortcut only for short name-like titles
    (<= 3 words, no function words), so "Comparison of baseball and cricket" is
    not "cricket" and "Prime Minister of India" is not "india"."""
    base = _norm(_PAREN.sub("", title).split(",")[0])
    if not base:
        return []
    forms = [base]
    words = base.split()
    shortcut = len(words) > 1 and len(words[-1]) >= 4
    if strict:
        shortcut = shortcut and len(words) <= 3 and not (set(words) & _FUNCTION_WORDS)
    if shortcut:
        forms.append(words[-1])
    return forms


class SubjectIndex:
    """Which article a passage comes from, in the claim's terms. Passage ids are
    "<English title>::<lang>::<n>" (demo corpus) or "wiki:<lang>:<title>::<n>"
    (expansion). Hindi demo passages carry the English title; their Hindi title
    comes from evidence_corpus_cache.json."""

    def __init__(self, hi_titles: dict[str, str] | None = None, strict: bool = False):
        self.hi_titles = hi_titles or {}
        self.strict = strict

    @classmethod
    def from_cache(cls, path: Path | str, strict: bool = False) -> "SubjectIndex":
        p = Path(path)
        if not p.exists():
            return cls(strict=strict)
        cache = json.loads(p.read_text(encoding="utf-8"))
        return cls({(e.get("en_title") or k): e["hi_title"] for k, e in cache.items() if e.get("hi_title")},
                   strict=strict)

    def names(self, passage_id: str) -> list[str]:
        if passage_id.startswith("wiki:"):
            _, _, rest = passage_id.split(":", 2)
            return title_forms(rest.rsplit("::", 1)[0], self.strict)
        parts = passage_id.split("::")
        title = parts[0]
        forms = title_forms(title, self.strict)
        if len(parts) > 1 and parts[1] == "hi" and title in self.hi_titles:
            forms += title_forms(self.hi_titles[title], self.strict)
        return forms

    def on_topic(self, claim: str, passage_id: str) -> bool:
        c = f" {_norm(claim)} "
        return any(f" {f} " in c for f in self.names(passage_id))


def aggregate(rows: list[tuple[float, float, bool]]) -> float:
    """rows: (P(entail), P(contradict), on_topic) per premise. See module doc."""
    if not rows:
        return 0.5
    max_e = max(e for e, _, _ in rows)
    if max_e >= ENTAIL_WINS:
        return 0.5 + 0.5 * max_e
    on_topic_c = [c for _, c, t in rows if t]
    return 0.5 + 0.5 * (max_e - (max(on_topic_c) if on_topic_c else 0.0))


def aggregate_legacy(rows: list[tuple[float, float, bool]]) -> float:
    """Previous rule: the most decisive passage's 0.5 + 0.5 * (e - c)."""
    if not rows:
        return 0.5
    nets = [0.5 + 0.5 * (e - c) for e, c, _ in rows]
    return max(nets, key=lambda s: abs(s - 0.5))


RULES = {"gated": aggregate, "legacy": aggregate_legacy}

# --- which passage decided, and where it comes from (shown to users as sources) ----------

LOW, HIGH = 0.35, 0.65  # the verdict tiers (member1_model/cmhsa.py)


def deciding(rows: list[tuple[float, float, bool, str]], aggregation: str = "gated") -> tuple[str, str] | None:
    """(passage_id, "supports" | "contradicts") for the passage that decided the NLI
    score, by the same logic as the rule itself; None when no passage decided it
    (the claim is Uncertain / there is no usable evidence). rows: (e, c, on_topic, id)."""
    if not rows:
        return None
    if aggregation == "legacy":
        best = max(rows, key=lambda r: abs(r[0] - r[1]))
        net = 0.5 + 0.5 * (best[0] - best[1])
        return (best[3], "supports") if net > HIGH else (best[3], "contradicts") if net < LOW else None
    top_e = max(rows, key=lambda r: r[0])
    if top_e[0] >= ENTAIL_WINS:
        return top_e[3], "supports"
    on_topic = [r for r in rows if r[2]]
    if on_topic:
        top_c = max(on_topic, key=lambda r: r[1])
        if 0.5 + 0.5 * (top_e[0] - top_c[1]) < LOW:
            return top_c[3], "contradicts"
    return None


def passage_source(passage_id: str, hi_titles: dict[str, str] | None = None) -> tuple[str, str, str]:
    """(title, language, Wikipedia URL) of the article a passage comes from."""
    from urllib.parse import quote
    if passage_id.startswith("wiki:"):
        _, lang, rest = passage_id.split(":", 2)
        title = rest.rsplit("::", 1)[0]
    else:
        parts = passage_id.split("::")
        title, lang = parts[0], (parts[1] if len(parts) > 1 else "en")
        if lang == "hi":  # demo-corpus Hindi passages carry the English title
            if hi_titles and title in hi_titles:
                title = hi_titles[title]
            else:
                lang = "en"  # no Hindi title known: link the English article
    return title, lang, f"https://{lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}"
