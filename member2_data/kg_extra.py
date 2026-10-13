"""
More knowledge-graph checks, for fact types chatbots often get wrong and Wikidata states
exactly (found by probing unseen claims, 2026-10-03):

  authorship        "X wrote Y", "Y was written by X", "X is the author of Y", "X ने Y लिखी"
                    (before: "Rabindranath Tagore wrote Gitanjali" -> Hallucinated)
  current office    "X is the President of India", "X भारत के राष्ट्रपति हैं": a FORMER holder
                    is not "is" (before: "Pratibha Patil is the President of India" -> Verified)
  quantities        height / elevation, length, population, area, in English and Hindi
                    (before: "Mount Everest is 7,200 metres tall" -> Verified)
  currency          "The currency of X is Y", "X की मुद्रा Y है"
                    (before: "जापान की मुद्रा यूरो है" -> Verified)

The same safeguards as birthplaces and dates: subjects are matched by EXACT name; with
namesakes, any match supports and a contradiction needs every namesake with a value on record
to disagree; a claimed name (author, currency) only contradicts if it is itself a known
Wikidata item; anything unclear gives no signal (never a guessed contradiction).

check(claim, language, linker, wikidata) returns None when no pattern applies (the general KG
path then runs), else a TripleVerification (status "unknown" = applies but no answer).
"""
from __future__ import annotations

import os
import re

from member2_data.wikidata_connector import TripleVerification

MAX_NAMESAKES = 5
_DEV = str.maketrans("०१२३४५६७८९", "0123456789")


def _tokens(s: str) -> set[str]:
    return {t for t in re.split(r"[\s.,'’\"“”\-–()]+", s.casefold()) if t}


def name_matches(claimed: str, names: set[str]) -> bool:
    """Every word of the claimed name is in one of the item's labels or aliases:
    "Tagore" ~ "Rabindranath Tagore", "J. K. Rowling" ~ "J. K. Rowling", "rupee" ~ "Indian rupee"."""
    c = _tokens(claimed)
    return bool(c) and any(c <= _tokens(n) for n in names)


def _clean(s: str) -> str:
    s = re.sub(r"[*_\"“”‘’]", "", s).strip(" ,")
    s = re.sub(r"\s+in\s+\d{3,4}$", "", s)  # "Gitanjali in 1910"
    return re.sub(r"^the\s+", "", s, flags=re.I).strip()


def _ids(statements: list[dict]) -> list[str]:
    return [s["value"]["id"] for s in statements if isinstance(s.get("value"), dict) and "id" in s["value"]]


def _result(subject: str, pid: str, expected: str, status: str, shown: list[str]) -> TripleVerification:
    return TripleVerification(subject_qid=subject, property_pid=pid, expected_value=expected,
                              found=status == "supported",
                              confidence={"supported": 1.0, "contradicted": 0.0}.get(status),
                              used_fallback_label=False, source="live", status=status,
                              actual_text=tuple(dict.fromkeys(shown)))


def _unknown(pid: str, expected: str) -> TripleVerification:
    return _result("", pid, expected, "unknown", [])


def _shown(wd, qids: list[str], language: str) -> list[str]:
    labels = wd.labels(qids, language)
    return [labels[q] for q in qids if q in labels]


# --- name-valued facts: authorship and currency ---------------------------------------

def _named_value(subject_text: str, claimed: str, pid: str, language: str, linker, wd) -> TripleVerification:
    """Does `subject` have `claimed` as its `pid` value (author, currency)? Supported if any
    namesake's value is named like `claimed` or IS the item `claimed` names; contradicted only
    if every namesake with values disagrees and `claimed` names a known item."""
    subjects = (linker.search_places(subject_text, language) or ())[:MAX_NAMESAKES]
    claimed_items = set(linker.search_places(claimed, language) or ())
    disagree = []
    for s in subjects:
        values = _ids(wd.statements(s, pid) or [])
        if not values:
            continue
        names = wd.names(values, language)
        if claimed_items & set(values) or any(name_matches(claimed, names.get(v, set())) for v in values):
            return _result(s, pid, claimed, "supported", _shown(wd, values, language))
        disagree.append((s, values))
    if disagree and claimed_items:
        s, values = disagree[0]
        return _result(s, pid, claimed, "contradicted", _shown(wd, values, language))
    return _unknown(pid, claimed)


