"""DetectionPipeline._capital_by_name: a capital claim naming the city by part of its full name
("Delhi" for New Delhi) is supported, without any network call (stub Wikidata names)."""
from member2_data.entity_linker import LinkedTriple
from member2_data.wikidata_connector import TripleVerification
from member3_backend.pipeline import DetectionPipeline

NAMES = {"Q668": {"india", "भारत"}, "Q1353": {"delhi", "दिल्ली"}, "Q987": {"new delhi", "नई दिल्ली"},
         "Q1156": {"mumbai", "मुंबई"}, "Q96": {"mexico", "मेक्सिको"}, "Q1489": {"mexico city"}}


class StubWikidata:
    def names(self, ids, language="en"):
        return {i: NAMES.get(i, set()) for i in ids}


def check(subject, city, capital, status="contradicted"):
    p = DetectionPipeline.__new__(DetectionPipeline)
    p.wikidata = StubWikidata()
    linked = LinkedTriple(subject_qid=subject, property_pid="P36", object_qid=city, linkable=True, object_candidates=(city,))
    v = TripleVerification(subject_qid=subject, property_pid="P36", expected_value=city, found=status == "supported",
                           confidence=0.0 if status == "contradicted" else 1.0, used_fallback_label=False, source="live",
                           status=status, actual_values=(capital,))
    return p._capital_by_name(v, linked, "hi")


def test_part_of_the_capitals_name_is_supported():
    v = check("Q668", "Q1353", "Q987")  # भारत की राजधानी दिल्ली है (capital: नई दिल्ली)
    assert v.status == "supported" and v.confidence == 1.0


def test_a_different_city_stays_contradicted():
    assert check("Q668", "Q1156", "Q987").status == "contradicted"  # Mumbai


def test_the_countrys_own_name_is_not_support():
    assert check("Q96", "Q96", "Q1489").status == "contradicted"  # "Mexico" for Mexico City


def test_other_properties_and_statuses_are_untouched():
    assert check("Q668", "Q1353", "Q987", status="unknown").status == "unknown"
