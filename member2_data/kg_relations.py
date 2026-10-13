"""
Version 2 knowledge-graph relations, chosen from the FEVER / Mu-SHROOM dev claims no source decided
(results/v2_data_PROTOCOL.md, "Wikidata relations"):

  nationality / origin / country   "X is an American actor", "X is a 2002 British film", "Janet Leigh was
                                   Canadian", "X comes from South Korea", "X is in the United States",
                                   "X एक भारतीय अभिनेता हैं", "X भारत में स्थित है"   (P27 / P495 / P17)
  year of a work                   "X is a 2002 film", "X was released in 1999"     (P577, P580, P571)
  director                         "X was directed by Y", "Y directed X"            (P57)
  cast member (support only)       "Y starred in X", "X stars Y"                    (P161)
  performer                        "X is a song by Y", "X was recorded by Y"        (P175)
  occupation (support only)        the "actor" in "X is an American actor"          (P106)

Safety rules (as for birthplaces, dates and authorship):
  * a claim is Verified only if EVERY fact word in it was checked and supported, by ONE namesake;
  * one fact that every namesake with a value contradicts is enough to make it Hallucinated;
  * negated or hedged claims ("not", "only", "at least" ...) and pronoun subjects are never decided;
  * anything unclear (lookup failed, no value on record) gives no decision: check() returns None and the
    general knowledge-graph path runs.
"""
from __future__ import annotations

import re

from member2_data.kg_extra import MAX_NAMESAKES, _clean, _ids, _result, _shown, name_matches