_WORK = r"(?:the (?:book|novel|poem|poems|play|epic|story|novella|collection) )?"
_EN_AUTHOR = [
    re.compile(rf"^(?P<author>.+?) (?:wrote|authored|penned) {_WORK}(?P<work>.+?)[\s.!]*$", re.I),
    re.compile(rf"^{_WORK}(?P<work>.+?) (?:was|is) (?:written|authored) by (?P<author>.+?)[\s.!]*$", re.I),
    re.compile(rf"^(?P<author>.+?) is the author of {_WORK}(?P<work>.+?)[\s.!]*$", re.I),
]
_HI_AUTHOR = re.compile(r"^(?P<author>.+?) ने (?P<work>.+?) (?:लिखी|लिखा|लिखे|की रचना की)(?: थी| था| थे| है| हैं)?$")


def _authorship(t: str, language: str):
    pats = _EN_AUTHOR if language == "en" else [_HI_AUTHOR]
    for p in pats:
        if m := p.match(t):
            author, work = _clean(m["author"]), _clean(m["work"])
            if author and work and len(author.split()) <= 6 and len(work.split()) <= 8:
                return author, work
    return None


_EN_CURRENCY = [
    re.compile(r"^the (?:official )?currency of (?P<s>.+?) is (?:the )?(?P<c>.+?)[\s.!]*$", re.I),
    re.compile(r"^(?P<s>.+?)'s (?:official )?currency is (?:the )?(?P<c>.+?)[\s.!]*$", re.I),
]
_HI_CURRENCY = re.compile(r"^(?P<s>.+?) की (?:आधिकारिक |राष्ट्रीय )?मुद्रा (?P<c>.+?) है$")


# --- current office -------------------------------------------------------------------

_ROLES_EN = ["prime minister", "president", "chief minister", "vice president", "governor"]
_EN_OFFICE = re.compile(rf"^(?P<p>.+?) is (?:currently )?the (?:current )?(?P<role>{'|'.join(_ROLES_EN)}) of "
                        rf"(?P<place>.+?)[\s.!]*$", re.I)
_ROLES_HI = "प्रधानमंत्री|प्रधान मंत्री|राष्ट्रपति|मुख्यमंत्री|उपराष्ट्रपति|राज्यपाल"
_HI_OFFICE = re.compile(rf"^(?P<pre>.+) (?:के|की) (?P<role>{_ROLES_HI}) (?:हैं|है)$")


def _ended(statement: dict) -> bool:
    return "P582" in (statement.get("qualifiers") or {})


def _current_office(person: str, office_text: str, language: str, linker, wd) -> TripleVerification:
    """Present tense: supported if a namesake holds the office now (a P39 statement without
    an end time); contradicted if the namesakes held it only in the past, or never and the
    office has a current holder on record."""
    office = linker.search_entity(office_text, language).qid
    people = (linker.search_places(person, language) or ())[:MAX_NAMESAKES]
    if not office or not people:
        return _unknown("P39", person)
    holders = [s for s in (wd.statements(office, "P1308") or []) if not _ended(s)]
    current = _ids(holders)
    former = False
    for p in people:
        held = [s for s in (wd.statements(p, "P39") or []) if _ids([s]) == [office]]
        if any(not _ended(s) for s in held) or p in current:
            return _result(office, "P1308", person, "supported", _shown(wd, current or [p], language))
        former = former or bool(held)
    if former or current:
        return _result(office, "P1308", person, "contradicted", _shown(wd, current, language))
    return _unknown("P39", person)


# --- quantities -------------------------------------------------------------------------

