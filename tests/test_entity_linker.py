from unittest.mock import MagicMock

from member2_data.entity_linker import EntityLinker


def _mock_search_response(results):
    resp = MagicMock()
    resp.json.return_value = {"search": results}
    return resp


def test_search_entity_finds_top_match():
    session = MagicMock()
    session.get.return_value = _mock_search_response(
        [{"id": "Q1058", "label": "Narendra Modi"}]
    )

    linker = EntityLinker(session=session)
    match = linker.search_entity("Narendra Modi", language="en")

    assert match.qid == "Q1058"
    assert match.wikidata_label == "Narendra Modi"


def test_search_entity_no_results_returns_none_qid():
    session = MagicMock()
    session.get.return_value = _mock_search_response([])

    linker = EntityLinker(session=session)
    match = linker.search_entity("Some Nonexistent Entity Xyz", language="en")

    assert match.qid is None
    assert match.confidence == 0.0


def test_search_entity_network_failure_returns_none_gracefully():
    import requests

    session = MagicMock()
    session.get.side_effect = requests.exceptions.ConnectionError("down")

    linker = EntityLinker(session=session)
    match = linker.search_entity("Anything", language="en")

    assert match.qid is None


def test_find_relation_pid_matches_known_phrase():
    linker = EntityLinker()
    pid = linker.find_relation_pid("Narendra Modi is the Prime Minister of India")
    assert pid == "P39"


def test_find_relation_pid_returns_none_for_unknown_relation():
    linker = EntityLinker()
    pid = linker.find_relation_pid("Narendra Modi enjoys playing chess on weekends")
    assert pid is None


def test_link_claim_fully_resolves_when_all_parts_found():
    session = MagicMock()
    session.get.side_effect = [
        _mock_search_response([{"id": "Q1058", "label": "Narendra Modi"}]),
        _mock_search_response([{"id": "Q14212", "label": "Prime Minister of India"}]),
    ]

    linker = EntityLinker(session=session)
    result = linker.link_claim(
        claim_text="Narendra Modi is the Prime Minister of India",
        subject_text="Narendra Modi",
        object_text="Prime Minister of India",
    )

    assert result.linkable is True
    assert result.subject_qid == "Q1058"
    assert result.property_pid == "P39"
    assert result.object_qid == "Q14212"


def test_link_claim_not_linkable_when_relation_unknown():
    session = MagicMock()
    session.get.return_value = _mock_search_response([{"id": "Q1058", "label": "Narendra Modi"}])

    linker = EntityLinker(session=session)
    result = linker.link_claim(
        claim_text="Narendra Modi enjoys chess",
        subject_text="Narendra Modi",
        object_text="chess",
    )

    assert result.linkable is False
    assert result.property_pid is None


def test_capital_of_maps_to_p1376_not_p36():
    # "X is the capital of Y" (city -> country) is P1376 ("capital of"), NOT
    # P36 ("capital", country -> city). The old P36 mapping built a reversed
    # triple that always failed verification.
    linker = EntityLinker()
    assert linker.find_relation_pid("Paris is the capital of France") == "P1376"


def test_expanded_relations_resolve():
    linker = EntityLinker()
    assert linker.find_relation_pid("Infosys was founded by N. R. Narayana Murthy") == "P112"
    assert linker.find_relation_pid("Mahatma Gandhi was born in Porbandar") == "P19"
    assert linker.find_relation_pid("The RBI is headquartered in Mumbai") == "P159"


def test_prime_minister_still_maps_to_p39_after_expansion():
    # Regression guard: the enlarged table + longest-first matching must not
    # shadow the P39 relation the pipeline/tests rely on.
    linker = EntityLinker()
    assert linker.find_relation_pid("Narendra Modi is the Prime Minister of India") == "P39"


def test_office_claim_links_the_office_not_the_country():
    # "Modi is the Prime Minister of India" -> (Modi, P39, "Prime Minister of India")
    from unittest.mock import MagicMock
    from member2_data.entity_linker import EntityLinker
    searched = []

    def get(url, params, headers, timeout):
        searched.append(params["search"])
        r = MagicMock()
        r.status_code, r.headers = 200, {}
        r.json.return_value = {"search": [{"id": "Q" + str(len(searched)), "label": params["search"]}]}
        return r
    session = MagicMock()
    session.get.side_effect = get
    t = EntityLinker(session=session).link_claim(
        "Narendra Modi is the Prime Minister of India.", "Narendra Modi", "India")
    assert searched == ["Narendra Modi", "Prime Minister of India"]
    assert t.property_pid == "P39" and t.linkable