# Wikidata names that count as the country | English names | English demonyms | Hindi names | Hindi demonyms
_COUNTRIES = [
    (("United States of America", "United States"), ("United States of America", "United States", "U.S.A.", "U.S.",
                                                     "USA", "US", "America"), ("American",),
     ("संयुक्त राज्य अमेरिका", "अमेरिका"), ("अमेरिकी",)),
    (("United Kingdom", "Great Britain", "England", "Scotland", "Wales", "Northern Ireland"),
     ("United Kingdom", "U.K.", "UK", "Great Britain", "Britain"), ("British",), ("यूनाइटेड किंगडम", "ब्रिटेन"), ("ब्रिटिश",)),
    (("England", "United Kingdom", "Great Britain"), ("England",), ("English",), ("इंग्लैंड",), ()),
    (("Scotland", "United Kingdom", "Great Britain"), ("Scotland",), ("Scottish",), ("स्कॉटलैंड",), ()),
    (("Wales", "United Kingdom", "Great Britain"), ("Wales",), ("Welsh",), ("वेल्स",), ()),
    (("Ireland",), ("Ireland",), ("Irish",), ("आयरलैंड",), ("आयरिश",)),
    (("India", "British Raj"), ("India",), ("Indian",), ("भारत",), ("भारतीय",)),
    (("Pakistan", "British Raj"), ("Pakistan",), ("Pakistani",), ("पाकिस्तान",), ("पाकिस्तानी",)),
    (("Bangladesh", "British Raj"), ("Bangladesh",), ("Bangladeshi",), ("बांग्लादेश",), ("बांग्लादेशी",)),
    (("Nepal",), ("Nepal",), ("Nepali", "Nepalese"), ("नेपाल",), ("नेपाली",)),
    (("Sri Lanka", "Ceylon"), ("Sri Lanka",), ("Sri Lankan",), ("श्रीलंका",), ("श्रीलंकाई",)),
    (("Canada",), ("Canada",), ("Canadian",), ("कनाडा",), ("कनाडाई",)),
    (("Australia",), ("Australia",), ("Australian",), ("ऑस्ट्रेलिया", "आस्ट्रेलिया"), ("ऑस्ट्रेलियाई", "आस्ट्रेलियाई")),
    (("New Zealand",), ("New Zealand",), ("New Zealand",), ("न्यूज़ीलैंड", "न्यूजीलैंड"), ()),
    (("France",), ("France",), ("French",), ("फ़्रांस", "फ्रांस"), ("फ़्रांसीसी", "फ्रांसीसी")),
    (("Germany", "German Empire", "Prussia", "German Reich", "Weimar Republic"), ("Germany",), ("German",),
     ("जर्मनी",), ("जर्मन",)),
    (("Italy",), ("Italy",), ("Italian",), ("इटली",), ("इतालवी",)),
    (("Spain",), ("Spain",), ("Spanish",), ("स्पेन",), ("स्पेनिश", "स्पैनिश")),
    (("Portugal",), ("Portugal",), ("Portuguese",), ("पुर्तगाल",), ("पुर्तगाली",)),
    (("Netherlands",), ("Netherlands",), ("Dutch",), ("नीदरलैंड",), ("डच",)),
    (("Belgium",), ("Belgium",), ("Belgian",), ("बेल्जियम",), ()),
    (("Sweden",), ("Sweden",), ("Swedish",), ("स्वीडन",), ("स्वीडिश",)),
    (("Norway",), ("Norway",), ("Norwegian",), ("नॉर्वे",), ()),
    (("Denmark",), ("Denmark",), ("Danish",), ("डेनमार्क",), ()),
    (("Finland",), ("Finland",), ("Finnish",), ("फ़िनलैंड", "फिनलैंड"), ()),
    (("Poland",), ("Poland",), ("Polish",), ("पोलैंड",), ()),
    (("Austria",), ("Austria",), ("Austrian",), ("ऑस्ट्रिया",), ()),
    (("Switzerland",), ("Switzerland",), ("Swiss",), ("स्विट्ज़रलैंड", "स्विट्जरलैंड"), ()),
    (("Greece",), ("Greece",), ("Greek",), ("यूनान", "ग्रीस"), ("यूनानी",)),
    (("Russia", "Soviet Union", "Russian Empire", "Russian Soviet Federative Socialist Republic"), ("Russia",),
     ("Russian",), ("रूस",), ("रूसी",)),
    (("Ukraine", "Soviet Union", "Ukrainian Soviet Socialist Republic"), ("Ukraine",), ("Ukrainian",), ("यूक्रेन",), ()),
    (("China", "Qing dynasty"), ("China",), ("Chinese",), ("चीन",), ("चीनी",)),
    (("Japan",), ("Japan",), ("Japanese",), ("जापान",), ("जापानी",)),
    (("South Korea", "Korean Empire"), ("South Korea",), ("South Korean",), ("दक्षिण कोरिया",), ("दक्षिण कोरियाई",)),
    (("South Korea", "North Korea", "Korean Empire", "Joseon"), (), ("Korean",), (), ("कोरियाई",)),
    (("Mexico",), ("Mexico",), ("Mexican",), ("मेक्सिको", "मैक्सिको"), ("मैक्सिकन",)),
    (("Brazil",), ("Brazil",), ("Brazilian",), ("ब्राज़ील", "ब्राजील"), ("ब्राज़ीली",)),
    (("Argentina",), ("Argentina",), ("Argentine", "Argentinian"), ("अर्जेंटीना",), ()),
    (("South Africa",), ("South Africa",), ("South African",), ("दक्षिण अफ़्रीका", "दक्षिण अफ्रीका"), ("दक्षिण अफ़्रीकी",)),
    (("Nigeria",), ("Nigeria",), ("Nigerian",), ("नाइजीरिया",), ()),
    (("Egypt",), ("Egypt",), ("Egyptian",), ("मिस्र",), ("मिस्री",)),
    (("Israel",), ("Israel",), ("Israeli",), ("इज़राइल", "इसराइल", "इज़रायल"), ("इज़राइली",)),
    (("Iran",), ("Iran",), ("Iranian",), ("ईरान",), ("ईरानी",)),
    (("Turkey", "Ottoman Empire"), ("Turkey",), ("Turkish",), ("तुर्की",), ()),
    (("Philippines",), ("Philippines", "the Philippines"), ("Filipino", "Philippine"), ("फ़िलीपींस", "फिलीपींस"), ()),
    (("Indonesia",), ("Indonesia",), ("Indonesian",), ("इंडोनेशिया",), ()),
    (("Thailand",), ("Thailand",), ("Thai",), ("थाईलैंड",), ()),
]


def _lookup(field: int) -> dict[str, tuple]:
    return {w: e for e in _COUNTRIES for w in e[field]}


_EN_NAME, _EN_DEM, _HI_NAME, _HI_DEM = _lookup(1), _lookup(2), _lookup(3), _lookup(4)
_EN_ANY = {**_EN_NAME, **_EN_DEM}
_HI_ANY = {**_HI_NAME, **_HI_DEM}


def _alt(words) -> str:
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))