_APPROX = r"(?:(?:about|around|approximately|nearly|roughly|almost|over|more than|some|just over|just under) )?"
_N = r"(?P<n>\d[\d,]*(?:\.\d+)?)"
_MULT = r"(?: (?P<mult>million|billion|crore|lakh|thousand))?"
_HEIGHT_U = r"(?P<u>metres|meters|metre|meter|m|feet|foot|ft)"
_LEN_U = r"(?P<u>kilometres|kilometers|kilometre|kilometer|km|miles|mile|mi)"
_AREA_U = r"(?P<u>square kilometres|square kilometers|sq km|km2|km²|square miles|sq mi)"
_EN_QTY = [
    ("height", re.compile(rf"^(?P<s>.+?) (?:is|stands) {_APPROX}{_N} ?{_HEIGHT_U}\b (?:tall|high|in height)", re.I)),
    ("height", re.compile(rf"^the (?:height|elevation) of (?P<s>.+?) is {_APPROX}{_N} ?{_HEIGHT_U}\b", re.I)),
    ("height", re.compile(rf"^(?P<s>.+?) has (?:a height|an elevation) of {_APPROX}{_N} ?{_HEIGHT_U}\b", re.I)),
    ("length", re.compile(rf"^(?P<s>.+?) is {_APPROX}{_N} ?{_LEN_U}\b long", re.I)),
    ("length", re.compile(rf"^the length of (?P<s>.+?) is {_APPROX}{_N} ?{_LEN_U}\b", re.I)),
    ("population", re.compile(rf"^(?P<s>.+?) has a population of {_APPROX}{_N}{_MULT}\b", re.I)),
    ("population", re.compile(rf"^the population of (?P<s>.+?) is {_APPROX}{_N}{_MULT}\b", re.I)),
    ("area", re.compile(rf"^(?P<s>.+?) has (?:a|an) (?:total )?area of {_APPROX}{_N}{_MULT} ?{_AREA_U}", re.I)),
    ("area", re.compile(rf"^the (?:total )?area of (?P<s>.+?) is {_APPROX}{_N}{_MULT} ?{_AREA_U}", re.I)),
]
_HI_APPROX = r"(?:लगभग |करीब |क़रीब |तकरीबन )?"
_HI_MULT = r"(?: (?P<mult>करोड़|लाख|अरब|मिलियन|बिलियन|हज़ार|हजार))?"
_HI_QTY = [
    ("height", re.compile(rf"^(?P<s>.+?) की (?:ऊंचाई|ऊँचाई) {_HI_APPROX}{_N} (?P<u>मीटर|फीट|फ़ुट) है$")),
    ("length", re.compile(rf"^(?P<s>.+?) की (?:लंबाई|लम्बाई) {_HI_APPROX}{_N} (?P<u>किलोमीटर|किमी|मील) है$")),
    ("population", re.compile(rf"^(?P<s>.+?) की (?:जनसंख्या|आबादी) {_HI_APPROX}{_N}{_HI_MULT} है$")),
    ("area", re.compile(rf"^(?P<s>.+?) का क्षेत्रफल {_HI_APPROX}{_N}{_HI_MULT} (?P<u>वर्ग किलोमीटर|वर्ग किमी) है$")),
]
_MULTS = {"thousand": 1e3, "हज़ार": 1e3, "हजार": 1e3, "lakh": 1e5, "लाख": 1e5, "million": 1e6, "मिलियन": 1e6,
          "crore": 1e7, "करोड़": 1e7, "billion": 1e9, "बिलियन": 1e9, "अरब": 1e9}
# claim unit -> factor to the base unit (m, km, km2, people)
_UNIT = {"metres": 1, "meters": 1, "metre": 1, "meter": 1, "m": 1, "मीटर": 1, "feet": 0.3048, "foot": 0.3048,
         "ft": 0.3048, "फीट": 0.3048, "फ़ुट": 0.3048, "kilometres": 1, "kilometers": 1, "kilometre": 1,
         "kilometer": 1, "km": 1, "किलोमीटर": 1, "किमी": 1, "miles": 1.609344, "mile": 1.609344, "mi": 1.609344,
         "मील": 1.609344, "square kilometres": 1, "square kilometers": 1, "sq km": 1, "km2": 1, "km²": 1,
         "वर्ग किलोमीटर": 1, "वर्ग किमी": 1, "square miles": 2.589988, "sq mi": 2.589988}
# Wikidata unit item -> factor to the base unit
_WD_UNIT = {"Q11573": 1, "Q3710": 0.3048, "Q828224": 1, "Q253276": 1.609344, "Q712226": 1, "Q232291": 2.589988,
            "Q35852": 0.01, "1": 1}
_QTY_PIDS = {"height": ("P2044", "P2048"), "length": ("P2043",), "population": ("P1082",), "area": ("P2046",)}
_TOLERANCE = {"height": 0.03, "length": 0.10, "population": 0.10, "area": 0.05}
_BASE_NAME = {"height": "m", "length": "km", "population": "", "area": "km²"}


