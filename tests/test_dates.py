"""Dates in claims are checked against Wikidata's date properties, never as places
(member2_data/dates.py). Before: "Mahatma Gandhi was born in 1869" -> Hallucinated
(the year was linked as a birthplace: Wikidata's item for the year 1869). No network."""
from types import SimpleNamespace
from unittest.mock import MagicMock

from member2_data.dates import DATE_PID, format_date, matches, parse_date, wikidata_time
from member2_data.entity_linker import EntityLinker, hindi_date_claim
from member2_data.wikidata_connector import TripleVerification, WikidataConnector
from member3_backend.pipeline import DetectionPipeline

G = "http://www.wikidata.org/entity/Q1985727"  # Gregorian
J = "http://www.wikidata.org/entity/Q1985786"  # Julian


def test_dates_are_read_in_english_and_hindi_and_places_are_not_dates():
    assert parse_date("1869") == (1869, None, None)
    assert parse_date("2 October 1869") == parse_date("October 2, 1869") == (1869, 10, 2)
    assert parse_date("the 2nd of October, 1869") == (1869, 10, 2)
    assert parse_date("2 अक्टूबर 1869") == (1869, 10, 2) and parse_date("1869 को") == (1869, None, None)
    for not_a_date in ("Porbandar", "New Delhi", "October", "2 October", "50", "Mumbai in 1869"):
        assert parse_date(not_a_date) is None, not_a_date
    assert DATE_PID == {"P19": "P569", "P20": "P570", "P571": "P571"}


def test_dates_are_compared_only_as_precisely_as_both_give_them():
    gandhi = wikidata_time({"time": "+1869-10-02T00:00:00Z", "precision": 11, "calendarmodel": G})
    assert matches((1869, None, None), gandhi) and matches((1869, 10, None), gandhi)
    assert matches((1869, 10, 2), gandhi)
    assert matches((1872, None, None), gandhi) is False and matches((1869, 10, 12), gandhi) is False
    year_only = wikidata_time({"time": "+1890-00-00T00:00:00Z", "precision": 9, "calendarmodel": G})
    assert matches((1890, 4, 23), year_only)  # the day cannot be contradicted by a year-only record
    newton = wikidata_time({"time": "+1642-12-25T00:00:00Z", "precision": 11, "calendarmodel": J})
    assert matches((1643, None, None), newton) is None  # Julian 1642 = Gregorian 1643: cannot tell
    assert matches((1700, None, None), newton) is False
    assert wikidata_time({"time": "+1800-00-00T00:00:00Z", "precision": 7}) is None  # century: too coarse
    assert format_date(gandhi) == "2 October 1869" and format_date(gandhi, "hi") == "2 अक्टूबर 1869"


def test_a_year_is_never_linked_as_a_place():
    session = MagicMock()
    session.get.return_value = SimpleNamespace(
        status_code=200, raise_for_status=lambda: None,
        json=lambda: {"search": [{"id": "Q202810", "match": {"text": "1869"}, "description": "year"}]})
    assert EntityLinker(session=session).search_places("1869") == ()
    session.get.assert_not_called()


def test_hindi_date_claims():
    assert hindi_date_claim("महात्मा गांधी का जन्म 1869 में हुआ था।") == ("महात्मा गांधी", (1869, None, None), "P569")
    assert hindi_date_claim("महात्मा गांधी का जन्म 2 अक्टूबर 1869 को हुआ था।")[1] == (1869, 10, 2)
    assert hindi_date_claim("जवाहरलाल नेहरू का निधन 1964 में हुआ था।")[2] == "P570"
    assert hindi_date_claim("महात्मा गांधी का जन्म पोरबंदर में हुआ था।") is None  # a place


def _connector(dates_by_qid):
    wd = WikidataConnector(session=MagicMock())
    wd._date_values = lambda qid, pid: [wikidata_time(t) for t in dates_by_qid.get(qid, [])]
    return wd


def test_verify_date_supported_contradicted_unknown():
    wd = _connector({"Q1001": [{"time": "+1869-10-02T00:00:00Z", "precision": 11, "calendarmodel": G}]})
    assert wd.verify_date("Q1001", "P569", (1869, None, None)).status == "supported"
    v = wd.verify_date("Q1001", "P569", (1872, None, None))
    assert (v.status, v.confidence, v.actual_text) == ("contradicted", 0.0, ("2 October 1869",))
    assert wd.verify_date("Q9", "P569", (1872, None, None)).status == "unknown"  # no date on record


def test_namesakes_any_match_supports_and_only_all_dated_disagreeing_contradicts():
    p = DetectionPipeline.__new__(DetectionPipeline)
    p.entity_linker = MagicMock()
    p.entity_linker.search_places.return_value = ("Q_player", "Q_scientist", "Q_statue")
    p.wikidata = _connector({"Q_player": [{"time": "+1963-02-17T00:00:00Z", "precision": 11, "calendarmodel": G}],
                             "Q_scientist": [{"time": "+1956-02-25T00:00:00Z", "precision": 11, "calendarmodel": G}]})
    assert p._date_lookup("Michael Jordan", "P569", (1956, None, None), "en")[0] == 1.0  # the scientist
    assert p._date_lookup("Michael Jordan", "P569", (1970, None, None), "en")[0] == 0.0  # nobody: the statue has no date
    p.entity_linker.search_places.return_value = ()
    assert p._date_lookup("Nobody Known", "P569", (1970, None, None), "en") == (None, None)


def test_the_correct_fact_shows_the_recorded_date():
    p = DetectionPipeline.__new__(DetectionPipeline)
    p.wikidata = MagicMock()
    p.wikidata.labels.return_value = {"Q1001": "Mahatma Gandhi", "P569": "date of birth"}
    v = TripleVerification("Q1001", "P569", "1872", False, 0.0, False, "live", "contradicted",
                           actual_text=("2 October 1869",))
    assert p._kg_fact(v, "en")["values"] == ["2 October 1869"]
