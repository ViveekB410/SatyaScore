"""On-demand Wikipedia expansion (no network: the API is mocked)."""
from unittest.mock import MagicMock

import numpy as np

from build_corpus import chunk as corpus_chunk
from member3_backend import wiki_expander as wx
from member3_backend.faiss_retriever import FAISSRetriever


def test_chunking_is_identical_to_the_existing_corpus():
    text = ("Intro paragraph that is long enough to be kept as a passage.\n\n== History ==\n\n"
            + "पहला वाक्य यहाँ है। " * 80 + "\n\nshort\n\n" + "An English sentence goes here. " * 60)
    assert wx.chunk(text) == corpus_chunk(text, "en")
    assert (wx.MIN_CHARS, wx.MAX_CHARS) == (40, 1000)


class FakeEmbedder:
    def embed(self, ids, texts, langs):
        rng = np.random.default_rng(len(texts))
        v = rng.normal(size=(len(texts), 8)).astype(np.float32)
        return MagicMock(vectors=v / np.linalg.norm(v, axis=1, keepdims=True))


def _api(responses):
    """Mock session: route by (host language, request kind)."""
    def get(url, params, headers=None, timeout=None):
        lang = url.split("//")[1].split(".")[0]
        kind = "search" if params.get("list") == "search" else params.get("prop")
        body = responses[(lang, kind)](params)
        r = MagicMock(status_code=200, headers={})
        r.json.return_value = body
        return r
    s = MagicMock()
    s.headers = {}
    s.get.side_effect = get
    return s


def _page(extract):
    return {"query": {"pages": {"1": {"extract": extract}}}}


def test_expansion_adds_new_articles_incrementally_and_skips_known_ones(tmp_path):
    base = np.eye(8, dtype=np.float32)
    r = FAISSRetriever(dim=8, n_clusters=1)
    r.build_index([f"p{i}" for i in range(8)], ["x"] * 8, base)
    long_text = "Mahatma Gandhi was born in Porbandar, a coastal town in Gujarat, India. " * 3
    session = _api({
        ("en", "search"): lambda p: {"query": {"search": [{"title": "Mahatma Gandhi"}, {"title": "Porbandar"}]}},
        ("en", "extracts"): lambda p: _page(long_text),
    })
    ex = wx.WikiExpander(FakeEmbedder(), r, tmp_path, indexed={("en", "Mahatma Gandhi")}, session=session)
    st = ex.expand([("Gandhi was born in Porbandar.", "en")])
    assert st.added_titles == [("en", "Porbandar")]  # the known article is not added again
    assert len(r) == 8 + st.passages_added and st.passages_added >= 1
    # second time: nothing new, and the article text came from the disk cache
    calls = session.get.call_count
    st2 = ex.expand([("Gandhi was born in Porbandar.", "en")])
    assert st2.articles_added == 0 and len(r) == 8 + st.passages_added
    assert session.get.call_count == calls + 1  # only the search, no fetch


def test_hindi_claims_also_bring_the_english_article(tmp_path):
    r = FAISSRetriever(dim=8, n_clusters=1)
    r.build_index([f"p{i}" for i in range(8)], ["x"] * 8, np.eye(8, dtype=np.float32))
    session = _api({
        ("hi", "search"): lambda p: {"query": {"search": [{"title": "पोरबंदर"}]}},
        ("hi", "langlinks"): lambda p: {"query": {"pages": {"1": {"langlinks": [{"lang": "en", "*": "Porbandar"}]}}}},
        ("hi", "extracts"): lambda p: _page("पोरबंदर गुजरात का एक तटीय शहर है और महात्मा गांधी का जन्मस्थान है।" * 2),
        ("en", "extracts"): lambda p: _page("Porbandar is a coastal city in Gujarat and the birthplace of Gandhi. " * 2),
    })
    st = wx.WikiExpander(FakeEmbedder(), r, tmp_path, session=session).expand(
        [("महात्मा गांधी का जन्म पोरबंदर में हुआ था।", "hi")])
    assert st.added_titles == [("hi", "पोरबंदर"), ("en", "Porbandar")]


def test_a_failed_lookup_never_breaks_the_request(tmp_path):
    r = FAISSRetriever(dim=8, n_clusters=1)
    r.build_index([f"p{i}" for i in range(8)], ["x"] * 8, np.eye(8, dtype=np.float32))
    session = MagicMock()
    session.headers = {}
    session.get.side_effect = ConnectionError("offline")
    st = wx.WikiExpander(FakeEmbedder(), r, tmp_path, session=session).expand([("Anything.", "en")])
    assert (st.failures, st.articles_added, len(r)) == (1, 0, 8)


# --- the pipeline switch (off by default) -----------------------------------------

def _pipeline(expander):
    from member1_model.cmhsa import CMHSAScorer
    from member3_backend.faiss_retriever import RetrievalResult, RetrievedPassage
    from member3_backend.pipeline import DetectionPipeline
    embedder = MagicMock()
    embedder.embed.return_value = MagicMock(vectors=np.ones((1, 8), np.float32), model_used=["xlm-r"])
    retriever = MagicMock()
    retriever.retrieve.return_value = RetrievalResult("c", [RetrievedPassage("p", "Evidence.", 0.9)], 1.0, True)
    scorer = CMHSAScorer()
    scorer.load_weights("en", alpha=0.5, beta=0.3, gamma=0.2)
    extractor = MagicMock()
    claim = MagicMock()
    claim.text = "Gandhi was born in Porbandar."
    extractor.extract.return_value = [claim]
    return DetectionPipeline(embedder=embedder, retriever=retriever, scorer=scorer,
                             claim_extractor=extractor, expander=expander), retriever


def test_pipeline_expands_before_retrieval_only_when_switched_on():
    order = []
    expander = MagicMock()
    expander.expand.side_effect = lambda claims: order.append(("expand", claims))
    p, retriever = _pipeline(expander)
    retriever.retrieve.side_effect = lambda *a, **k: order.append(("retrieve",)) or MagicMock(passages=[])
    p.run("Gandhi was born in Porbandar.", "en")
    assert order[0] == ("expand", [("Gandhi was born in Porbandar.", "en")]) and order[1] == ("retrieve",)

    off, _ = _pipeline(None)
    assert off.expander is None
    off.run("Gandhi was born in Porbandar.", "en")  # runs without any expansion

def test_titles_already_in_a_loaded_corpus_are_known():
    from member3_backend.wiki_expander import indexed_titles_from_passages
    passages = [{"id": "Cricket::en::0"}, {"id": "wiki:en:Porbandar::3"}, {"id": "wiki:hi:पोरबंदर::0"},
                {"id": "wiki:en:Porbandar::4"}]
    assert indexed_titles_from_passages(passages) == {("en", "Porbandar"), ("hi", "पोरबंदर")}