def _find_countries(text: str, table: dict[str, tuple]) -> tuple[list[tuple[str, tuple]], str]:
    """The country words in `text` (case-sensitive, whole words) and the text without them."""
    pat = re.compile(rf"(?<![\w.])(?:{_alt(table)})(?![\w])")
    found = [(m.group(0), table[m.group(0)]) for m in pat.finditer(text)]
    return found, pat.sub(" ", text)


# ------------------------------------------------------------------------------- kinds of subject
_OCC_EN = {  # head word -> occupation names that support it (English labels / aliases on Wikidata)
    "actor": ("actor",), "actress": ("actor", "actress"), "singer": ("singer",), "songwriter": ("songwriter",),
    "singer-songwriter": ("singer-songwriter", "singer"), "rapper": ("rapper",), "musician": ("musician",),
    "writer": ("writer", "novelist", "author", "screenwriter", "poet", "playwright"), "author": ("writer", "author", "novelist"),
    "novelist": ("novelist",), "poet": ("poet",), "playwright": ("playwright",), "screenwriter": ("screenwriter",),
    "director": ("film director", "director", "television director"), "film director": ("film director",),
    "filmmaker": ("film director", "filmmaker"), "producer": ("producer",), "film producer": ("film producer",),
    "record producer": ("record producer",), "politician": ("politician",), "journalist": ("journalist",),
    "comedian": ("comedian",), "model": ("model",), "dancer": ("dancer",), "footballer": ("association football player", "footballer"),
    "cricketer": ("cricketer",), "boxer": ("boxer",), "wrestler": ("wrestler",), "painter": ("painter",),
    "composer": ("composer",), "businessman": ("businessperson", "entrepreneur", "businessman"),
    "businesswoman": ("businessperson", "entrepreneur", "businesswoman"), "entrepreneur": ("entrepreneur", "businessperson"),
    "scientist": ("scientist",), "physicist": ("physicist",), "chemist": ("chemist",), "philosopher": ("philosopher",),
    "historian": ("historian",), "lawyer": ("lawyer",), "economist": ("economist",), "architect": ("architect",),
    "photographer": ("photographer",), "television presenter": ("television presenter",), "voice actor": ("voice actor",),
    "guitarist": ("guitarist",), "drummer": ("drummer",), "pianist": ("pianist",), "athlete": ("athlete",),
}
_WORK_EN = {  # head word -> description words that identify such an item
    "film": ("film", "movie"), "movie": ("film", "movie"), "documentary": ("documentary", "film"),
    "album": ("album",), "studio album": ("album",), "song": ("song", "single"), "single": ("single", "song"),
    "EP": ("ep", "extended play"), "novel": ("novel", "book"), "book": ("book", "novel"),
    "series": ("series", "sitcom", "programme", "program", "show", "serial"), "sitcom": ("sitcom", "series"),
    "miniseries": ("miniseries", "series"), "show": ("show", "series", "programme", "program"),
    "video game": ("video game", "game"), "musical": ("musical",), "play": ("play",), "anime": ("anime",),
    "manga": ("manga",), "telenovela": ("telenovela",), "opera": ("opera",), "soundtrack": ("soundtrack", "album"),
}
_ORG_EN = {
    "band": ("band", "group"), "group": ("group", "band"), "company": ("company", "business", "corporation"),
    "corporation": ("corporation", "company"), "station": ("station",), "channel": ("channel",), "network": ("network",),
    "newspaper": ("newspaper",), "magazine": ("magazine",), "airline": ("airline",), "university": ("university",),
    "team": ("team",), "club": ("club",), "party": ("party",), "studio": ("studio",), "record label": ("record label", "label"),
    "restaurant chain": ("restaurant",), "brand": ("brand",), "manufacturer": ("manufacturer", "company"),
    "publisher": ("publisher", "publishing"), "bank": ("bank",),
}
_KIND_PIDS = {"person": ("P27",), "work": ("P495", "P17"), "org": ("P17", "P495")}
_IGNORABLE_EN = {"former", "retired", "professional", "famous", "well-known", "popular", "noted", "renowned",
                 "prominent", "feature", "television", "TV"}

