"""Professional fact-checks: the API client (member2_data/factcheck.py) and when a
fact-check decides a claim (member3_backend/factcheck_rules.py). No network."""
from types import SimpleNamespace

import numpy as np

from member2_data.factcheck import FactCheck, FactChecker, normalise_rating
from member3_backend.factcheck_rules import FactCheckMatch, decide, match


def fc(text, rating, publisher="PIB Fact Check"):
    return FactCheck(claim_text=text, rating=rating, verdict=normalise_rating(rating), publisher=publisher,
                     url="https://example.org/check", review_date="2024-01-01", language="en")


def test_ratings_qualified_ones_never_count_as_false_or_true():
    assert [normalise_rating(r) for r in ("False", "Fake", "Pants on Fire", "Not true", "गलत", "फर्जी")] == ["false"] * 6
    assert [normalise_rating(r) for r in ("True", "Correct", "सही")] == ["true"] * 3
    for r in ("Partly false", "Misleading", "Missing context", "Mostly true", "Satire", "भ्रामक"):
        assert normalise_rating(r) == "mixed", r
    assert normalise_rating("Truth unknown") is None and normalise_rating("") is None
    assert normalise_rating("सही नहीं") == "false"


class FakeResponse:
    status_code = 200

    def json(self):
        return {"claims": [{"text": "Drinking hot water kills the coronavirus.",
                            "claimReview": [{"publisher": {"name": "Factly"}, "url": "https://factly.in/x",
                                             "textualRating": "False", "reviewDate": "2020-03-20",
                                             "languageCode": "en"}]}]}


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append(params)
        return FakeResponse()


def test_client_parses_caches_and_needs_a_key(tmp_path, monkeypatch):
    s = FakeSession()
    checker = FactChecker(cache_dir=tmp_path, session=s)
    monkeypatch.delenv("GOOGLE_FACTCHECK_KEY", raising=False)
    assert checker.search("hot water kills coronavirus", "en") == [] and not s.calls  # no key: no call
    monkeypatch.setenv("GOOGLE_FACTCHECK_KEY", "test-key")
    [r] = checker.search("hot water kills coronavirus", "en")
    assert (r.publisher, r.rating, r.verdict) == ("Factly", "False", "false")
    assert checker.search("hot water kills coronavirus", "en")[0].url == "https://factly.in/x"
    assert len(s.calls) == 1  # second lookup from the disk cache
    assert "test-key" not in "".join(p.read_text(encoding="utf-8") for p in tmp_path.iterdir())


def test_client_failure_is_no_signal(tmp_path, monkeypatch):
    class Broken:
        def get(self, *a, **k):
            raise __import__("requests").ConnectionError("offline")
    monkeypatch.setenv("GOOGLE_FACTCHECK_KEY", "test-key")
    assert FactChecker(cache_dir=tmp_path, session=Broken()).search("anything", "en") == []


def m(check, sim=0.9, fwd=0.9, back=0.9, contra=0.0):
    return FactCheckMatch(check, sim, fwd, back, contra)


def test_a_rating_decides_only_when_logic_carries_it_over_to_our_claim():
    false = fc("Hot water kills the coronavirus.", "False")
    true = fc("Hot water kills the coronavirus.", "True")
    assert decide([m(false)]).check is false and decide([m(true)]).check is true
    # rated false: OUR claim must entail the checked one (ours implies a false statement)
    assert decide([m(false, fwd=0.9, back=0.1)]).check is false
    assert decide([m(false, fwd=0.1, back=0.9)]) is None
    # rated true: the CHECKED claim must entail ours
    assert decide([m(true, fwd=0.1, back=0.9)]).check is true
    assert decide([m(true, fwd=0.9, back=0.1)]) is None
    assert decide([m(false, contra=0.5)]) is None       # any contradiction: e.g. a negation
    assert decide([m(false, sim=0.3)]) is None           # another topic
    assert decide([m(fc("Hot water kills the coronavirus.", "Misleading"))]) is None
    assert decide([m(false), m(true)]) is None           # fact-checks disagree
    assert decide([]) is None

def test_match_uses_both_nli_directions():
    claim, checked = "Hot water does not cure COVID.", "Hot water cures COVID."

    class Emb:
        def embed(self, ids, texts, langs, use_muril=None):
            return SimpleNamespace(vectors=np.array([[1.0, 0.0]] * len(texts)))  # identical meaning vectors

    class NLI:  # a negation: each contradicts the other
        def score_batch(self, claim_ids, premises, hypotheses):
            return [SimpleNamespace(entailment_prob=0.01, contradiction_prob=0.98) for _ in premises]

    [r] = match(claim, "en", [fc(checked, "False")], Emb(), NLI())
    assert r.similarity > 0.99 and not r.applies
    assert decide([r]) is None


def test_pipeline_uses_a_matching_fact_check_and_keeps_the_score_otherwise():
    from member1_model.cmhsa import ClaimScore, Verdict
    from member3_backend.pipeline import DetectionPipeline

    base = ClaimScore(claim_id="claim_0", hallu_score=0.5, verdict=Verdict.UNCERTAIN, active_signals=["nli"])
    pipe = DetectionPipeline.__new__(DetectionPipeline)

    class Emb:
        def embed(self, ids, texts, langs, use_muril=None):
            return SimpleNamespace(vectors=np.array([[1.0, 0.0]] * len(texts)))

    class NLI:
        def __init__(self, e):
            self.e = e

        def score_batch(self, claim_ids, premises, hypotheses):
            return [SimpleNamespace(entailment_prob=self.e, contradiction_prob=0.0) for _ in premises]

    class Checker:
        def search(self, claim, language):
            return [fc("Hot water kills the coronavirus.", "False", "Factly")]

    pipe.embedder, pipe.fact_checker = Emb(), Checker()
    pipe.nli_scorer = NLI(0.95)
    s, info = pipe._fact_check(base, "Drinking hot water kills the coronavirus.", "en")
    assert s.verdict == Verdict.HALLUCINATED and "factcheck" in s.active_signals
    assert s.note.startswith("fact-checked by Factly") and info["rating"] == "False"
    pipe.nli_scorer = NLI(0.2)  # not the same claim: unchanged
    assert pipe._fact_check(base, "Drinking hot water kills the coronavirus.", "en") == (base, None)
