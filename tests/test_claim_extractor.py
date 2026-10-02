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


# --- IMPROVEMENT_PLAN.md task 1.1: no broken fragments, no lost facts ---------

def test_percent_sign_is_kept_so_the_claim_keeps_its_meaning(extractor):
    claims = extractor.extract("About 65% of the warming is caused by carbon dioxide.", "en")
    assert any("65%" in c.text for c in claims)
    assert not any("65 of the" in c.text for c in claims)


def test_appositive_claim_uses_the_full_subject_phrase(extractor):
    claims = extractor.extract(
        "The Universal Immunization Programme, a vaccination programme, was launched by the "
        "Government of India in 1985.", "en")
    appos = next(c for c in claims if c.extraction_method == "decomposed_appos")
    assert appos.text == "The Universal Immunization Programme is a vaccination programme."


def test_bracketed_asides_do_not_become_claims(extractor):
    # They used to: "X (UIP) is ..." gave "X is UIP." and life dates gave "Ambedkar is 14.",
    # nonsense claims that turned TRUE text into false alarms (diagnosis_true_claims.md).
    text = ("Bhimrao Ramji Ambedkar (14 April 1891 – 6 December 1956) was an Indian jurist. "
            "The Universal Immunization Programme (UIP) is a vaccination programme.")
    claims = extractor.extract(text, "en")
    assert [c.text for c in claims] == ["Bhimrao Ramji Ambedkar was an Indian jurist.",
                                        "The Universal Immunization Programme is a vaccination programme."]
    first = claims[0]
    assert text[first.start_char:first.end_char].startswith("Bhimrao Ramji Ambedkar (14 April")  # offsets intact


def test_existential_there_sentence_is_a_claim(extractor):
    claims = extractor.extract("There are 11 players on a cricket team.", "en")
    assert [c.text for c in claims] == ["There are 11 players on a cricket team."]


def test_label_prefix_is_stripped_to_the_claim(extractor):
    claims = extractor.extract("Capital city: Paris is the capital of France.", "en")
    assert [c.text for c in claims] == ["Paris is the capital of France."]
    assert claims[0].extraction_method == "sentence_level"


def test_bare_list_intro_is_not_a_claim(extractor):
    assert extractor.extract("Its significance includes:", "en") == []
    assert extractor.extract("The rules for a run-out are:", "en") == []


def test_intro_plus_list_line_is_one_claim(extractor):
    claims = extractor.extract(
        "Common symptoms of dengue fever include: High fever, severe headache and "
        "pain behind the eyes.", "en")
    assert len(claims) == 1
    assert "include" in claims[0].text and "High fever" in claims[0].text


def test_conjunct_with_its_own_subject_does_not_borrow_the_auxiliary(extractor):
    claims = extractor.extract(
        "Mass and weight are often used interchangeably, but they have distinct meanings:", "en")
    assert not any(c.text.startswith("Are ") for c in claims)
    assert any("distinct meanings" in c.text for c in claims)


def test_pronoun_is_never_resolved_to_a_number(extractor):
    claims = extractor.extract("In 1947 India became independent. It adopted a constitution.", "en")
    assert any(c.text.startswith("India adopted") for c in claims)
    assert not any("1947 adopted" in c.text for c in claims)


def test_no_emitted_claim_is_broken_by_the_audit_rules(extractor):
    from member3_backend.claim_extractor import is_well_formed_claim
    text = ("Photosynthesis happens in plants. Key Features: Chlorophyll absorbs light. "
            "Registering and regulating political parties. About 65% of the warming is caused "
            "by carbon dioxide. There are 11 players on a cricket team.")
    claims = extractor.extract(text, "en")
    assert claims and all(is_well_formed_claim(c.text, "en") for c in claims)


def test_quality_rule_false_positives_are_fixed():
    from member3_backend.claim_extractor import claim_quality
    # reference numbers are not stripped percentages
    assert claim_quality("Article 370 of the Indian Constitution granted special status "
                         "to Jammu and Kashmir.", "en") == ("ok", "")
    assert claim_quality("There are 11 players on a cricket team.", "en") == ("ok", "")
    # a genuinely stripped % is still caught
    assert claim_quality("The candidate with more than 50 of the total votes is elected.",
                         "en") == ("broken", "stripped_symbol")