_OCC_HI = {
    "अभिनेता": ("अभिनेता", "actor"), "अभिनेत्री": ("अभिनेत्री", "actor", "actress"), "गायक": ("गायक", "singer"),
    "गायिका": ("गायिका", "singer"), "लेखक": ("लेखक", "writer", "novelist", "author"), "लेखिका": ("लेखिका", "writer", "novelist", "author"),
    "कवि": ("कवि", "poet"), "कवयित्री": ("कवयित्री", "poet"), "राजनेता": ("राजनेता", "politician"),
    "राजनीतिज्ञ": ("राजनीतिज्ञ", "politician"), "क्रिकेटर": ("क्रिकेटर", "cricketer"), "क्रिकेट खिलाड़ी": ("क्रिकेटर", "cricketer"),
    "फ़िल्म निर्देशक": ("फ़िल्म निर्देशक", "film director"), "फिल्म निर्देशक": ("फ़िल्म निर्देशक", "film director"),
    "निर्देशक": ("निर्देशक", "film director", "director"), "संगीतकार": ("संगीतकार", "composer", "musician"),
    "पत्रकार": ("पत्रकार", "journalist"), "उपन्यासकार": ("उपन्यासकार", "novelist"), "वैज्ञानिक": ("वैज्ञानिक", "scientist"),
    "उद्योगपति": ("उद्योगपति", "businessperson", "entrepreneur"), "व्यवसायी": ("व्यवसायी", "businessperson"),
    "चित्रकार": ("चित्रकार", "painter"), "नाटककार": ("नाटककार", "playwright"), "दार्शनिक": ("दार्शनिक", "philosopher"),
    "इतिहासकार": ("इतिहासकार", "historian"), "फ़ुटबॉल खिलाड़ी": ("association football player",),
    "फुटबॉल खिलाड़ी": ("association football player",), "मॉडल": ("मॉडल", "model"),
}
_WORK_HI = {"फ़िल्म": ("film",), "फिल्म": ("film",), "उपन्यास": ("novel",), "गीत": ("song",), "गाना": ("song",),
            "पुस्तक": ("book",), "धारावाहिक": ("series", "serial"), "टीवी धारावाहिक": ("series", "serial"), "एल्बम": ("album",)}
_ORG_HI = {"कंपनी": ("company",), "बैंड": ("band",), "राजनीतिक दल": ("party",), "समाचार पत्र": ("newspaper",),
           "अख़बार": ("newspaper",), "अखबार": ("newspaper",), "विश्वविद्यालय": ("university",)}
_IGNORABLE_HI = {"प्रसिद्ध", "मशहूर", "पूर्व", "लोकप्रिय", "प्रख्यात", "जाने-माने", "जानी-मानी", "जानेमाने", "सुप्रसिद्ध"}

_HEDGE_EN = re.compile(r"\b(?:not|never|only|no longer|n't|at least|at most|neither|nor|except|mistakenly|falsely|"
                       r"incorrectly|allegedly|reportedly|rumou?red|may|might|possibly|probably|perhaps|almost|nearly|"
                       r"also|sometimes|often|usually|mainly|mostly|partly|considered|regarded)\b", re.I)
_HEDGE_HI = re.compile(r"(?:नहीं|न तो|केवल|सिर्फ़|सिर्फ|शायद|संभवतः|संभवत|कभी|माना जाता|भी )")
_PRONOUNS_EN = {"it", "he", "she", "they", "this", "that", "these", "those", "his", "her", "its", "their", "there",
                "which", "who", "one", "some", "many", "all", "both", "each"}
_PRONOUNS_HI = {"यह", "वह", "ये", "वे", "इस", "उस", "इन", "उन", "इसका", "उसका", "इसकी", "उसकी", "जो"}


def _subject_ok(s: str, language: str) -> bool:
    words = s.split()
    if not words or len(words) > 8:
        return False
    if language == "en":
        return words[0].lower() not in _PRONOUNS_EN and (words[0][0].isupper() or words[0][0].isdigit())
    return words[0] not in _PRONOUNS_HI


# ------------------------------------------------------------------------------- facts
_FAIL = "fail"


def _search(linker, text: str, language: str, kinds: tuple[str, ...] = ()):
    """(namesake ids, kind_ok) for the subject, trying it as written and without a leading "the".
    None if the lookup failed or the linker cannot search named items."""
    search = getattr(linker, "search_named", None)
    if search is None:
        return None
    for cand in dict.fromkeys([text.strip(" ,\"'“”"), _clean(text)]):
        if not cand:
            continue
        got = search(cand, language, kinds)
        if got is None:
            return None
        ids, kind_ok = got
        if ids:
            return tuple(ids)[:MAX_NAMESAKES], kind_ok
    return (), False


