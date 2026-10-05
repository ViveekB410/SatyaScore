"""Evidence aggregation rules (member3_backend/evidence_rules.py)."""
from member3_backend.evidence_rules import SubjectIndex, aggregate, aggregate_legacy, title_forms

CRICKET = "Cricket is a bat-and-ball sport played between two teams usually with 11 players per team."


def verdict(score):
    return "Hallucinated" if score < 0.35 else "Verified" if score > 0.65 else "Uncertain"


def test_the_reported_cricket_false_alarm_is_fixed():
    # measured live: passage 2 was a Hindi FOOTBALL passage with contradiction 0.934,
    # passage 3 a Cricket passage entailing the claim at 0.916
    rows = [(0.096, 0.008, True), (0.025, 0.934, False), (0.916, 0.033, True)]
    assert verdict(aggregate_legacy(rows)) == "Hallucinated"
    assert verdict(aggregate(rows)) == "Verified"


def test_an_off_topic_passage_cannot_contradict():
    # "The prime minister of Canada ..." against passages about India's prime minister
    assert verdict(aggregate([(0.006, 0.693, False), (0.003, 0.84, False)])) == "Uncertain"


def test_an_on_topic_contradiction_still_counts():
    # "The capital of Japan is Beijing." against the Japan article
    assert verdict(aggregate([(0.01, 0.95, True), (0.02, 0.10, False)])) == "Hallucinated"


def test_support_beats_any_contradiction_and_no_evidence_is_uncertain():
    assert verdict(aggregate([(0.95, 0.01, True), (0.01, 0.99, True)])) == "Verified"
    assert aggregate([]) == 0.5


def test_passages_are_matched_to_the_claim_by_article_title_in_both_languages():
    s = SubjectIndex({"Cricket": "क्रिकेट", "Association football": "फुटबॉल"})
    assert s.on_topic(CRICKET, "Cricket::en::3")
    assert not s.on_topic(CRICKET, "Association football::hi::5")
    assert s.on_topic("क्रिकेट एक खेल है।", "Cricket::hi::0")
    assert s.on_topic("Gandhi was born in Porbandar.", "wiki:en:Mahatma Gandhi::2")
    assert title_forms("Chief Minister (India)") == ["chief minister", "minister"]
    assert title_forms("Prime Minister of India") == ["prime minister of india", "india"]


def test_the_deciding_source_is_the_passage_the_rule_used():
    from member3_backend.evidence_rules import deciding
    cricket = [(0.08, 0.01, True, "Cricket::en::0"), (0.02, 0.94, False, "Association football::hi::4"),
               (0.92, 0.03, True, "Cricket::en::23")]
    assert deciding(cricket) == ("Cricket::en::23", "supports")
    assert deciding([(0.01, 0.95, True, "Japan::en::1")]) == ("Japan::en::1", "contradicts")
    assert deciding([(0.01, 0.95, False, "Paris::en::1")]) is None  # off-topic never decides
    assert deciding([]) is None


def test_sources_link_to_the_right_wikipedia():
    from member3_backend.evidence_rules import passage_source
    assert passage_source("wiki:en:Porbandar::3") == ("Porbandar", "en", "https://en.wikipedia.org/wiki/Porbandar")
    title, lang, url = passage_source("Cricket::hi::0", {"Cricket": "क्रिकेट"})
    assert (title, lang) == ("क्रिकेट", "hi") and url.startswith("https://hi.wikipedia.org/wiki/")
    assert passage_source("Cricket::hi::0", {})[1] == "en"  # no Hindi title known: English article

def test_strict_rule_only_on_topic_passages_verify():
    from member3_backend.evidence_rules import aggregate_strict, deciding
    # measured: "Viral infections tend to be more easily spread." Verified by a Hindi herpes passage
    off_topic_support = [(0.92, 0.01, False), (0.10, 0.05, True)]
    assert verdict(aggregate(off_topic_support)) == "Verified"
    assert verdict(aggregate_strict(off_topic_support)) == "Uncertain"
    # on-topic support still verifies (the cricket case), on-topic contradiction still contradicts
    assert verdict(aggregate_strict([(0.096, 0.008, True), (0.025, 0.934, False), (0.916, 0.033, True)])) == "Verified"
    assert verdict(aggregate_strict([(0.01, 0.95, True)])) == "Hallucinated"
    assert aggregate_strict([]) == 0.5 and aggregate_strict([(0.9, 0.0, False)]) == 0.5
    assert deciding([(0.9, 0.0, False, "off"), (0.2, 0.1, True, "on")], "strict") is None

def test_capped_rules_verify_only_with_a_supporting_passage():
    from member3_backend.evidence_rules import aggregate_capped, aggregate_capped_strong, deciding
    # measured: "Humans can breathe naturally underwater." best entailment 0.44, nothing on-topic -> 0.72
    weak = [(0.44, 0.18, False), (0.34, 0.29, False), (0.17, 0.49, False), (0.10, 0.76, False)]
    assert verdict(aggregate(weak)) == "Verified"
    assert verdict(aggregate_capped(weak)) == "Uncertain"
    # measured: "Human can breath naturally underwater." Scuba diving passage (off-topic) 0.79
    scuba = [(0.79, 0.01, False), (0.47, 0.14, False), (0.16, 0.51, False)]
    assert verdict(aggregate_capped(scuba)) == "Verified"
    assert verdict(aggregate_capped_strong(scuba)) == "Uncertain"
    assert deciding([(0.79, 0.01, False, "scuba")], "capped_strong") is None
    # strong off-topic support, on-topic support and on-topic contradiction are unchanged
    assert verdict(aggregate_capped_strong([(0.95, 0.01, False)])) == "Verified"
    assert verdict(aggregate_capped_strong([(0.096, 0.008, True), (0.025, 0.934, False), (0.916, 0.033, True)])) == "Verified"
    assert verdict(aggregate_capped_strong([(0.01, 0.95, True)])) == "Hallucinated"