def test_list_items_after_a_lead_in_become_claims_on_their_own_lines(extractor):
    # reported: only the lead-in was a claim ("Seek urgent medical care if there is.")
    # and the six warning signs under it were never checked
    text = ("Dengue is spread by Aedes mosquitoes.\n\nSeek urgent medical care if there is:\n\n"
            "Severe abdominal pain\nPersistent vomiting\nVery little urine\n\nMost people recover within two weeks.")
    claims = extractor.extract(text, "en")
    assert [c.text for c in claims] == [
        "Dengue is spread by Aedes mosquitoes.",
        "Seek urgent medical care if there is severe abdominal pain.",
        "Seek urgent medical care if there is persistent vomiting.",
        "Seek urgent medical care if there is very little urine.",
        "Most people recover within two weeks.",
    ]
    assert text[claims[1].start_char:claims[1].end_char] == "Severe abdominal pain"  # highlighted on its own line
    spans = sorted((c.start_char, c.end_char) for c in claims)
    assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:]))  # no overlaps: every item gets highlighted


def test_bulleted_items_join_their_lead_in_and_full_sentence_items_stay_as_they_are(extractor):
    text = ("Common symptoms include:\n- High fever\n- Severe headache\n\n"
            "The rules are:\n1. The virus spreads through mosquito bites.\n2. It does not spread from person to person.")
    texts = [c.text for c in extractor.extract(text, "en")]
    assert texts[:2] == ["Common symptoms include high fever.", "Common symptoms include severe headache."]
    assert "The virus spreads through mosquito bites." in texts
    assert not any(t.startswith("The rules are") for t in texts)


def test_a_heading_before_a_blank_line_is_not_glued_to_the_next_sentence(extractor):
    text = "\U0001FA78 Dengue warning signs \U0001F6A8\n\nDengue is spread by Aedes mosquitoes."
    assert [c.text for c in extractor.extract(text, "en")] == ["Dengue is spread by Aedes mosquitoes."]


def test_a_possessive_pronoun_becomes_a_possessive_name(extractor):
    claims = extractor.extract("Marie Curie won two Nobel Prizes. Her research was on radioactivity.", "en")
    assert claims[1].text == "Marie Curie's research was on radioactivity."

# --- Sentences that are not factual claims are skipped ----------------------------

from member3_backend.claim_extractor import not_a_claim


def test_questions_pleasantries_advice_and_opinions_are_not_claims():
    for s in ("I hope this helps!", "Let me know if you have any other questions.", "Great question!",
              "Let me explain how it works.", "Is it worth visiting?", "You should visit it in winter.",
              "I think it is the most beautiful building ever made.", "Visit it early in the morning.",
              "Make sure to carry water."):
        assert not_a_claim(s, "en"), s
    for s in ("The Taj Mahal is closed on Fridays.", "Note that Agra is in Uttar Pradesh.",
              "In summary, DNA is a molecule that carries genetic information.",
              "Keep in mind that the monument is closed on Fridays.",
              # a list heading run into a fact (an annotated test-set claim, verbatim)
              "Provide instructions for protein synthesis DNA contains the instructions for the production "
              "of proteins which are essential for various cellular functions."):
        assert not not_a_claim(s, "en"), s
    assert not_a_claim("आपको इसे सर्दियों में देखना चाहिए।", "hi") and not_a_claim("क्या आप जाना चाहेंगे?", "hi")
    assert not not_a_claim("ताजमहल आगरा में स्थित है।", "hi")


def test_a_chatbot_answer_keeps_only_its_facts(extractor):
    text = ("Great question! The Taj Mahal is located in Agra. You should definitely visit it in winter! "
            "Is it worth visiting? I hope this helps!")
    assert [c.text for c in extractor.extract(text, "en")] == ["The Taj Mahal is located in Agra."]
    hi = extractor.extract("ताजमहल आगरा में स्थित है। मुझे उम्मीद है कि इससे मदद मिलेगी।", "hi")
    assert [c.text for c in hi] == ["ताजमहल आगरा में स्थित है।"] and hi[0].claim_id == "claim_0"