def _country_fact(entry: tuple, pids: tuple[str, ...], language: str, wd):
    accepted = entry[0]

    def fact(s):
        for pid in pids:
            st = wd.statements(s, pid)
            if st is None:
                return _FAIL
            values = _ids(st)
            if not values:
                continue
            names = wd.names(values, "en")
            if not names:
                return _FAIL
            ok = any(name_matches(a, names.get(v, set())) for v in values for a in accepted)
            return ("supported" if ok else "contradicted"), pid, _shown(wd, values, language)
        return None
    return fact


def _years(statements: list[dict]) -> set[int]:
    out = set()
    for s in statements:
        v = s.get("value")
        if isinstance(v, dict) and isinstance(v.get("time"), str) and int(v.get("precision", 11)) >= 9:
            if m := re.match(r"\+(\d{4})-", v["time"]):
                out.add(int(m[1]))
    return out


def _make_year_fact(year: int, wd):
    def fact(s):
        for pid in ("P577", "P580", "P571"):
            st = wd.statements(s, pid)
            if st is None:
                return _FAIL
            ys = _years(st)
            if ys:
                return ("supported" if year in ys else "contradicted"), pid, [str(y) for y in sorted(ys)]
        return None
    return fact


def _occupation_fact(words: tuple[str, ...], language: str, wd):
    """Support only: Wikidata's occupation lists are incomplete, so a missing one contradicts nothing."""
    def fact(s):
        st = wd.statements(s, "P106")
        if st is None:
            return _FAIL
        values = _ids(st)
        if not values:
            return None
        names = wd.names(values, language)
        if not names:
            return _FAIL
        if any(name_matches(w, names.get(v, set())) for v in values for w in words):
            return "supported", "P106", _shown(wd, values, language)
        return None
    return fact


def _person_fact(pid: str, claimed: str, language: str, linker, wd, support_only: bool = False):
    """Is the person named `claimed` a `pid` value (director, cast member, performer) of the subject?
    Contradicted only if `claimed` is itself a known Wikidata item (and support_only is False)."""
    got = _search(linker, claimed, language)
    if got is None:
        return None
    claimed_items = set(got[0])

    def fact(s):
        st = wd.statements(s, pid)
        if st is None:
            return _FAIL
        values = _ids(st)
        if not values:
            return None
        names = wd.names(values, language)
        if not names:
            return _FAIL
        if claimed_items & set(values) or any(name_matches(claimed, names.get(v, set())) for v in values):
            return "supported", pid, _shown(wd, values, language)
        if support_only or not claimed_items:
            return None
        return "contradicted", pid, _shown(wd, values, language)
    return fact


def _decide(subjects: tuple[str, ...], facts: list, complete: bool, claimed: str, words: list[str] | None = None):
    """Contradicted if, for some fact, every namesake with a value contradicts it; supported if the claim
    is complete and one namesake supports every fact; else None (no decision)."""
    if not subjects or not facts or any(f is None for f in facts):
        return None
    table = {}
    for s in subjects:
        for i, f in enumerate(facts):
            r = f(s)
            if r == _FAIL:
                return None
            table[(s, i)] = r
    for i in range(len(facts)):
        vals = [(s, table[(s, i)]) for s in subjects if table[(s, i)]]
        if vals and all(r[0] == "contradicted" for _, r in vals):
            s, (_, pid, shown) = vals[0]  # the claimed word that is wrong (shown as the error)
            return _result(s, pid, words[i] if words else claimed, "contradicted", shown)
    if complete:
        for s in subjects:
            rs = [table[(s, i)] for i in range(len(facts))]
            if all(r and r[0] == "supported" for r in rs):
                return _result(s, rs[0][1], claimed, "supported", [x for r in rs for x in r[2]])
    return None


# ------------------------------------------------------------------------------- English patterns
def _heads(*tables) -> str:
    return _alt([w for t in tables for w in t])


_KIND_OF = {**{w: "person" for w in _OCC_EN}, **{w: "work" for w in _WORK_EN}, **{w: "org" for w in _ORG_EN}}
_DESC_OF = {**{w: (w,) + tuple(v) for w, v in _OCC_EN.items()}, **_WORK_EN, **_ORG_EN}
_EN_ISA = re.compile(rf"^(?P<s>.+?) (?:is|was) an? (?P<mods>(?:\S+ ){{0,6}})(?P<head>{_heads(_OCC_EN, _WORK_EN, _ORG_EN)})"
                     rf"(?P<tail>(?: .*)?)$")
