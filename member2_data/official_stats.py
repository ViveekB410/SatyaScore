"""
Official statistics: World Bank Open Data and the WHO Global Health Observatory.

For country statistics chatbots often get wrong, the claim is checked against the official
figure (the most recent year on record):

  population        World Bank SP.POP.TOTL           tolerance 10 %
  GDP (current US$) World Bank NY.GDP.MKTP.CD        tolerance 15 %
  life expectancy   World Bank SP.DYN.LE00.IN + WHO WHOSIS_000001   +/- 3 years
  literacy rate     World Bank SE.ADT.LITR.ZS        +/- 5 points
  infant mortality  World Bank SP.DYN.IMRT.IN + WHO MDG_0000000001  tolerance 20 %

in English and Hindi ("Life expectancy in Japan is 84 years", "भारत में जीवन प्रत्याशा
लगभग 72 वर्ष है").

Reliability rules: the country is identified by its ISO 3166 code on Wikidata (P298), found
by exact name, so only real countries are checked; where TWO official sources have a figure,
both must agree for a verdict (if they disagree, no signal); a failed lookup gives no signal.
Population of a non-country (a city) is left to Wikidata (member2_data/kg_extra.py).

check(claim, language, linker, wd) -> TripleVerification | None (None: no pattern applies).
"""
from __future__ import annotations

import re

import requests

from member2_data._http import polite_get
from member2_data.kg_extra import _APPROX, _DEV, _HI_APPROX, _MULTS, _N, _clean, _quantity
from member2_data.wikidata_connector import TripleVerification

WB = "https://api.worldbank.org/v2/country/{iso}/indicator/{ind}"
WHO = "https://ghoapi.azureedge.net/api/{code}"
MAX_NAMESAKES = 5

KINDS = {
    # kind: (world bank indicator, WHO code or None, tolerance, absolute?, unit shown, property shown)
    "population": ("SP.POP.TOTL", None, 0.10, False, "", "population"),
    "gdp": ("NY.GDP.MKTP.CD", None, 0.15, False, "US$", "GDP (current US$)"),
    "life": ("SP.DYN.LE00.IN", "WHOSIS_000001", 3.0, True, "years", "life expectancy"),
    "literacy": ("SE.ADT.LITR.ZS", None, 5.0, True, "%", "adult literacy rate"),
    "infant": ("SP.DYN.IMRT.IN", "MDG_0000000001", 0.20, False, "per 1,000 live births", "infant mortality rate"),
}
_HI_PROPERTY = {"population": "जनसंख्या", "gdp": "सकल घरेलू उत्पाद (US$)", "life": "जीवन प्रत्याशा",
                "literacy": "वयस्क साक्षरता दर", "infant": "शिशु मृत्यु दर (प्रति 1,000 जीवित जन्म)"}

