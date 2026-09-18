import pytest

from member3_backend.claim_extractor import ClaimExtractor

# Loading spaCy's model is slow — share one extractor instance across all
# tests in this module rather than reloading per test.
@pytest.fixture(scope="module")
def extractor():
    return ClaimExtractor()


def test_simple_sentence_no_decomposition_needed(extractor):
    claims = extractor.extract("Delhi is the capital of India.", "en")
    assert len(claims) == 1
    assert claims[0].text == "Delhi is the capital of India."


def test_multiple_independent_sentences(extractor):
    claims = extractor.extract(
        "Delhi is the capital of India. Mumbai is the financial capital.", "en"
    )
    assert len(claims) == 2
    assert "Delhi" in claims[0].text
    assert "Mumbai" in claims[1].text


def test_appositive_decomposition(extractor):
    claims = extractor.extract(
        "Modi, the Prime Minister of India, visited the temple yesterday.", "en"
    )
    methods = {c.extraction_method for c in claims}
    assert "decomposed_appos" in methods
    assert "decomposed_base" in methods

    appos_claim = next(c for c in claims if c.extraction_method == "decomposed_appos")
    assert "Modi" in appos_claim.text
    assert "Prime Minister" in appos_claim.text

    base_claim = next(c for c in claims if c.extraction_method == "decomposed_base")
    assert "visited" in base_claim.text
    assert "Prime Minister" not in base_claim.text


def test_relative_clause_decomposition(extractor):
    claims = extractor.extract(
        "Modi, who is the Prime Minister of India, visited the temple yesterday.", "en"
    )
    methods = {c.extraction_method for c in claims}
    assert "decomposed_relcl" in methods

    relcl_claim = next(c for c in claims if c.extraction_method == "decomposed_relcl")
    assert "who" not in relcl_claim.text.lower()
    assert "Modi" in relcl_claim.text


def test_coordinated_clause_decomposition(extractor):
    claims = extractor.extract("Modi visited Delhi and met the President.", "en")
    methods = {c.extraction_method for c in claims}
    assert "decomposed_conj" in methods
    assert "decomposed_base" in methods

    conj_claim = next(c for c in claims if c.extraction_method == "decomposed_conj")
    assert "Modi" in conj_claim.text
    assert "President" in conj_claim.text


def test_all_claims_have_original_text_char_spans(extractor):
    text = "Modi, the Prime Minister of India, visited the temple."
    claims = extractor.extract(text, "en")
    for c in claims:
        assert 0 <= c.start_char < c.end_char <= len(text)


def test_empty_text_via_pipeline_semantics(extractor):
    # extract() itself doesn't reject empty text (that's pipeline.py's job,
    # via the "no claims extracted" ValueError) — but it should return an
    # empty list rather than crashing.
    claims = extractor.extract("", "en")
    assert claims == []


def test_over_word_limit_raises(extractor):
    long_text = " ".join(["word"] * 2001)
    with pytest.raises(ValueError):
        extractor.extract(long_text, "en")


def test_hindi_sentence_level_extraction(extractor):
    text = "गंगा नदी गंगोत्री से निकलती है। यह वाराणसी से होकर बहती है।"
    claims = extractor.extract(text, "hi")
    assert len(claims) == 2
    assert all(c.extraction_method == "sentence_level" for c in claims)


def test_extract_entities_returns_ner_spans(extractor):
    entities = extractor.extract_entities("Narendra Modi visited Paris in 2023.", "en")
    assert "Narendra Modi" in entities


def test_extract_entities_empty_for_hindi(extractor):
    # No Hindi NER model wired in — should return [] rather than guessing.
    entities = extractor.extract_entities("मोदी जी दिल्ली गए।", "hi")
    assert entities == []


def test_known_limitation_nearest_entity_coref_can_pick_wrong_referent(extractor):
    """
    DOCUMENTED LIMITATION, not a silent bug — see module docstring item 1.
    spaCy's small model mis-parses "Ganga" as a compound modifier rather
    than the sentence subject here, so "it" falls back to nearest-entity-
    by-proximity and resolves to "Gangotri" instead of "Ganga". This test
    locks in and documents that known behavior on purpose.
    """
    text = "The Ganga originates in Gangotri and it flows through Varanasi."
    claims = extractor.extract(text, "en")
    conj_claim = next(c for c in claims if c.extraction_method == "decomposed_conj")
    assert "Gangotri" in conj_claim.text  # known-wrong resolution, tracked here on purpose
