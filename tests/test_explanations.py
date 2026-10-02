"""Explanations shown with each verdict (no verdict changes): the evidence sentence
of the deciding passage, and the fact Wikidata holds. No network."""
from types import SimpleNamespace
from unittest.mock import MagicMock

from member1_model.cmhsa import KG_NOTE
from member2_data.wikidata_connector import TripleVerification, WikidataConnector
from member3_backend.factcheck_rules import FC_NOTE_PREFIX
from member3_backend.pipeline import DetectionPipeline, _decided_elsewhere

CRICKET = "Cricket is a bat-and-ball sport played between two teams usually with 11 players per team."
PASSAGE = ("Cricket is popular in South Asia. It is played on a field with a pitch at the centre. "
           "Each team has eleven players and the game is played with a bat and a ball.")


class KeywordNLI:
    """Entails when the premise mentions 'eleven players'; contradicts when it mentions 'nine'."""
    def score_batch(self, claim_ids, premises, hypotheses):
        return [SimpleNamespace(entailment_prob=0.9 if "eleven players" in p else 0.05,
                                contradiction_prob=0.9 if "nine" in p else 0.05) for p in premises]


def pipe():
    p = DetectionPipeline.__new__(DetectionPipeline)
    p.nli_scorer = KeywordNLI()
    return p


def test_excerpt_is_the_sentence_that_supports_the_claim():
    pc = {"deciding": ("Cricket::en::0", "supports"), "passage_ids": ["Cricket::en::0"], "passages": [PASSAGE]}
    [ex] = pipe()._excerpts([CRICKET], [pc])
    assert ex == "Each team has eleven players and the game is played with a bat and a ball."


def test_excerpt_for_a_contradiction_and_none_without_a_deciding_passage():
    text = "Cricket teams are large. A cricket team has nine players on the field. Matches can last days."
    pc = {"deciding": ("Cricket::en::1", "contradicts"), "passage_ids": ["Cricket::en::1"], "passages": [text]}
    no = {"deciding": None, "passage_ids": ["Cricket::en::1"], "passages": [text]}
    assert pipe()._excerpts([CRICKET, CRICKET], [pc, no]) == ["A cricket team has nine players on the field.", None]


def test_only_nli_decided_claims_get_a_passage_excerpt():
    assert _decided_elsewhere(KG_NOTE) and _decided_elsewhere(f"{FC_NOTE_PREFIX} Factly: rated \"False\"")
    assert _decided_elsewhere("judged by LLM (x) from the retrieved passages")
    assert not _decided_elsewhere(None) and not _decided_elsewhere("insufficient evidence: no passage")


def test_kg_fact_names_the_value_wikidata_holds():
    p = pipe()
    p.wikidata = MagicMock()
    p.wikidata.labels.return_value = {"Q1001": "Mahatma Gandhi", "P19": "place of birth", "Q200017": "Porbandar"}
    v = TripleVerification("Q1001", "P19", "Q987", False, 0.0, False, "live", "contradicted", ("Q200017",))
    assert p._kg_fact(v, "en") == {"subject": "Mahatma Gandhi", "property": "place of birth", "values": ["Porbandar"],
                                   "status": "contradicted", "url": "https://www.wikidata.org/wiki/Q1001"}
    p.wikidata.labels.return_value = {}  # names unavailable (offline): no fact shown, no error
    assert p._kg_fact(v, "en") is None
    unknown = TripleVerification("Q1001", "P19", "Q987", False, None, False, "live", "unknown")
    assert p._kg_fact(unknown, "en") is None and p._kg_fact(None, "en") is None


class Resp:
    def __init__(self, data):
        self._d = data
        self.status_code = 200

    def json(self):
        return self._d

    def raise_for_status(self):
        pass


def test_wikidata_keeps_the_actual_value_and_names_it_with_english_fallback(monkeypatch):
    claims = {"claims": {"P19": [{"rank": "normal", "mainsnak": {"datavalue": {"value": {"id": "Q200017"}}}}]}}
    entities = {"entities": {"Q1001": {"labels": {"hi": {"value": "महात्मा गांधी"}}},
                             "Q200017": {"labels": {"en": {"value": "Porbandar"}}}}}
    calls = []

    def fake_get(session, url, params=None, timeout=None):
        calls.append((params["action"], params.get("entity"), params.get("property")))
        return Resp(claims if params["action"] == "wbgetclaims" else entities)

    monkeypatch.setattr("member2_data.wikidata_connector.polite_get", fake_get)
    wd = WikidataConnector()
    r = wd.verify_triple("Q1001", "P19", "Q987")
    assert (r.status, r.actual_values) == ("contradicted", ("Q200017",))
    # the birthplace is fetched once; showing it reuses that (cached) lookup
    assert calls.count(("wbgetclaims", "Q1001", "P19")) == 1
    assert wd.labels(["Q1001", "Q200017"], "hi") == {"Q1001": "महात्मा गांधी", "Q200017": "Porbandar"}

def test_no_excerpt_when_no_sentence_visibly_addresses_the_claim():
    # measured live: the deciding Beijing passage was one sentence about ring roads,
    # rated "contradicts" 0.99 by NLI; quoting it would not explain anything
    class Contra:
        def score_batch(self, claim_ids, premises, hypotheses):
            return [SimpleNamespace(entailment_prob=0.0, contradiction_prob=0.99) for _ in premises]
    p = pipe()
    p.nli_scorer = Contra()
    text = "Beijing is an important transport hub in North China with six ring roads and nine railways."
    pc = {"deciding": ("wiki:en:Beijing::75", "contradicts"), "passage_ids": ["wiki:en:Beijing::75"], "passages": [text]}
    assert p._excerpts(["The capital of Japan is Beijing."], [pc]) == [None]
    on_topic = "Beijing is the capital of the People's Republic of China."
    pc2 = {**pc, "passages": [on_topic]}
    assert p._excerpts(["The capital of Japan is Beijing."], [pc2]) == [on_topic]


def test_names_stored_only_as_multilingual_labels_are_found(monkeypatch):
    # Wikidata keeps some names only under "mul" (e.g. Albert Einstein, Q937)
    entities = {"entities": {"Q937": {"labels": {"mul": {"value": "Albert Einstein"}}},
                             "P19": {"labels": {"en": {"value": "place of birth"}}}}}
    monkeypatch.setattr("member2_data.wikidata_connector.polite_get",
                        lambda session, url, params=None, timeout=None: Resp(entities))
    assert WikidataConnector().labels(["Q937", "P19"], "en") == {"Q937": "Albert Einstein", "P19": "place of birth"}
