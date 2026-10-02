"""
Number guard: a claim is Verified by a passage only if the evidence contains the claim's
important numbers.

Why: the NLI model largely ignores numbers. Measured live: "India became independent in
1950", "Mount Everest is 7,200 metres tall" and "The Indian Constitution came into effect on
15 August 1947" were all Verified, each supported by a passage that gives the right number.

The rule (version 2): for a claim Verified by an NLI passage (not by the knowledge graph, a
fact-check or the LLM judge), every YEAR and every number of 100 or more written in DIGITS in
the claim must appear in a retrieved passage from the SAME ARTICLE as the deciding passage --
years exactly, other numbers when the passage's number rounds to the claim's at its precision
or is within 1% -- else the claim becomes Uncertain (never Hallucinated: a missing number is
not proof of a wrong one). Passages count number words ("eleven") and Devanagari digits, in
Western or Indian grouping ("4,30,000").

Version 1 (every number, the deciding passage only) was NOT adopted: it removed Verified from
too many true claims (results/number_guard_eval.md). Version 2's changes each address a cause
seen there: number words used as non-quantities ("one of the greatest", "two main types"),
small counts absent from the passage ("8 gold medals", list markers "२)"), Indian digit
grouping, reference numbers ("Article 324"), and true years given elsewhere in the article.
"""
from __future__ import annotations

import re

NUMBER_NOTE = "a number in the claim is not in the supporting evidence"
REL_TOLERANCE = 0.01
MIN_CHECKED = 100  # non-year numbers below this are not checked (small counts, list markers)

_DEVANAGARI = str.maketrans("०१२३४५६७८९", "0123456789")
# a number not glued to a word or a hyphen ("Chandrayaan-3", "21st", "COVID-19", "A4");
# digit groups in Western (1,430,000) or Indian (14,30,000) style
_NUM = re.compile(r"(?<![\w.\-])(\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?![\w\-]|\.\d)")
_WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen twenty".split())}
_WORDS.update({"thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90})
_WORD_RE = re.compile(r"\b(" + "|".join(sorted(_WORDS, key=len, reverse=True)) +
                      r")(?:-(one|two|three|four|five|six|seven|eight|nine))?\b", re.I)
# reference numbers, not quantities: "Article 370", "अनुच्छेद 324", "Section 377"
_REFERENCE = re.compile(r"(?:article|articles|section|sections|clause|chapter|schedule|amendment|rule|"
                        r"part|no\.?|number|अनुच्छेद|धारा|अध्याय|अनुसूची|संशोधन)\s*$", re.I)


def numbers(text: str, words: bool = True) -> list[tuple[float, int]]:
    """(value, decimals written) for every number in the text; number words too if `words`."""
    t = text.translate(_DEVANAGARI)
    out = []
    for m in _NUM.finditer(t):
        s = m.group(1).replace(",", "")
        out.append((float(s), len(s.split(".")[1]) if "." in s else 0))
    if words:
        for m in _WORD_RE.finditer(t):
            out.append((float(_WORDS[m.group(1).lower()] + (_WORDS[m.group(2).lower()] if m.group(2) else 0)), 0))
    return out


def _is_year(x: float) -> bool:
    return x.is_integer() and 1000 <= x <= 2100


def checked_numbers(claim: str) -> list[tuple[float, int, bool]]:
    """The claim's numbers the guard checks, as (value, precision, is_year): years and
    numbers >= MIN_CHECKED written in digits, not reference numbers. A number written with
    commas is never a year ("1,400 million"). Precision: decimals written, or for a round
    integer minus its trailing zeros, keeping two significant digits ("1,400" -> -2)."""
    t = claim.translate(_DEVANAGARI)
    out = []
    for m in _NUM.finditer(t):
        if _REFERENCE.search(t[:m.start(1)]):
            continue
        raw = m.group(1)
        s = raw.replace(",", "")
        x = float(s)
        year = "," not in raw and _is_year(x)
        if not (year or x >= MIN_CHECKED):
            continue
        if "." in s:
            precision = len(s.split(".")[1])
        else:
            precision = -min(len(s) - len(s.rstrip("0")), max(len(s) - 2, 0))
        out.append((x, precision, year))
    return out


def _close(claimed: tuple[float, int, bool], found: float) -> bool:
    """Years must be equal. Other numbers: equal, or the passage's number rounds to the
    claim's number at the claim's precision (1.43 -> "1.4"; 8,848.86 -> "8,849"; 1,430 ->
    "1,400"), or within 1%."""
    a, precision, year = claimed
    if a == found:
        return True
    if year:
        return False
    return round(found, precision) == a or abs(a - found) <= REL_TOLERANCE * max(abs(a), abs(found))


def missing_numbers(claim: str, evidence: str | list[str]) -> list[str]:
    """The checked numbers of the claim that no evidence text contains (as values)."""
    texts = [evidence] if isinstance(evidence, str) else evidence
    have = [v for t in texts for v, _ in numbers(t)]
    out = []
    for c in checked_numbers(claim):
        if not any(_close(c, y) for y in have):
            out.append(str(int(c[0])) if c[0].is_integer() else str(c[0]))
    return out
