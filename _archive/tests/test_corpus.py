"""Tests for corpus.py. No network: the MediaWiki API is stubbed."""

from __future__ import annotations

import csv

import pytest

import corpus


class _Response:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class StubSession:
    """Answers extract and langlinks queries. Records every call so tests can
    assert that caching prevents refetching."""

    def __init__(self, hindi_for: set[str] | None = None):
        self.calls: list[tuple[str, str]] = []
        self.hindi_for = hindi_for if hindi_for is not None else set()

    def get(self, url, params=None, headers=None, timeout=None):
        language = url.split("//")[1].split(".")[0]
        self.calls.append((language, params.get("prop")))

        if params.get("prop") == "langlinks":
            titles = params["titles"].split("|")
            pages = {}
            for i, title in enumerate(titles):
                links = ([{"lang": "hi", "*": f"HI_{title}"}]
                         if title in self.hindi_for else [])
                pages[str(i)] = {"title": title.replace("_", " "), "langlinks": links}
            normalized = [{"from": t, "to": t.replace("_", " ")} for t in titles]
            return _Response({"query": {"normalized": normalized, "pages": pages}})

        sentence = "वाक्य एक। " if language == "hi" else "Sentence one. "
        body = "\n\n".join(sentence * 30 for _ in range(2))
        return _Response({"query": {"pages": {"1": {"extract": f"{params['titles']}. {body}"}}}})


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(corpus, "CACHE_PATH", tmp_path / "cache.json")
    monkeypatch.setattr(corpus, "REQUEST_DELAY_S", 0)
    yield


@pytest.fixture
def evidence_csv(tmp_path):
    path = tmp_path / "gold.csv"
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["claim_id", "evidence_url"])
        writer.writeheader()
        writer.writerow({"claim_id": "c1",
                         "evidence_url": "https://en.wikipedia.org/wiki/Legislative_procedure_in_India"})
        writer.writerow({"claim_id": "c2",
                         "evidence_url": "https://hi.wikipedia.org/wiki/भारत#इतिहास"})
        writer.writerow({"claim_id": "c3", "evidence_url": ""})
        writer.writerow({"claim_id": "c4", "evidence_url": "https://example.com/not-wikipedia"})
    return path


def test_chunking_respects_bounds_and_drops_fragments():
    text = "short\n\n" + ("A sentence that is long enough to keep. " * 40)
    chunks = corpus.chunk_article_text(text)
    assert chunks, "expected at least one chunk"
    assert all(len(chunk) <= corpus.MAX_CHUNK_CHARS for chunk in chunks)
    assert all(len(chunk) >= corpus.MIN_CHUNK_CHARS for chunk in chunks)
    assert "short" not in chunks


def test_chunking_splits_hindi_on_danda():
    paragraph = "यह एक लंबा हिन्दी वाक्य है जो पर्याप्त लंबा है। " * 20
    chunks = corpus.chunk_article_text(paragraph)
    assert len(chunks) > 1, "danda should act as a sentence boundary"
    assert all(len(chunk) <= corpus.MAX_CHUNK_CHARS for chunk in chunks)


def test_evidence_titles_are_grouped_by_wiki_language(evidence_csv):
    titles = corpus.evidence_titles_from_csvs([evidence_csv])
    assert titles["en"] == {"Legislative_procedure_in_India"}
    assert titles["hi"] == {"भारत"}  # fragment stripped, percent-decoding applied


def test_plan_includes_evidence_titles_and_resolved_hindi(evidence_csv):
    session = StubSession(hindi_for={"Water", "Legislative_procedure_in_India"})
    plan = corpus.plan_titles(("en", "hi"), evidence_csvs=[evidence_csv], session=session)

    assert "Legislative_procedure_in_India" in plan["en"]
    assert set(corpus.STARTER_TOPICS_EN).issubset(set(plan["en"]))
    assert "HI_Water" in plan["hi"]
    assert "भारत" in plan["hi"], "a Hindi evidence_url should enter the Hindi plan directly"
    assert "HI_Black_hole" not in plan["hi"], "unresolved titles must not be invented"


def test_per_chunk_language_matches_its_source_wiki(evidence_csv):
    session = StubSession(hindi_for={"Water"})
    built = corpus.build_corpus(languages=("en", "hi"), evidence_csvs=[evidence_csv],
                                session=session, verbose=False)

    assert len(built.ids) == len(built.texts) == len(built.languages)
    assert set(built.languages) == {"en", "hi"}
    for identifier, language in zip(built.ids, built.languages):
        assert identifier.startswith(f"{language}:")
    assert built.chunks_by_language["hi"] > 0, "Hindi passages must reach the index"


def test_second_build_makes_no_network_calls(evidence_csv):
    session = StubSession(hindi_for={"Water"})
    first = corpus.build_corpus(languages=("en", "hi"), evidence_csvs=[evidence_csv],
                                session=session, verbose=False)
    calls_after_first = len(session.calls)

    second = corpus.build_corpus(languages=("en", "hi"), evidence_csvs=[evidence_csv],
                                 session=session, verbose=False)

    assert len(session.calls) == calls_after_first, "cache should serve the whole rebuild"
    assert len(second) == len(first)


def test_failed_fetch_is_reported_not_silently_dropped(evidence_csv, monkeypatch):
    session = StubSession(hindi_for=set())
    monkeypatch.setattr(corpus, "fetch_wikipedia_fulltext",
                        lambda title, language="en", **kwargs: None)
    built = corpus.build_corpus(languages=("en",), evidence_csvs=[evidence_csv],
                                session=session, verbose=False)
    assert len(built) == 0
    assert built.failed_titles, "failures must be recorded for the run summary"
