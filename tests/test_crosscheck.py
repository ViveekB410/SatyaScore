from member3_backend.crosscheck import crosscheck_verdict as cc


def test_a_structured_or_fact_check_decision_stands():
    assert cc("Hallucinated", True, 0.99, "Verified") == "Hallucinated"
    assert cc("Verified", True, 0.10, "Hallucinated") == "Verified"


def test_verified_needs_passage_support_and_the_llm():
    assert cc("Verified", False, 0.90, "Verified") == "Verified"
    assert cc("Verified", False, 0.90, "Hallucinated") == "Uncertain"  # 'same topic read as support' is caught
    assert cc("Uncertain", False, 0.50, "Verified") == "Uncertain"     # the LLM alone cannot verify


def test_hallucinated_on_contradiction_or_no_support_plus_llm_false():
    assert cc("Hallucinated", False, 0.20, "Uncertain") == "Hallucinated"  # on-topic contradiction
    assert cc("Uncertain", False, 0.50, "Hallucinated") == "Hallucinated"  # nothing supports it, the LLM says false
    assert cc("Uncertain", False, None, "Hallucinated") == "Hallucinated"  # no relevant passage at all


def test_no_usable_llm_answer_keeps_v1():
    assert cc("Verified", False, 0.90, None) == "Verified"
    assert cc("Uncertain", False, 0.50, "garbage") == "Uncertain"


def test_number_guard_still_blocks_verified():
    assert cc("Uncertain", False, 0.90, "Verified", number_missing=True) == "Uncertain"
    assert cc("Uncertain", False, 0.90, "Hallucinated", number_missing=True) == "Hallucinated"


def test_symmetric_variant_needs_the_llm_for_a_contradiction_too():
    assert cc("Hallucinated", False, 0.20, "Verified") == "Uncertain"  # default: symmetric
    assert cc("Hallucinated", False, 0.20, "Uncertain") == "Hallucinated"
    assert cc("Hallucinated", False, 0.20, "Verified", symmetric=False) == "Hallucinated"  # rule as first chosen


def test_no_evidence_filter():
    from member3_backend.crosscheck import llm_verdict_used as used
    assert used("Hallucinated", "No evidence supports Omar Epps winning that award.") == "Uncertain"
    assert used("Hallucinated", "The claim is not supported by the passages.") == "Uncertain"
    assert used("Hallucinated", "He was born in Porbandar, not Delhi.") == "Hallucinated"
    assert used("Verified", "No evidence against it.") == "Verified"


def test_v4a_contradiction_alone_never_flags():
    assert cc("Hallucinated", False, 0.20, "Uncertain", flag_needs_llm=True) == "Uncertain"
    assert cc("Hallucinated", False, 0.20, "Hallucinated", flag_needs_llm=True) == "Hallucinated"
    assert cc("Uncertain", False, 0.50, "Hallucinated", flag_needs_llm=True) == "Hallucinated"
    assert cc("Uncertain", False, 0.90, "Verified", flag_needs_llm=True) == "Verified"