_PCT = r" ?(?:%|percent|per cent)"
_MONEY_MULT = r"(?P<mult>trillion|billion|million)"
_EN = [
    ("life", re.compile(rf"^(?:the )?(?:average )?life expectancy (?:at birth )?(?:in|of|for) (?P<s>.+?) is {_APPROX}{_N}(?: years)?$", re.I)),
    ("life", re.compile(rf"^(?P<s>.+?) has (?:an? )?(?:average )?life expectancy of {_APPROX}{_N}(?: years)?$", re.I)),
    ("literacy", re.compile(rf"^(?:the )?(?:adult )?literacy rate (?:in|of) (?P<s>.+?) is {_APPROX}{_N}{_PCT}$", re.I)),
    ("literacy", re.compile(rf"^(?P<s>.+?) has (?:an? )?(?:adult )?literacy rate of {_APPROX}{_N}{_PCT}$", re.I)),
    ("gdp", re.compile(rf"^(?:the )?(?:nominal )?gdp of (?P<s>.+?) is {_APPROX}(?:us)?\$ ?{_N} ?{_MONEY_MULT}(?: us)?(?: dollars)?$", re.I)),
    ("gdp", re.compile(rf"^(?P<s>.+?)'s (?:nominal )?gdp is {_APPROX}(?:us)?\$ ?{_N} ?{_MONEY_MULT}(?: us)?(?: dollars)?$", re.I)),
    ("gdp", re.compile(rf"^(?P<s>.+?) has a (?:nominal )?gdp of {_APPROX}(?:us)?\$ ?{_N} ?{_MONEY_MULT}(?: us)?(?: dollars)?$", re.I)),
    ("infant", re.compile(rf"^(?:the )?infant mortality rate (?:in|of) (?P<s>.+?) is {_APPROX}{_N}(?: deaths)?(?: per 1,?000 live births)?$", re.I)),
]
_HI = [
    ("life", re.compile(rf"^(?P<s>.+?) में (?:औसत )?जीवन प्रत्याशा {_HI_APPROX}{_N} (?:वर्ष|साल) है$")),
    ("literacy", re.compile(rf"^(?P<s>.+?) की (?:वयस्क )?साक्षरता दर {_HI_APPROX}{_N} ?(?:%|प्रतिशत) है$")),
    ("gdp", re.compile(rf"^(?P<s>.+?) (?:की जीडीपी|का सकल घरेलू उत्पाद(?: \(जीडीपी\))?) {_HI_APPROX}{_N} (?P<mult>ट्रिलियन|अरब|बिलियन) (?:अमेरिकी )?डॉलर है$")),
    ("infant", re.compile(rf"^(?P<s>.+?) में शिशु मृत्यु दर {_HI_APPROX}{_N}(?: प्रति (?:1,?000|हजार|हज़ार) जीवित जन्म)? है$")),
]
_MONEY = {"trillion": 1e12, "ट्रिलियन": 1e12, "billion": 1e9, "बिलियन": 1e9, "अरब": 1e9, "million": 1e6}

_cache: dict[tuple, object] = {}


def parse(t: str, language: str) -> tuple[str, str, float, float] | None:
    """(kind, country text, claimed value, half a unit of its last written digit) or None.
    "about $0.1 billion" is written to 0.1 billion, so it means 0.05-0.15 billion."""
    for kind, p in (_EN if language == "en" else _HI):
        if m := p.match(t):
            raw = m["n"].replace(",", "")
            n = float(raw)
            half = 0.5 * 10 ** -(len(raw.split(".")[1]) if "." in raw else 0)
            if kind == "gdp":
                n *= _MONEY[m["mult"].lower()]
                half *= _MONEY[m["mult"].lower()]
            return kind, _clean(m["s"]), n, half
    q = _quantity(t, language)  # population, same patterns as the Wikidata check
    if q and q[0] == "population":
        return "population", q[1], q[2], 0.0
    return None


CACHE_DIR = None  # a folder to keep World Bank / WHO answers on disk (set by the evaluation)


def _get_json(session, url: str, params: dict, attempts: int = 3):
    """Cached GET; the World Bank API is sometimes slow, so a timeout is retried."""
    key = (url, tuple(sorted(params.items())))
    if key not in _cache and CACHE_DIR is not None:
        import hashlib
        import json
        from pathlib import Path
        f = Path(CACHE_DIR) / (hashlib.sha1(repr(key).encode()).hexdigest()[:20] + ".json")
        if f.exists():
            _cache[key] = json.loads(f.read_text(encoding="utf-8"))
        else:
            for i in range(attempts):
                try:
                    _cache[key] = polite_get(session, url, params=params, timeout=30).json()
                    break
                except requests.exceptions.Timeout:
                    if i == attempts - 1:
                        raise
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(_cache[key]), encoding="utf-8")
    if key not in _cache:
        for i in range(attempts):
            try:
                _cache[key] = polite_get(session, url, params=params, timeout=30).json()
                break
            except requests.exceptions.Timeout:
                if i == attempts - 1:
                    raise
    return _cache[key]


def country_iso3(name: str, language: str, linker, wd) -> tuple[str, str] | None:
    """(ISO3, Wikidata id) of the country named exactly `name`, or None."""
    for q in (linker.search_places(name, language) or ())[:MAX_NAMESAKES]:
        codes = [s["value"] for s in (wd.statements(q, "P298") or []) if isinstance(s.get("value"), str)]
        if codes:
            return codes[0].upper(), q
    return None


