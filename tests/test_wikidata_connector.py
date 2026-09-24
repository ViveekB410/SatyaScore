from unittest.mock import MagicMock, patch

import pytest
import requests

from member2_data.wikidata_connector import WikidataConnector


def _mock_response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = {}
    resp.json.return_value = json_data
    return resp


def _claims(pid, qids, rank="normal"):
    return {"claims": {pid: [{"rank": rank, "mainsnak": {"datavalue": {"value": {"id": q}}}}
                             for q in qids]}}


def _session(table):
    """table: {(entity, property): [qids]} served as wbgetclaims responses."""
    session = MagicMock()

    def get(url, params, headers, timeout):
        key = (params.get("entity"), params.get("property"))
        return _mock_response(_claims(key[1], table.get(key, [])))
    session.get.side_effect = get
    return session


# --- three outcomes: supported / contradicted / unknown -----------------------

def test_supported_when_the_value_is_on_record():
    wd = WikidataConnector(session=_session({("Q1058", "P39"): ["Q192711"]}))
    r = wd.verify_triple("Q1058", "P39", "Q192711")
    assert (r.status, r.found, r.confidence, r.source) == ("supported", True, 1.0, "live")


def test_multi_valued_property_not_found_is_unknown_not_false():
    # "Modi is the President of India": P39 holds other offices -> absence proves nothing
    wd = WikidataConnector(session=_session({("Q1058", "P39"): ["Q192711"]}))
    r = wd.verify_triple("Q1058", "P39", "Q313383")
    assert (r.status, r.found, r.confidence) == ("unknown", False, None)


def test_single_valued_property_with_a_different_value_is_contradicted():
    # "Paris is the capital of Germany": Paris P1376 = France
    wd = WikidataConnector(session=_session({("Q90", "P1376"): ["Q142"]}))
    r = wd.verify_triple("Q90", "P1376", "Q183")
    assert (r.status, r.confidence) == ("contradicted", 0.0)


def test_single_valued_property_with_no_value_is_unknown():
    wd = WikidataConnector(session=_session({}))
    r = wd.verify_triple("Q90", "P1376", "Q183")
    assert (r.status, r.confidence) == ("unknown", None)


def test_place_claim_holds_through_an_enclosing_region():
    # "The Taj Mahal is located in India": Taj -P131-> Agra -P17-> India
    wd = WikidataConnector(session=_session({("Q9141", "P131"): ["Q42941"],
                                             ("Q42941", "P17"): ["Q668"]}))
    assert wd.verify_triple("Q9141", "P131", "Q668").status == "supported"


def test_birthplace_outside_the_region_is_contradicted():
    # "Gandhi was born in Pakistan": born in Porbandar, which is in India
    wd = WikidataConnector(session=_session({("Q1001", "P19"): ["Q1934"],
                                             ("Q1934", "P17"): ["Q668"]}))
    assert wd.verify_triple("Q1001", "P19", "Q843").status == "contradicted"


def test_preferred_rank_wins_and_deprecated_is_ignored():
    session = MagicMock()
    session.get.return_value = _mock_response({"claims": {"P36": [
        {"rank": "deprecated", "mainsnak": {"datavalue": {"value": {"id": "Q_OLD"}}}},
        {"rank": "preferred", "mainsnak": {"datavalue": {"value": {"id": "Q_NOW"}}}},
        {"rank": "normal", "mainsnak": {"datavalue": {"value": {"id": "Q_NORMAL"}}}}]}})
    wd = WikidataConnector(session=session)
    assert wd.verify_triple("Q1", "P36", "Q_NOW").status == "supported"
    assert wd.verify_triple("Q1", "P36", "Q_OLD").status == "contradicted"


# --- failures and caching -----------------------------------------------------

def test_network_failure_is_unknown_and_not_cached():
    session = MagicMock()
    session.get.side_effect = requests.exceptions.ConnectionError("network down")
    wd = WikidataConnector(session=session)
    r = wd.verify_triple("Q1058", "P39", "Q192711")
    assert (r.status, r.found, r.confidence) == ("unknown", False, None)
    wd.verify_triple("Q1058", "P39", "Q192711")
    assert session.get.call_count == 2  # the failure was not cached for 24h


def test_result_is_cached_on_second_call():
    session = _session({("Q1058", "P39"): ["Q192711"]})
    wd = WikidataConnector(session=session)
    first = wd.verify_triple("Q1058", "P39", "Q192711")
    second = wd.verify_triple("Q1058", "P39", "Q192711")
    assert first.source == "live" and second.source == "cache"
    assert session.get.call_count == 1


@patch("member2_data._http.time.sleep")
def test_rate_limit_429_is_retried_after_waiting(sleep):
    limited = _mock_response({}, status_code=429)
    limited.headers = {"Retry-After": "2"}
    ok = _mock_response(_claims("P39", ["Q192711"]))
    session = MagicMock()
    session.get.side_effect = [limited, ok]
    wd = WikidataConnector(session=session)
    assert wd.verify_triple("Q1058", "P39", "Q192711").status == "supported"
    assert any(call.args[0] == 2.0 for call in sleep.call_args_list)


# --- labels (SPARQL) ------------------------------------------------------------

def test_get_label_falls_back_to_english_when_hindi_missing():
    session = MagicMock()

    def side_effect(url, params, headers, timeout):
        if 'LANG(?label) = "hi"' in params["query"]:
            return _mock_response({"results": {"bindings": []}})  # no Hindi label
        return _mock_response({"results": {"bindings": [{"label": {"value": "Mount Everest"}}]}})

    session.get.side_effect = side_effect
    label, used_fallback = WikidataConnector(session=session).get_label("Q513", language="hi")
    assert label == "Mount Everest"
    assert used_fallback is True


def test_get_label_no_fallback_needed_when_native_label_exists():
    session = MagicMock()
    session.get.return_value = _mock_response(
        {"results": {"bindings": [{"label": {"value": "एवरेस्ट पर्वत"}}]}})
    label, used_fallback = WikidataConnector(session=session).get_label("Q513", language="hi")
    assert label == "एवरेस्ट पर्वत"
    assert used_fallback is False