def _quantity(t: str, language: str):
    for kind, p in (_EN_QTY if language == "en" else _HI_QTY):
        if m := p.match(t):
            n = float(m["n"].replace(",", ""))
            d = m.groupdict()
            n *= _MULTS.get((d.get("mult") or "").lower(), 1)
            n *= _UNIT.get((d.get("u") or "").lower(), 1) if kind != "population" else 1
            return kind, _clean(m["s"]), n
    return None


def _stored_amounts(statements: list[dict], kind: str) -> list[float]:
    """The current value(s): preferred rank; else (population) the latest point in time;
    else all. Converted to the base unit; values in unknown units are skipped."""
    def amount(s):
        v = s.get("value")
        if not isinstance(v, dict) or "amount" not in v:
            return None
        unit = str(v.get("unit", "1")).rsplit("/", 1)[-1]
        return float(v["amount"]) * _WD_UNIT[unit] if unit in _WD_UNIT else None
    chosen = [s for s in statements if s.get("rank") == "preferred"]
    if not chosen and kind == "population":
        def when(s):
            q = (s.get("qualifiers") or {}).get("P585") or []
            return q[0].get("datavalue", {}).get("value", {}).get("time", "") if q else ""
        latest = max((when(s) for s in statements), default="")
        chosen = [s for s in statements if when(s) == latest]
    return [a for a in (amount(s) for s in (chosen or statements)) if a is not None]


def _fmt(x: float, kind: str) -> str:
    unit = _BASE_NAME[kind]
    value = f"{x:,.0f}" if x >= 100 else f"{x:,.2f}".rstrip("0").rstrip(".")
    return f"{value} {unit}".strip()


def _check_quantity(kind: str, subject: str, claimed: float, language: str, linker, wd) -> TripleVerification:
    tol = _TOLERANCE[kind]
    disagree = None
    for s in (linker.search_places(subject, language) or ())[:MAX_NAMESAKES]:
        for pid in _QTY_PIDS[kind]:
            amounts = _stored_amounts(wd.statements(s, pid) or [], kind)
            if not amounts:
                continue
            shown = [_fmt(a, kind) for a in amounts]
            if any(abs(claimed - a) <= tol * a for a in amounts):
                return _result(s, pid, str(claimed), "supported", shown)
            disagree = disagree or (s, pid, shown)
            break
    if disagree:
        s, pid, shown = disagree
        return _result(s, pid, str(claimed), "contradicted", shown)
    return _unknown(_QTY_PIDS[kind][0], str(claimed))


# --- entry point -------------------------------------------------------------------------

def check(claim_text: str, language: str, linker, wd) -> TripleVerification | None:
    t = " ".join(claim_text.translate(_DEV).split()).rstrip("।.!? ")
    if language == "hi":
        t = t.rstrip("।").strip()
    if (a := _authorship(t, language)) is not None:
        author, work = a
        return _named_value(work, author, "P50", language, linker, wd)
    cur = [_HI_CURRENCY] if language == "hi" else _EN_CURRENCY
    for p in cur:
        if m := p.match(t):
            return _named_value(_clean(m["s"]), _clean(m["c"]), "P38", language, linker, wd)
    if language == "en" and (m := _EN_OFFICE.match(t)):
        office = f"{m['role'].title()} of {m['place'].strip()}"  # "President of the United States"
        return _current_office(_clean(m["p"]), office, language, linker, wd)
    if language == "hi" and (m := _HI_OFFICE.match(t)):
        # "<person> <place> के/की <role> हैं": the place is the last one or two words before
        # के/की -- the split whose office exists is used. The office is named with "के" even
        # when the holder is a woman ("भारत की राष्ट्रपति").
        words = m["pre"].split()
        for k in (1, 2):
            if len(words) > k and linker.search_places(f"{' '.join(words[-k:])} के {m['role']}", "hi"):
                return _current_office(" ".join(words[:-k]), f"{' '.join(words[-k:])} के {m['role']}",
                                       language, linker, wd)
        return _unknown("P39", m["pre"])
    if (q := _quantity(t, language)) is not None:
        return _check_quantity(*q, language, linker, wd)
    if os.environ.get("SATYASCORE_KG_RELATIONS", "0") != "1":  # Version 2, on only after the dev check
        return None
    from member2_data import kg_relations  # nationality / origin, year of a work, director, cast, performer
    return kg_relations.check(t, language, linker, wd)