def world_bank(session, iso3: str, indicator: str) -> tuple[int, float, str] | None:
    """(year, value, ISO2) of the most recent non-empty value, or None."""
    data = _get_json(session, WB.format(iso=iso3, ind=indicator), {"format": "json", "mrnev": 1})
    rows = data[1] if isinstance(data, list) and len(data) > 1 and data[1] else []
    for r in rows:
        if r.get("value") is not None:
            return int(r["date"]), float(r["value"]), (r.get("country") or {}).get("id", "")
    return None


def who(session, iso3: str, code: str) -> tuple[int, float] | None:
    """(year, value) of the most recent both-sexes value, or None."""
    data = _get_json(session, WHO.format(code=code),
                     {"$filter": f"SpatialDim eq '{iso3}' and Dim1 eq 'SEX_BTSX'"})
    rows = [r for r in data.get("value", []) if r.get("NumericValue") is not None]
    if not rows:
        return None
    r = max(rows, key=lambda x: x.get("TimeDim") or 0)
    return int(r["TimeDim"]), float(r["NumericValue"])


def _agrees(claimed: float, official: float, tol: float, absolute: bool, half: float = 0.0) -> bool:
    """Within the tolerance, or within the precision the claim is written to (a rounded
    figure: "$0.1 billion" for 0.066 billion)."""
    return abs(claimed - official) <= max(tol if absolute else tol * official, half)


def _fmt(kind: str, x: float) -> str:
    if kind == "population":
        return f"{x:,.0f}"
    if kind == "gdp":
        return f"US$ {x / 1e12:,.2f} trillion" if x >= 1e12 else f"US$ {x / 1e9:,.1f} billion"
    if kind == "literacy":
        return f"{x:.1f}%"
    return f"{x:.1f} {KINDS[kind][4]}"


def check(claim_text: str, language: str, linker, wd, session=None) -> TripleVerification | None:
    t = " ".join(claim_text.translate(_DEV).split()).rstrip("।.!? ")
    parsed = parse(t, language)
    if parsed is None:
        return None
    kind, country, claimed, half = parsed
    ind, who_code, tol, absolute, _, prop = KINDS[kind]
    found = country_iso3(country, language, linker, wd)
    if found is None:
        # not a country: population goes to the Wikidata check, other kinds give no signal
        return None if kind == "population" else _unknown(kind, claimed)
    iso3, qid = found
    session = session or requests.Session()
    figures = []  # (authority, year, value, url)
    try:
        if (wb := world_bank(session, iso3, ind)) is not None:
            year, value, iso2 = wb
            figures.append(("World Bank", year, value,
                            f"https://data.worldbank.org/indicator/{ind}?locations={iso2 or iso3}"))
        if who_code and (w := who(session, iso3, who_code)) is not None:
            figures.append(("WHO", w[0], w[1], "https://www.who.int/data/gho"))
    except Exception:
        return _unknown(kind, claimed)
    if not figures:
        return _unknown(kind, claimed)
    votes = {_agrees(claimed, v, tol, absolute, half) for _, _, v, _ in figures}
    if len(votes) > 1:  # the official sources disagree about this claim: no verdict
        return _unknown(kind, claimed)
    status = "supported" if votes == {True} else "contradicted"
    names = wd.labels([qid], language)
    authority = ", ".join(dict.fromkeys(a for a, _, _, _ in figures))
    years = "; ".join(f"{a} {y}" for a, y, _, _ in figures)
    shown = [f"{_fmt(kind, v)} ({a} {y})" for a, y, v, _ in figures]
    v = TripleVerification(subject_qid=qid, property_pid=ind, expected_value=str(claimed), found=status == "supported",
                           confidence=1.0 if status == "supported" else 0.0, used_fallback_label=False,
                           source="live", status=status, actual_text=tuple(shown))
    v.display = {"subject": names.get(qid, country),
                 "property": (_HI_PROPERTY[kind] if language == "hi" else prop) + f" ({years})",
                 "url": figures[0][3], "authority": authority}
    return v


def _unknown(kind: str, claimed: float) -> TripleVerification:
    return TripleVerification(subject_qid="", property_pid=KINDS[kind][0], expected_value=str(claimed), found=False,
                              confidence=None, used_fallback_label=False, source="live", status="unknown")
