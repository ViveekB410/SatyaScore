"""
Dates in claims ("1869", "October 1869", "2 October 1869", "October 2, 1869",
"2 अक्टूबर 1869") and on Wikidata, compared only as precisely as both state.

Why: "born in" / "died in" / "founded in" are followed by a PLACE or a DATE. A year
read as a place found Wikidata's item for the year itself ("1869"), and true claims
("Mahatma Gandhi was born in 1869") were contradicted. Dates are now checked against
the date properties: date of birth (P569), date of death (P570), inception (P571).
"""
from __future__ import annotations

import re

# relation (place / founding) -> the date property used when its object is a date
DATE_PID = {"P19": "P569", "P20": "P570", "P571": "P571"}

_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4,
    "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9,
    "sep": 9, "sept": 9, "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
    "जनवरी": 1, "फरवरी": 2, "फ़रवरी": 2, "मार्च": 3, "अप्रैल": 4, "अप्रेल": 4, "मई": 5, "जून": 6,
    "जुलाई": 7, "अगस्त": 8, "सितंबर": 9, "सितम्बर": 9, "अक्टूबर": 10, "अक्तूबर": 10,
    "नवंबर": 11, "नवम्बर": 11, "दिसंबर": 12, "दिसम्बर": 12,
}
_MONTH_NAMES = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September",
           "October", "November", "December"],
    "hi": ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर",
           "नवंबर", "दिसंबर"],
}
# words allowed around a date: "the 2nd of October, 1869", "सन 1869", "1869 को"
_FILLER = {"the", "of", "on", "in", "year", "सन", "वर्ष", "को", "में", "ई", "ई."}
_TOKEN = re.compile(r"[^\s,.]+")

GREGORIAN = "http://www.wikidata.org/entity/Q1985727"
GREGORIAN_FROM = 1583  # before this, Julian/Gregorian conversions shift days and even years


def parse_date(text: str) -> tuple[int, int | None, int | None] | None:
    """(year, month, day) if `text` is a date and nothing else; None otherwise
    (a place, a number that is not a year, a month without a year)."""
    year = month = day = None
    for tok in _TOKEN.findall(text.strip().casefold()):
        tok = tok.rstrip(".")
        if tok in _FILLER:
            continue
        if tok in _MONTHS and month is None:
            month = _MONTHS[tok]
        elif re.fullmatch(r"\d{3,4}", tok) and year is None and 100 <= int(tok) <= 2100:
            year = int(tok)
        elif (m := re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?", tok)) and day is None and 1 <= int(m[1]) <= 31:
            day = int(m[1])
        else:
            return None
    if year is None or (day is not None and month is None):
        return None
    return year, month, day


def wikidata_time(value: dict) -> tuple[int, int | None, int | None, bool] | None:
    """A Wikidata time value -> (year, month, day, gregorian), to its precision
    (9 = year, 10 = month, 11 = day). None for BCE dates or coarser than a year."""
    m = re.fullmatch(r"\+(\d{1,4})-(\d{2})-(\d{2})T.*", value.get("time", ""))
    precision = value.get("precision", 0)
    if not m or precision < 9:
        return None
    y, mo, d = int(m[1]), int(m[2]), int(m[3])
    return (y, mo if precision >= 10 and mo else None, d if precision >= 11 and d else None,
            value.get("calendarmodel") == GREGORIAN)


def matches(claim: tuple, stored: tuple) -> bool | None:
    """Does a claimed (year, month, day) agree with a stored Wikidata date? Compared
    only where both give a part. None = cannot tell (an early, non-Gregorian date
    whose day or month could shift between calendars)."""
    cy, cm, cd = claim
    sy, sm, sd, gregorian = stored
    if sy < GREGORIAN_FROM or not gregorian:
        if abs(cy - sy) > 1:
            return False
        return True if cy == sy and cm is None else None
    if cy != sy:
        return False
    if cm is not None and sm is not None and cm != sm:
        return False
    if cd is not None and sd is not None and cd != sd:
        return False
    return True


def format_date(stored: tuple, language: str = "en") -> str:
    y, m, d, _ = stored
    names = _MONTH_NAMES["hi" if language == "hi" else "en"]
    return " ".join(str(x) for x in (d, names[m - 1] if m else None, y) if x)