_EN_DIRECTED_BY = re.compile(r"^(?P<w>.+?) (?:is|was) directed by (?P<p>.+)$")
_EN_DIRECTED = re.compile(r"^(?P<p>.+?) directed (?:the (?:film|movie|documentary) )?(?P<w>[A-Z0-9\"“].*)$")
_EN_STARRED_IN = re.compile(r"^(?P<p>.+?) (?:starred|stars|appeared|appears|acted|co-starred|costarred) in "
                            r"(?:the (?:\d{4} )?(?:film|movie|series|television series|TV series|show|sitcom) )?(?P<w>[A-Z0-9\"“].*)$")
_EN_STARS = re.compile(r"^(?P<w>.+?) (?:stars|starred|features|featured) (?P<p>[A-Z].*)$")
_EN_SONG_BY = re.compile(r"^(?P<w>.+?) (?:is|was) an? (?:(?P<y>\d{4}) )?(?:song|single|album|studio album|EP|record) "
                         r"(?:recorded |performed |released )?by (?P<p>.+)$")
_EN_RECORDED_BY = re.compile(r"^(?P<w>.+?) (?:is|was) (?:recorded|performed|sung) by (?P<p>.+)$")
_EN_RELEASED = re.compile(r"^(?P<s>.+?) (?:is|was) (?:first |originally )?(?:released|published|premiered|launched|"
                          r"broadcast|aired) in (?P<y>\d{4})$")
_EN_IN = re.compile(rf"^(?P<s>.+?) (?:is|was|lies) (?:located |situated |found |based )?in (?:the )?(?P<c>{_alt(_EN_NAME)})$")
_EN_FROM = re.compile(rf"^(?P<s>.+?) (?:is|was|comes|came|hails|originates|originated) from (?:the )?(?P<c>{_alt(_EN_NAME)})$")
_EN_BARE_DEM = re.compile(rf"^(?P<s>.+?) (?:is|was) (?P<c>{_alt(_EN_DEM)})$")
_FILMISH = ("film", "movie", "series", "documentary", "show", "sitcom", "episode")
_SONGISH = ("song", "single", "album", "ep", "extended play")


def _single_person(p: str) -> bool:
    return bool(p) and " and " not in p and "," not in p and len(p.split()) <= 5 and p[0].isupper()


def _english(t: str, linker, wd):
    if m := _EN_DIRECTED_BY.match(t) or _EN_DIRECTED.match(t):
        w, p = m["w"], _clean(m["p"])
        if not (_single_person(p) and _subject_ok(w, "en")):
            return None
        got = _search(linker, w, "en", _FILMISH)
        return got and _decide(got[0], [_person_fact("P57", p, "en", linker, wd)], got[1], p)
    if m := _EN_STARRED_IN.match(t) or _EN_STARS.match(t):
        w, p = m["w"], _clean(m["p"])
        if not (_single_person(p) and _subject_ok(w, "en")):
            return None
        got = _search(linker, w, "en", _FILMISH)
        return got and _decide(got[0], [_person_fact("P161", p, "en", linker, wd, support_only=True)], got[1], p)
    if m := _EN_SONG_BY.match(t) or _EN_RECORDED_BY.match(t):
        w, p = m["w"], _clean(m["p"])
        if not (_single_person(p) and _subject_ok(w, "en")):
            return None
        got = _search(linker, w, "en", _SONGISH)
        if not got:
            return None
        facts = [_person_fact("P175", p, "en", linker, wd)]
        if m.groupdict().get("y"):
            facts.append(_make_year_fact(int(m["y"]), wd))
        return _decide(got[0], facts, got[1], p)
    if m := _EN_RELEASED.match(t):
        if not _subject_ok(m["s"], "en"):
            return None
        got = _search(linker, m["s"], "en")
        return got and _decide(got[0], [_make_year_fact(int(m["y"]), wd)], True, m["y"])
    for pat, pids in ((_EN_IN, ("P17",)), (_EN_FROM, ("P27", "P495", "P17")), (_EN_BARE_DEM, ("P27", "P495", "P17"))):
        if m := pat.match(t):
            if not _subject_ok(m["s"], "en"):
                return None
            got = _search(linker, m["s"], "en")
            return got and _decide(got[0], [_country_fact(_EN_ANY[m["c"]], pids, "en", wd)], True, m["c"])
    if m := _EN_ISA.match(t):
        return _is_a(m["s"], m["mods"].strip(), m["head"], m["tail"].strip(), "en", linker, wd)
    return None


