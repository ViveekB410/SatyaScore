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
