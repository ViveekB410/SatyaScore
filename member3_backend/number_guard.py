"""
Number guard: a claim is Verified by a passage only if the passage contains the claim's
numbers.

Why: the NLI model largely ignores numbers. Measured live: "India became independent in
1950", "Mount Everest is 7,200 metres tall" and "The Indian Constitution came into effect on
15 August 1947" were all Verified, each supported by a passage that gives the right number.

The rule: for a claim Verified by an NLI passage (not by the knowledge graph, a fact-check or
the LLM judge), every number in the claim must appear in that passage -- years exactly, other
numbers within 1% ("8,849" matches "8,848.86"), number words counted ("eleven" = 11),
Devanagari digits read. Otherwise the claim becomes Uncertain (never Hallucinated: a missing
number is not proof of a wrong one). Adopted only if number_guard_eval.py meets its fixed rule.
"""
from __future__ import annotations

import re

NUMBER_NOTE = "a number in the claim is not in the supporting evidence"
REL_TOLERANCE = 0.01

_DEVANAGARI = str.maketrans("०१२३४५६७८९", "0123456789")
# a number not glued to a word or a hyphen: not "Chandrayaan-3", "21st", "COVID-19", "A4"
_NUM = re.compile(r"(?<![\w.\-])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?![\w\-]|\.\d)")
_WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen twenty".split())}
_WORDS.update({"thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90})
_WORD_RE = re.compile(r"\b(" + "|".join(sorted(_WORDS, key=len, reverse=True)) + r")(?:-(one|two|three|four|five|six|seven|eight|nine))?\b",
                      re.I)


def numbers(text: str) -> list[tuple[float, int]]:
    """(value, decimals written) for every number in the text."""
    t = text.translate(_DEVANAGARI)
    out = []
    for m in _NUM.finditer(t):
        s = m.group(1).replace(",", "")
        out.append((float(s), len(s.split(".")[1]) if "." in s else 0))
    for m in _WORD_RE.finditer(t):
        out.append((float(_WORDS[m.group(1).lower()] + (_WORDS[m.group(2).lower()] if m.group(2) else 0)), 0))
    return out


def _is_year(x: float) -> bool:
    return x.is_integer() and 1000 <= x <= 2100


def _close(claimed: tuple[float, int], found: float) -> bool:
    """Years must be equal. Other numbers: equal, or the passage's number rounds to the
    claim's number at the claim's precision (1.43 -> "1.4"; 8,848.86 -> "8,849"), or
    within 1% ("8,800" for 8,848.86)."""
    a, decimals = claimed
    if a == found:
        return True
    if _is_year(a) or _is_year(found):
        return False
    return round(found, decimals) == a or abs(a - found) <= REL_TOLERANCE * max(abs(a), abs(found))


def missing_numbers(claim: str, passage: str) -> list[str]:
    """The claim's numbers that the passage does not contain (as written in the claim)."""
    have = [v for v, _ in numbers(passage)]
    out = []
    for c in numbers(claim):
        if not any(_close(c, y) for y in have):
            out.append(str(int(c[0])) if c[0].is_integer() else str(c[0]))
    return out