def _is_a(s: str, mods: str, head: str, tail: str, language: str, linker, wd):
    """'X is a/an <mods> <head>' / 'X एक <mods> <head> है': nationality / origin, a work's year, occupation."""
    if not _subject_ok(s, language):
        return None
    occ, work, org = (_OCC_EN, _WORK_EN, _ORG_EN) if language == "en" else (_OCC_HI, _WORK_HI, _ORG_HI)
    countries, rest = _find_countries(mods, _EN_ANY if language == "en" else _HI_ANY)
    words = rest.split()
    # "American film director": the last modifier and the head may form one occupation
    if language == "en" and words and f"{words[-1]} {head}" in occ:
        head, words = f"{words[-1]} {head}", words[:-1]
    kind = "person" if head in occ else "work" if head in work else "org"
    years = [w for w in words if re.fullmatch(r"\d{4}", w)] if kind == "work" else []
    ignorable = _IGNORABLE_EN if language == "en" else _IGNORABLE_HI
    leftover = [w for w in words if w not in years and w not in ignorable]
    kinds = (head,) + tuple(occ[head]) if kind == "person" else (work if kind == "work" else org)[head]
    if language == "hi":
        kinds = tuple(k for k in kinds if k.isascii())  # descriptions are searched in the claim language too
    facts = [_country_fact(e, _KIND_PIDS[kind], language, wd) for _, e in countries]
    facts += [_make_year_fact(int(y), wd) for y in years]
    if kind == "person":
        facts.append(_occupation_fact(occ[head], language, wd))
    if not countries and not years and kind != "person":
        return None
    got = _search(linker, s, language, kinds)
    if not got:
        return None
    complete = not leftover and not tail and (kind == "person" or got[1])
    words = [c for c, _ in countries] + years + ([head] if kind == "person" else [])
    return _decide(got[0], facts, complete, " ".join(words + ([] if kind == "person" else [head])), words)


# ------------------------------------------------------------------------------- Hindi patterns
_HI_END = r"(?:है|हैं|था|थी|थे)"
_HI_IN = re.compile(rf"^(?P<s>.+?) (?P<c>{_alt(_HI_NAME)}) (?:में|मे) (?:स्थित )?{_HI_END}$")
_HI_ISA = re.compile(rf"^(?P<s>.+?) (?:(?P<y>\d{{4}}) (?:की|का|में बनी|में रिलीज़ हुई) )?एक (?P<mods>(?:\S+ ){{0,5}})"
                     rf"(?P<head>{_heads(_OCC_HI, _WORK_HI, _ORG_HI)}) {_HI_END}$")


def _hindi(t: str, linker, wd):
    if m := _HI_IN.match(t):
        if not _subject_ok(m["s"], "hi"):
            return None
        got = _search(linker, m["s"], "hi")
        return got and _decide(got[0], [_country_fact(_HI_ANY[m["c"]], ("P17",), "hi", wd)], True, m["c"])
    if m := _HI_ISA.match(t):
        mods = m["mods"].strip()
        if m["y"]:
            mods = f"{m['y']} {mods}"
        return _is_a(m["s"], mods, m["head"], "", "hi", linker, wd)
    return None


# Dropped by the keep-or-drop rule on the dev sets (results/v2_kg_relations_dev.md): "country" (P17) was
# 4/5 correct (< 90%). Its one wrong decision was FEVER's "Tijuana is in Mexico." labelled false; the rule
# was applied as written anyway.
DROPPED_PIDS = {"P17"}


def check(t: str, language: str, linker, wd):
    """t: the claim, normalised by kg_extra.check (digits, final punctuation). A TripleVerification
    (supported / contradicted) or None (no decision: the general path runs)."""
    if language == "en":
        r = None if _HEDGE_EN.search(t) else _english(t, linker, wd)
    elif language == "hi":
        r = None if _HEDGE_HI.search(t + " ") else _hindi(t, linker, wd)
    else:
        r = None
    return r if r and r.property_pid not in DROPPED_PIDS else None
